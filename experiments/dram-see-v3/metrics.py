"""Matched-curve v3 observables; no scalar-offset substitution or legacy labels."""
import argparse
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('_v3_archive_audit_for_metrics', HERE / 'audit.py')
audit_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_module)
THRESHOLDS_V = audit_module.THRESHOLDS_V
sample = audit_module.sample
classification = audit_module.classification


def _bundle_checked(bundle):
    if not isinstance(bundle, dict) or not {'parameters', 'circuit', 'summary'} <= set(bundle):
        raise ValueError('Need complete audited curve bundle')
    p = bundle['parameters']
    if p.get('schema') != 'dram-see-v3' or bundle['summary'].get('audit_status') != 'NUMERICAL_CONTRACT_PASSED':
        raise ValueError('Curve source has not passed the v3 raw audit')
    if bundle['summary'].get('parameters') != p:
        raise ValueError('Curve/summary parameters differ')
    contract = audit_module.matching_key(p)
    rows = audit_module.clean(bundle['circuit'])
    if abs(rows[-1]['time'] - 4e-9) > 1e-18:
        raise ValueError('Curve does not reach final sample')
    for time in (.95e-9, 2.8e-9, 3.8e-9, 4e-9):
        for key in ('v(sn)', 'v(bl)'):
            if not math.isfinite(sample(rows, key, time)):
                raise ValueError('Nonfinite required observation')
    return p, contract, rows


def _source(bundle):
    summary = bundle['summary']
    return {'run_id': summary['run_id'], 'archive_sha256': summary['archive_sha256'], 'mesh_sha256': summary['mesh_sha256'],
            'matching_contract_sha256': bundle['parameters']['matching_contract_sha256']}


def _same_mesh(*bundles):
    hashes = [bundle['summary'].get('mesh_sha256') for bundle in bundles]
    if any(not isinstance(value, str) or len(value) != 64 for value in hashes) or len(set(hashes)) != 1:
        raise ValueError('Actual mesh bytes differ or mesh hash is missing; geometry script equality is insufficient')


def _window(signal, neutral, sign):
    times = sorted({3.8e-9, 4e-9} | {row['time'] for rows in (signal, neutral) for row in rows if 3.8e-9 <= row['time'] <= 4e-9})
    values = [sign * (sample(signal, 'v(bl)', time) - sample(neutral, 'v(bl)', time)) for time in times]
    return {'start_s': 3.8e-9, 'end_s': 4e-9, 'start_margin_V': values[0], 'end_margin_V': values[-1],
            'endpoint_change_V': values[-1] - values[0], 'min_margin_V': min(values),
            'max_margin_V': max(values), 'range_V': max(values) - min(values),
            'classification_stability': {str(epsilon): len({classification(value, epsilon) for value in values}) == 1 for epsilon in THRESHOLDS_V}}


def compute_curves(signal, control, neutral):
    """Pure curve calculation; production callers should use compute(run IDs)."""
    ps, ks, cs = _bundle_checked(signal)
    pc, kc, cc = _bundle_checked(control)
    pn, kn, cn = _bundle_checked(neutral)
    if ks != kc or ks != kn:
        raise ValueError('Signal/control/neutral complete matching keys differ')
    _same_mesh(signal, control, neutral)
    if ps['reference_mode'] != 'offline' or pc['reference_mode'] != 'offline' or pn['reference_mode'] != 'offline':
        raise ValueError('Offline metrics require three independent single-device curves')
    if ps.get('neutral') or pc.get('neutral') or not pn.get('neutral') or pn.get('target_voltage_V') != .5:
        raise ValueError('Wrong signal/control/neutral roles')
    if ps.get('stored_bit') not in (0, 1) or pc.get('stored_bit') != ps['stored_bit'] or pc['target_voltage_V'] != ps['target_voltage_V']:
        raise ValueError('Matched control has different original bit/initialization')
    for p in (pc, pn):
        if p.get('charge_pc') != 0 or p.get('source_event') or p.get('particle') or p.get('source_evidence_sha256'):
            raise ValueError('Control/reference must be a no-particle run')
    sign = 2 * ps['stored_bit'] - 1
    d = sample(cs, 'v(bl)', 4e-9) - sample(cn, 'v(bl)', 4e-9)
    dcontrol = sample(cc, 'v(bl)', 4e-9) - sample(cn, 'v(bl)', 4e-9)
    margin, margin_control = sign * d, sign * dcontrol
    delta_q = ps['capacitance_F'] * (sample(cs, 'v(sn)', 2.8e-9) - sample(cc, 'v(sn)', 2.8e-9)) * 1e15
    result = {'schema': 'dram-see-v3-matched-metrics', 'stored_bit': ps['stored_bit'],
              'matching_contract_sha256': ps['matching_contract_sha256'],
              'sources': {'signal': _source(signal), 'control': _source(control), 'neutral': _source(neutral)},
              'deltaQ_fC': delta_q, 'D4_V': d, 'M4_V': margin, 'control_D4_V': dcontrol,
              'control_M4_V': margin_control, 'deltaM_V': margin_control - margin,
              'classification': {str(epsilon): classification(margin, epsilon) for epsilon in THRESHOLDS_V},
              'control_classification': {str(epsilon): classification(margin_control, epsilon) for epsilon in THRESHOLDS_V},
              'read_window': _window(cs, cn, sign), 'control_read_window': _window(cc, cn, sign),
              'validity': 'metrics_computed; physical_reference_and_sensitivity_gates_must_be_joined_before_final_validity',
              'interpolation': 'piecewise linear on original samples; union of breakpoints for 3.8–4 ns extrema; no extrapolation',
              'definitions': {'deltaQ_fC': 'Cstore*(SNsignal(2.8ns)-SNcontrol(2.8ns))*1e15',
                              'D4_V': 'BLsignal(4ns)-BLneutral(4ns)',
                              'M4_V': '(2*original_bit-1)*D4', 'deltaM_V': 'Mcontrol-Msignal'},
              'scope': 'Criterion readout margin of uncalibrated model; no fixed common-mode subtraction'}
    return result


def compare_physical_curves(physical, signal, neutral):
    """Both BLs and D must pass separately: shared voltage error cannot cancel."""
    pp, kp, cp = _bundle_checked(physical)
    ps, ks, cs = _bundle_checked(signal)
    pn, kn, cn = _bundle_checked(neutral)
    if kp != ks or kp != kn:
        raise ValueError('Physical/offline matching parameters differ')
    _same_mesh(physical, signal, neutral)
    if pp.get('reference_mode') != 'physical' or ps.get('reference_mode') != 'offline' or pn.get('reference_mode') != 'offline':
        raise ValueError('Wrong physical/offline reference modes')
    if pp.get('neutral') or ps.get('neutral') or not pn.get('neutral'):
        raise ValueError('Wrong physical/offline branch roles')
    if pp.get('stored_bit') != ps.get('stored_bit') or pp['target_voltage_V'] != ps['target_voltage_V']:
        raise ValueError('Different signal initial bit')
    for key in ('charge_pc', 'seed', 'particle', 'energy_MeV', 'angle_deg', 'source_evidence_sha256'):
        if pp.get(key) != ps.get(key):
            raise ValueError('Physical/offline source mismatch: ' + key)
    if pn.get('charge_pc') != 0 or pn.get('particle') or pn.get('source_event'):
        raise ValueError('Reference must be unirradiated')
    source_zero = physical['summary'].get('radiation', {}).get('reference_source_zero')
    if not isinstance(source_zero, dict) or source_zero.get('verified') is not True:
        raise ValueError('Physical reference has no zero-source audit')
    bps, bpr = sample(cp, 'v(bl)', 4e-9), sample(cp, 'v(ref)', 4e-9)
    bos, bor = sample(cs, 'v(bl)', 4e-9), sample(cn, 'v(bl)', 4e-9)
    differences = {'signal_BL_V': bps - bos, 'reference_BL_V': bpr - bor, 'D_V': (bps - bpr) - (bos - bor)}
    sign = 2 * pp['stored_bit'] - 1
    physical_classes = {str(e): classification(sign * (bps - bpr), e) for e in THRESHOLDS_V}
    offline_classes = {str(e): classification(sign * (bos - bor), e) for e in THRESHOLDS_V}
    passed = all(abs(value) <= .0001 for value in differences.values()) and physical_classes == offline_classes
    return {'schema': 'dram-see-v3-reference-validation',
            'status': 'PASSED' if passed else 'FAILED', 'passed': passed, 'tolerance_V': .0001,
            'differences_4ns': differences, 'physical_classification': physical_classes,
            'offline_classification': offline_classes, 'classification_agreement': physical_classes == offline_classes,
            'sources': {'physical': _source(physical), 'signal': _source(signal), 'neutral': _source(neutral)},
            'matching_contract_sha256': pp['matching_contract_sha256'],
            'scope': 'This matched bit/geometry/source only; no automatic whole-matrix validation'}


def compute(signal_run, control_run, neutral_run, export=False):
    result = compute_curves(*(audit_module.load_curves(run) for run in (signal_run, control_run, neutral_run)))
    if export:
        destination = HERE / 'data/metrics'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / (signal_run + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return result


def compare_physical(physical_run, signal_run, neutral_run, export=False):
    result = compare_physical_curves(*(audit_module.load_curves(run) for run in (physical_run, signal_run, neutral_run)))
    if export:
        destination = HERE / 'data/reference-validation'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / (physical_run + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return result


def _load_input(value):
    if isinstance(value, str):
        return audit_module.load_curves(value)
    if isinstance(value, dict) and 'run_id' in value:
        loaded = audit_module.load_curves(value['run_id'])
        if loaded['summary']['archive_sha256'] != value.get('archive_sha256'):
            raise ValueError('Audit summary no longer matches original archive')
        return loaded
    raise ValueError('Expected run ID or audit summary, not unaudited curve data')


def paired_metrics(event, control, neutral):
    """Controller interface: each argument is a run ID or audit() summary."""
    return compute_curves(*(_load_input(value) for value in (event, control, neutral)))


def compare_reference(physical, signal, neutral):
    """Controller interface: returns PASSED/FAILED without relaxing tolerances."""
    return compare_physical_curves(*(_load_input(value) for value in (physical, signal, neutral)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    compute_parser = commands.add_parser('compute')
    compute_parser.add_argument('signal_run')
    compute_parser.add_argument('control_run')
    compute_parser.add_argument('neutral_run')
    compare_parser = commands.add_parser('compare-physical')
    compare_parser.add_argument('physical_run')
    compare_parser.add_argument('signal_run')
    compare_parser.add_argument('neutral_run')
    for subparser in (compute_parser, compare_parser):
        subparser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    result = (compute(args.signal_run, args.control_run, args.neutral_run, args.export) if args.command == 'compute'
              else compare_physical(args.physical_run, args.signal_run, args.neutral_run, args.export))
    print(json.dumps(result, indent=2))
