"""Read archived real Sentaurus results, validate electrical contracts, export CSV/PNG."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def parse_plt(text):
    datasets = re.search(r'datasets\s*=\s*\[(.*?)\]', text, re.S)
    block = re.search(r'\bData\s*\{(.*?)\}', text, re.S)
    if not datasets or not block:
        raise ValueError('Missing DF-ISE dataset or data section')
    names = re.findall(r'"([^"]+)"', datasets.group(1))
    if not names or len(set(names)) != len(names):
        raise ValueError('Empty or duplicate dataset names')
    values = [float(token) for token in block.group(1).split()]
    if not values or len(values) % len(names) or not all(map(math.isfinite, values)):
        raise ValueError('Truncated, empty or nonfinite PLT data')
    rows = [dict(zip(names, values[i:i+len(names)])) for i in range(0, len(values), len(names))]
    return names, rows


def first_crossing(rows, x, y, threshold):
    for before, after in zip(rows, rows[1:]):
        a, b = abs(before[y]), abs(after[y])
        if 0 < a < threshold <= b:
            fraction = math.log(threshold/a) / math.log(b/a)
            value = before[x] + fraction * (after[x] - before[x])
            return {'value': value, 'threshold': threshold, 'bracket': [[before[x], a], [after[x], b]],
                    'method': 'log-current interpolation of two actual adjacent solver samples'}
    return None


def current_balance(rows):
    worst = 0.0
    max_absolute = 0.0
    for row in rows:
        currents = [row[f'{contact} TotalCurrent'] for contact in ['source', 'drain', 'gate']]
        residual = abs(sum(currents))
        tolerance = max(1e-12, 1e-3 * max(map(abs, currents)))
        worst = max(worst, residual/tolerance)
        max_absolute = max(max_absolute, residual)
    if worst > 1:
        raise ValueError(f'Terminal current conservation exceeded tolerance: {worst}')
    return {'maximum_residual_A_per_um': max_absolute, 'worst_fraction_of_tolerance': worst}


def read_archive(tf, name):
    matches = [m for m in tf.getmembers() if m.isfile() and m.name.removeprefix('./') == name]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one archive file {name}; found {len(matches)}')
    return tf.extractfile(matches[0]).read()


def analyze_run(run_id):
    folder = ROOT / 'local_runtime/runs' / run_id
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest['state'] != 'COLLECTED' or manifest['ssh_exit_code'] != 0:
        raise ValueError(f'Run not successfully collected: {run_id}')
    actual_hash = hashlib.sha256((folder / 'results.tar').read_bytes()).hexdigest()
    if actual_hash != manifest['results_sha256']:
        raise ValueError('Results archive hash mismatch')
    with tarfile.open(folder / 'results.tar') as tf:
        if read_archive(tf, 'exit-code.txt').strip() != b'0':
            raise ValueError('Remote exit-code is not zero')
        if b'ENGINEERING_RUN_COMPLETED' not in read_archive(tf, 'execution.log'):
            raise ValueError('Missing engineering completion marker')
        params = json.loads(read_archive(tf, 'parameters.json'))
        names_t, transfer = parse_plt(read_archive(tf, 'idvg_transfer_des.plt').decode())
        transfer_sources = ['idvg_transfer_des.plt']
        if transfer[0]['gate OuterVoltage'] > 0:
            init_names, initial = parse_plt(read_archive(tf, 'transfer_des.plt').decode())
            zero = initial[-1]
            if init_names != names_t or abs(zero['gate OuterVoltage']) > 1e-7:
                raise ValueError('Missing compatible true zero-gate initialization sample')
            if not math.isclose(zero['drain InnerVoltage'], .1, abs_tol=1e-7):
                raise ValueError('Initialization sample has wrong drain bias')
            transfer.insert(0, zero)
            transfer_sources.insert(0, 'transfer_des.plt:last actual drain-initialization sample')
        names_b, breakdown = parse_plt(read_archive(tf, 'breakdown_des.plt').decode())
        for name in ['transfer_des.log', 'breakdown_des.log']:
            log = read_archive(tf, name).decode(errors='replace')
            trace_done = 'Curve trace finished' in log
            safety_stop = name == 'breakdown_des.log' and 'Contact current exceeded limit:' in log
            if 'Sentaurus Device simulation finished' not in log or not (trace_done or safety_stop):
                raise ValueError(f'Missing successful trace or declared safety stop in {name}')
        if not math.isclose(transfer[-1]['gate OuterVoltage'], 10, abs_tol=1e-7):
            raise ValueError('Transfer curve did not reach VGS=10 V')
        if any(not math.isclose(row['drain InnerVoltage'], .1, abs_tol=1e-7) for row in transfer):
            raise ValueError('IDVG does not have the specified VDS=0.1 V')
        if any(abs(row['gate OuterVoltage']) > 1e-7 for row in breakdown):
            raise ValueError('Breakdown gate is not zero')
        if not (abs(breakdown[-1]['drain TotalCurrent']) >= 5e-6 or
                math.isclose(breakdown[-1]['drain OuterVoltage'], 1000, abs_tol=1e-5)):
            raise ValueError('Breakdown reached neither safety current nor supply goal')
        vth = first_crossing(transfer, 'gate OuterVoltage', 'drain TotalCurrent', 1e-7)
        bv = first_crossing(breakdown, 'drain InnerVoltage', 'drain TotalCurrent', 1e-6)
        ion_names = [n for n in names_b if 'ImpactIonization' in n]
        if len(ion_names) != 1:
            raise ValueError('Missing unambiguous semiconductor impact-ionization integral')
        bracket_voltages = {point[0] for point in bv['bracket']} if bv else set()
        avalanche_samples = []
        for row in breakdown:
            if row['drain InnerVoltage'] in bracket_voltages or row is breakdown[-1]:
                # Installed BVmethods example: integral * q * 1e-12 (um^3 to cm^3).
                generated = abs(row[ion_names[0]]) * 1.602176634e-19 * 1e-12
                current = abs(row['drain TotalCurrent'])
                avalanche_samples.append({
                    'internal_vds_V': row['drain InnerVoltage'],
                    'drain_current_A_per_um': current,
                    'impact_ionization_current_A_per_um': generated,
                    'generation_to_drain_current_ratio': generated/current if current else None})
        summary = {'run_id': run_id, 'parameters': params, 'results_sha256': actual_hash,
                   'transfer_sources': transfer_sources,
                   'input_sha256': manifest['input_sha256'],
                   'transfer_points': len(transfer), 'breakdown_points': len(breakdown),
                   'vth': vth, 'bv_current_criterion': bv,
                   'id_vg10_A_per_um': transfer[-1]['drain TotalCurrent'],
                   'id_vg0_A_per_um': transfer[0]['drain TotalCurrent'],
                   'last_inner_vd_V': breakdown[-1]['drain InnerVoltage'],
                   'last_supply_vd_V': breakdown[-1]['drain OuterVoltage'],
                   'last_id_A_per_um': breakdown[-1]['drain TotalCurrent'],
                   'last_impact_ionization': {n: breakdown[-1][n] for n in ion_names},
                   'avalanche_samples': avalanche_samples,
                   'last_semiconductor_peak_field': {n: breakdown[-1][n] for n in names_b if 'ElectricField' in n},
                   'transfer_balance': current_balance(transfer),
                   'breakdown_balance': current_balance(breakdown),
                   'status': 'Electrical contract passed; uncalibrated physical model',
                   'tdr_bytes': {n: len(read_archive(tf, n)) for n in ['vdmos_msh.tdr','transfer_des.tdr','breakdown_des.tdr']}}
    return summary, (names_t, transfer), (names_b, breakdown)


def write_csv(path, names, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def compare_resolution(summaries):
    reference = {s['parameters']['dose_krad_SiO2']: s for s in summaries if s['kind'] == 'production'}
    comparisons = []
    for refined in summaries:
        if refined['kind'] != 'verification':
            continue
        dose = refined['parameters']['dose_krad_SiO2']
        base = reference[dose]
        for key in ['not_cm2', 'nit_total_cm2', 'area_factor', 'generator_sha256']:
            if base['parameters'][key] != refined['parameters'][key]:
                raise ValueError(f'Resolution comparison changed physical input: {key}')
        if not base['vth'] or not refined['vth'] or not base['bv_current_criterion'] or not refined['bv_current_criterion']:
            raise ValueError('Resolution comparison lacks bracketed Vth or BV')
        vth_delta = abs(refined['vth']['value'] - base['vth']['value'])
        id_relative = abs(refined['id_vg10_A_per_um']/base['id_vg10_A_per_um'] - 1)
        bv_relative = abs(refined['bv_current_criterion']['value']/base['bv_current_criterion']['value'] - 1)
        comparisons.append({'dose_krad_SiO2': dose, 'reference_run_id': base['run_id'],
                            'verification_run_id': refined['run_id'],
                            'mesh_scale': refined['parameters']['mesh_scale'],
                            'step_scale': refined['parameters']['step_scale'],
                            'absolute_Vth_difference_V': vth_delta,
                            'relative_ID_VG10_difference': id_relative,
                            'relative_BV_difference': bv_relative,
                            'passed': vth_delta <= .05 and id_relative <= .05 and bv_relative <= .05})
    return comparisons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    all_results, production = [], []
    for record in index['runs']:
        summary, trans, breakdown = analyze_run(record['run_id'])
        summary['kind'] = record['kind']
        summary['case_name'] = record['case_name']
        all_results.append(summary)
        stem = record['case_name']
        write_csv(args.output / (stem + '-idvg.csv'), *trans)
        write_csv(args.output / (stem + '-breakdown.csv'), *breakdown)
        if record['kind'] == 'production':
            production.append((summary, trans[1], breakdown[1]))
    all_results.sort(key=lambda r: (r['kind'], r['parameters']['dose_krad_SiO2']))
    (args.output / 'summary.json').write_text(json.dumps(all_results, indent=2) + '\n', encoding='utf-8')
    (args.output / 'resolution-check.json').write_text(
        json.dumps(compare_resolution(all_results), indent=2) + '\n', encoding='utf-8')
    scalar_rows = [{'case': s['case_name'], 'kind': s['kind'], 'dose_krad_SiO2': s['parameters']['dose_krad_SiO2'],
                    'Vth_V': s['vth']['value'] if s['vth'] else '',
                    'BV_current_criterion_V': s['bv_current_criterion']['value'] if s['bv_current_criterion'] else '',
                    'ID_VG10_A_per_um': s['id_vg10_A_per_um'], 'run_id': s['run_id']} for s in all_results]
    if scalar_rows:
        write_csv(args.output/'scalars.csv', list(scalar_rows[0]), scalar_rows)
    if production:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        production.sort(key=lambda item: item[0]['parameters']['dose_krad_SiO2'])
        for filename, xkey, rows_index, log_y, title in [
            ('idvg-linear', 'gate OuterVoltage', 1, False, 'Post-TID VDMOS transfer; VDS=0.1 V, 300 K'),
            ('idvg-log', 'gate OuterVoltage', 1, True, 'Post-TID VDMOS transfer; VDS=0.1 V, 300 K'),
            ('breakdown-iv', 'drain InnerVoltage', 2, True, 'Off-state VDMOS; VGS=0 V, 300 K')]:
            fig, ax = plt.subplots(figsize=(8,5))
            for item in production:
                dose = item[0]['parameters']['dose_krad_SiO2']
                rows = item[rows_index]
                ax.plot([r[xkey] for r in rows], [abs(r['drain TotalCurrent']) for r in rows], label=f'{dose:g} krad')
            if log_y: ax.set_yscale('log')
            ax.set(xlabel='VGS (V)' if rows_index == 1 else 'Internal VDS (V)', ylabel='|ID| (A/um)', title=title)
            ax.grid(True, which='both', alpha=.3); ax.legend()
            fig.text(.5,.01,'Real TCAD samples; uncalibrated effective TID assumptions; half-cell, unit depth',ha='center',fontsize=8)
            fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(args.output/(filename+'.png'),dpi=180); plt.close(fig)
        for filename, key, ylabel, title in [('bv-dose','bv_current_criterion','BV at 1e-6 A/um (V)','Current-criterion BV; not chip rating'),
                                            ('vth-dose','vth','Vth at 1e-7 A/um (V)','Threshold vs effective TID')]:
            fig, ax = plt.subplots(figsize=(7,4.5))
            valid = [item[0] for item in production if item[0][key] is not None]
            ax.plot([s['parameters']['dose_krad_SiO2'] for s in valid], [s[key]['value'] for s in valid],
                    'o-', label=f'Nominal mesh/step: {len(valid)} doses')
            refined = [s for s in all_results if s['kind'] == 'verification' and s[key] is not None]
            if refined:
                ax.scatter([s['parameters']['dose_krad_SiO2'] for s in refined],
                           [s[key]['value'] for s in refined], marker='x', s=70,
                           label='Refined mesh/step: measured endpoints', zorder=3)
                ax.legend()
            ax.ticklabel_format(axis='y', style='plain', useOffset=False)
            ax.set(xlabel='Dose (krad(SiO2))', ylabel=ylabel,title=title); ax.grid(True,alpha=.3)
            fig.text(.5,.01,'Extracted from real solver brackets; uncalibrated training assumptions',ha='center',fontsize=8)
            fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(args.output/(filename+'.png'),dpi=180); plt.close(fig)
    print(json.dumps(scalar_rows, indent=2))


if __name__ == '__main__':
    main()
