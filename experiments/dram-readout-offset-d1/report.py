"""Present existing D1 audits; never run a solver or change scientific decisions.

Run after the controller stops writing, with the existing plotting environment:
  local_runtime/vdmos-analysis-venv/Scripts/python.exe -B experiments/dram-readout-offset-d1/report.py
"""

import csv
import hashlib
import json
import re
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / 'local_runtime/dram-readout-offset-d1'
ORIGINAL_BASE = '20261010T014743Z-v2-base-l025-b1-143253c7'
ORIGINAL_ALPHA = '20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa'
PRIOR_PATH = ROOT / 'local_runtime/dram-readout-offset-diagnostic/inspection/sign-check-and-alpha101-charge.json'
ORIGINAL_DATA = ROOT / 'experiments/dram-see-v2/data/tcad'
SUMMARY_FIELDS = (
    'run_id', 'initial_SN_V', 'read_SN_V', 'read_BL_V', 'final_SN_V',
    'final_BL_V', 'final_REF_V', 'D_mV', 'two_capacitor_D_mV', 'offset_mV',
    'charge_predicted_offset_mV', 'SN_BL_gain_fC', 'source_drain_outflow_fC',
    'gate_body_inflow_fC', 'reference_drift_mV', 'SN_BL_endpoint_separation_mV',
    'newton_retries', 'solver_s', 'archive_sha256',
)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_curve(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(stream)]


def relative(path):
    return path.relative_to(ROOT).as_posix()


def historical_attempts(design, ledger):
    """Keep superseded attempts separate from the active case denominator."""
    active_tags = {case['tag'] for case in design['cases']}
    candidates = [(tag, item) for tag, item in ledger.get('runs', {}).items() if tag not in active_tags]
    candidates += [(item.get('case', {}).get('tag'), item) for item in ledger.get('failures', [])
                   if item.get('case', {}).get('tag') not in active_tags]
    rows, paths, seen = [], [], set()
    for tag, item in candidates:
        if not tag or not tag.startswith('rodiag1-'):
            continue
        rid = item.get('run_id')
        if not rid:
            pattern = re.compile(r'^\d{8}T\d{6}Z-' + re.escape(tag) + r'-[0-9a-f]{8}$')
            matches = [folder for folder in (ROOT / 'local_runtime/runs').glob('*-' + tag + '-*')
                       if pattern.fullmatch(folder.name)]
            if len(matches) == 1:
                rid = matches[0].name
        identity = (tag, rid)
        if identity in seen:
            continue
        seen.add(identity)
        row = {'cohort': 'historical_attempt', 'tag': tag, 'state': item.get('state', 'UNKNOWN'),
               'run_id': rid, 'failure_reason': item.get('failure_reason', ''),
               'presentation_error': '', 'raw_manifest_state': None, 'raw_error_excerpt': ''}
        if rid:
            folder = ROOT / 'local_runtime/runs' / rid
            manifest_path, log_path = folder / 'manifest.json', folder / 'console.log'
            if manifest_path.exists():
                manifest = read_json(manifest_path)
                row['raw_manifest_state'] = manifest.get('state')
                row['raw_ssh_exit_code'] = manifest.get('ssh_exit_code')
                paths.append(manifest_path)
            if log_path.exists():
                log = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
                excerpts = [line.strip() for line in log
                            if ('offending input:' in line or 'syntax error' in line.lower())]
                row['raw_error_excerpt'] = ' | '.join(excerpts)
                paths.append(log_path)
        rows.append(row)
    return rows, paths


def collect():
    """Read already audited exports. Missing exports remain explicit, not repaired."""
    design_path = next((HERE / name for name in ('design-r4.json', 'design-r3.json', 'design-r2.json', 'design.json')
                        if (HERE / name).exists()), HERE / 'design.json')
    if not design_path.exists():
        raise RuntimeError('No frozen design-r3.json/design-r2.json/design.json; presentation cannot claim a submitted diagnostic batch')
    ledger_path = LOCAL / 'ledger.json'
    design = read_json(design_path)
    ledger = read_json(ledger_path) if ledger_path.exists() else {'runs': {}, 'failures': []}
    if any(row.get('state') == 'RUNNING' for row in ledger.get('runs', {}).values()):
        raise RuntimeError('Controller has RUNNING cases; wait for a consistent presentation snapshot')
    source_paths = [design_path, Path(__file__)] + ([ledger_path] if ledger_path.exists() else [])
    source_paths.extend(HERE / name for name in ('design.json', 'design-r2.json', 'design-r3.json', 'design-r4.json')
                        if (HERE / name).exists())
    history, history_paths = historical_attempts(design, ledger)
    source_paths.extend(history_paths)
    statuses, cases = [], []
    for case in sorted(design['cases'], key=lambda row: row['order']):
        item = ledger.get('runs', {}).get(case['tag'], {})
        status = {'cohort': 'active_design', 'tag': case['tag'], 'state': item.get('state', 'NOT_STARTED'),
                  'run_id': item.get('run_id'), 'failure_reason': item.get('failure_reason', ''),
                  'presentation_error': ''}
        statuses.append(status)
        if item.get('state') != 'VERIFIED':
            continue
        folder = HERE / 'data' / item['run_id']
        required = [folder / name for name in ('summary.json', 'circuit.csv', 'device.csv')]
        missing = [relative(path) for path in required if not path.is_file()]
        if missing:
            status['presentation_error'] = 'Missing audited exports: ' + ', '.join(missing)
            continue
        summary = read_json(required[0])
        if (summary.get('run_id') != item['run_id'] or
                summary['parameters']['case']['tag'] != case['tag']):
            status['presentation_error'] = 'Export identity differs from ledger/frozen case'
            continue
        circuit, device = read_curve(required[1]), read_curve(required[2])
        if not circuit or not device:
            status['presentation_error'] = 'Empty CSV export'
            continue
        cases.append({'case': case, 'summary': summary, 'circuit': circuit,
                      'device': device, 'sources': required})
        source_paths.extend(required)
    comparisons_path = HERE / 'comparisons.json'
    comparisons = read_json(comparisons_path) if comparisons_path.exists() else None
    if comparisons is not None:
        source_paths.append(comparisons_path)
    prior = None
    if PRIOR_PATH.exists():
        prior = next((row for row in read_json(PRIOR_PATH) if row['run_id'] == ORIGINAL_ALPHA), None)
        source_paths.append(PRIOR_PATH)
    original = {'historical_attempts': history, 'active_design_file': design_path.name}
    for name, rid in (('baseline', ORIGINAL_BASE), ('alpha', ORIGINAL_ALPHA)):
        path = ORIGINAL_DATA / rid / 'summary.json'
        if path.exists():
            original[name] = read_json(path)
            source_paths.append(path)
    alpha_curve_path = ORIGINAL_DATA / ORIGINAL_ALPHA / 'circuit.csv'
    if original.get('alpha') and alpha_curve_path.exists():
        curve = read_curve(alpha_curve_path)
        required_fields = {'time', 'v(bl)', 'v(ref)'}
        if original['alpha'].get('run_id') != ORIGINAL_ALPHA or not curve:
            raise ValueError('Prior alpha evidence identity/CSV mismatch')
        if not all(required_fields.issubset(row) for row in curve):
            raise ValueError('Prior alpha CSV lacks actual differential fields')
        original['alpha_curve_evidence'] = {
            'summary': original['alpha'], 'circuit': curve, 'role': 'prior_particle_evidence',
            'sources': [ORIGINAL_DATA / ORIGINAL_ALPHA / 'summary.json', alpha_curve_path]}
        source_paths.append(alpha_curve_path)
    source_hashes = {relative(path): sha(path) for path in sorted(set(source_paths))}
    return design, ledger, statuses, cases, comparisons, prior, original, source_hashes


def rows_for_summary(statuses, cases, history=()):
    by_tag = {row['case']['tag']: row for row in cases}
    center = by_tag.get('rodiag1-center050')
    result = []
    for status in statuses:
        record = dict(status)
        item = by_tag.get(status['tag'])
        if item:
            summary = item['summary']
            record.update({key: summary.get(key) for key in SUMMARY_FIELDS})
            record.update(variant=item['case']['variant'], sn_target_V=item['case']['sn_target_V'])
            for port, components in summary['port_integrals_fC'].items():
                record.update({f'{port}_{component}_fC': value for component, value in components.items()})
            record['offline_center_BL_reference_D_mV'] = (
                (summary['final_BL_V'] - center['summary']['final_BL_V']) * 1e3 if center else None)
            record['offline_reference_definition'] = 'BL_case(4 ns) - BL_center050(4 ns); diagnostic only'
        result.append(record)
    return result + [dict(row) for row in history]


def plots(cases, source_hashes, original):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.fonttype': 'none'})
    destination = HERE / 'figures'
    destination.mkdir(parents=True, exist_ok=True)
    proof = []
    by_tag = {row['case']['tag']: row for row in cases}

    def arrays(item, table, key):
        return np.array([row[key] for row in item[table]])

    def absent(ax, message):
        ax.text(.5, .5, message, transform=ax.transAxes, ha='center', va='center', color='#666666')

    def legend(ax, **kwargs):
        handles, _ = ax.get_legend_handles_labels()
        if handles:
            ax.legend(**kwargs)

    def save(fig, name, used, conditions, note):
        run_ids = list(dict.fromkeys(row['summary']['run_id'] for row in used))
        footer = ['DATA PLOT (Matplotlib), from existing audited solver exports.',
                  *textwrap.wrap(conditions + ' ' + note, 165), 'Run IDs:']
        footer += run_ids if run_ids else ['None: no eligible completed exports for this figure.']
        fig.set_figheight(max(fig.get_figheight(), 6.7 + .18 * len(run_ids)))
        fig.text(.025, .012, '\n'.join(footer), fontsize=7, va='bottom', color='#333333')
        fig.tight_layout(rect=(0, min(.38, .05 + .025 * len(footer)), 1, .93))
        files = {}
        for extension in ('png', 'svg'):
            path = destination / (name + '.' + extension)
            fig.savefig(path, dpi=170)
            files[extension] = {'path': relative(path), 'sha256': sha(path)}
        paths = sorted({relative(path) for row in used for path in row['sources']})
        proof.append({'figure': name, 'conditions': conditions, 'note': note,
                      'run_ids': run_ids, 'source_files_sha256': {path: source_hashes[path] for path in paths},
                      'diagnostic_run_ids': [row['summary']['run_id'] for row in used if row.get('role') != 'prior_particle_evidence'],
                      'historical_reference_run_ids': [row['summary']['run_id'] for row in used if row.get('role') == 'prior_particle_evidence'],
                      'archive_sha256': {row['summary']['run_id']: row['summary']['archive_sha256'] for row in used},
                      'files': files, 'kind': 'DATA PLOT, not a Sentaurus Visual screenshot'})
        plt.close(fig)

    standard = sorted((row for row in cases if row['case']['variant'] == 'standard'),
                      key=lambda row: row['summary']['read_SN_V'])
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.7))
    if standard:
        sn = [row['summary']['read_SN_V'] for row in standard]
        axes[0].plot(sn, [row['summary']['D_mV'] for row in standard], 'o-', label='Actual D at 4 ns')
        axes[0].plot(sn, [row['summary']['two_capacitor_D_mV'] for row in standard], 's--', label='Closed two-capacitor prediction')
        axes[1].plot(sn, [row['summary']['offset_mV'] for row in standard], 'o-', label='Actual minus two-capacitor prediction')
        axes[1].plot(sn, [row['summary']['charge_predicted_offset_mV'] for row in standard], 'x--', label='Existing audit charge-identity result')
    else:
        for ax in axes:
            absent(ax, 'No VERIFIED standard-WL exports')
    axes[0].set(xlabel='Actual SN before read, 3 ns (V)', ylabel='BL - REF at 4 ns (mV)')
    axes[1].set(xlabel='Actual SN before read, 3 ns (V)', ylabel='Readout offset (mV)')
    for ax in axes:
        ax.grid(alpha=.2)
        legend(ax, fontsize=8)
    fig.suptitle('D1 deterministic SN scan | L=0.25 um, no particle, 300 K')
    save(fig, '01-sn-transfer-and-offset', standard,
         'Cstore=10 fF, CBL=100 fF; standard WL: 0 to 1.8 V over 3.05-3.10 ns; decision readout at 4 ns.',
         'Lines connect actual cases; no fitted curve, extrapolation, bit redefinition, or new event sample.')

    center_items = [by_tag[tag] for tag in ('rodiag1-center050', 'rodiag1-wl-off', 'rodiag1-wl-slow') if tag in by_tag]
    colors = {'standard': '#287d5e', 'wl_off': '#666666', 'wl_slow': '#a85632'}
    labels = {'standard': 'WL 50 ps ramp', 'wl_off': 'WL held at 0 V', 'wl_slow': 'WL 200 ps ramp'}
    fig, axes = plt.subplots(4, 1, figsize=(14, 10.6), sharex=True)
    for item in center_items:
        variant = item['case']['variant']
        tc = arrays(item, 'circuit', 'time') * 1e9
        td = arrays(item, 'device', 'time') * 1e9
        mc, md = (tc >= 3) & (tc <= 4), (td >= 3) & (td <= 4)
        axes[0].plot(tc[mc], arrays(item, 'circuit', 'v(wl)')[mc], color=colors[variant], label=labels[variant])
        axes[1].plot(td[md], arrays(item, 'device', 'gate TotalCurrent')[md] * 1e6, color=colors[variant], label=labels[variant] + ' total')
        axes[1].plot(td[md], arrays(item, 'device', 'gate DisplacementCurrent')[md] * 1e6, '--', color=colors[variant], alpha=.65, label=labels[variant] + ' displacement')
        axes[2].plot(td[md], arrays(item, 'device', 'body TotalCurrent')[md] * 1e6, color=colors[variant], label=labels[variant])
        differential = (arrays(item, 'circuit', 'v(bl)') - arrays(item, 'circuit', 'v(ref)')) * 1e3
        axes[3].plot(tc[mc], differential[mc], color=colors[variant], label=labels[variant])
    if not center_items:
        for ax in axes:
            absent(ax, 'No VERIFIED center-WL contrast exports')
    axes[0].set(ylabel='WL voltage (V)')
    axes[1].set(ylabel='Gate device current (uA)')
    axes[2].set(ylabel='Body device current (uA)')
    axes[3].set(xlabel='Time (ns)', ylabel='BL - REF (mV)', xlim=(3, 4))
    for ax in axes:
        ax.axvline(3.05, color='#aaaaaa', ls=':', lw=.7)
        ax.grid(alpha=.2)
        legend(ax, fontsize=8, ncol=3)
    fig.suptitle('D1 center-state WL and readout contrasts | SN target=0.5 V, no particle')
    save(fig, '02-wl-and-terminal-currents', center_items,
         'L=0.25 um, 300 K, Cstore=10 fF, CBL=100 fF; same WL start=3.05 ns.',
         'Device terminal sign is opposite circuit inflow at source/drain. Gate displacement is not carrier tunneling through oxide.')

    fig, axes = plt.subplots(2, 1, figsize=(15, 8.3), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    if cases:
        x = np.arange(len(cases))
        gates = [row['summary']['port_integrals_fC']['gate']['TotalCurrent'] for row in cases]
        bodies = [row['summary']['port_integrals_fC']['body']['TotalCurrent'] for row in cases]
        nets = [row['summary']['source_drain_outflow_fC'] for row in cases]
        gains = [row['summary']['SN_BL_gain_fC'] for row in cases]
        for shift, values, color, label in ((-.27, gates, '#4a6faf', 'Integral gate total'),
                                          (-.09, bodies, '#c77746', 'Integral body total'),
                                          (.09, nets, '#56886b', '-Integral (source + drain) total'),
                                          (.27, gains, '#8871a5', 'External capacitor charge gain')):
            axes[0].bar(x + shift, values, width=.18, color=color, label=label)
        axes[1].plot(x, np.array(gains) - np.array(nets), 'o-', label='Cap gain minus source/drain net')
        axes[1].plot(x, np.array(nets) - np.array(gates) - np.array(bodies), 's--', label='Source/drain net minus gate+body')
        axes[1].set_xticks(x, [row['case']['tag'].removeprefix('rodiag1-') for row in cases], rotation=30, ha='right')
    else:
        for ax in axes:
            absent(ax, 'No VERIFIED charge-accounting exports')
    axes[0].set(ylabel='Integrated charge (fC)')
    axes[1].set(ylabel='Closure residual (fC)', xlabel='Frozen deterministic case')
    for ax in axes:
        ax.axhline(0, color='#888888', lw=.7)
        ax.grid(axis='y', alpha=.2)
        legend(ax, fontsize=8, ncol=2)
    fig.suptitle('D1 audited four-port charge accounting | 3-4 ns, BE right-endpoint integration')
    save(fig, '03-port-integrals-and-closure', cases,
         'L=0.25 um, no particle; signal branch Cstore=10 fF, CBL=100 fF; reference topology and WL vary by frozen case.',
         'All quantities are existing audit outputs; residuals show their differences, not a new acceptance test.')

    # r2 renames the unsubmitted r1 tag without a Windows case-only collision.
    signal = (by_tag.get('rodiag1-alpha-match') or by_tag.get('rodiag1-alphasn') or
              by_tag.get('rodiag1-alphaSN'))
    center = by_tag.get('rodiag1-center050')
    physical = by_tag.get('rodiag1-matched-ref-r3') or by_tag.get('rodiag1-matched-ref')
    used = [row for row in (signal, center, physical) if row]
    alpha_evidence = original.get('alpha_curve_evidence')
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.7))
    labels4, values4, colors4 = [], [], []
    if signal:
        labels4.append('Ideal 0.5 V REF')
        values4.append(signal['summary']['D_mV'])
        colors4.append('#4a6faf')
        t = arrays(signal, 'circuit', 'time') * 1e9
        mask = (t >= 3) & (t <= 4)
        d = (arrays(signal, 'circuit', 'v(bl)') - arrays(signal, 'circuit', 'v(ref)')) * 1e3
        axes[1].plot(t[mask], d[mask], color=colors4[-1], label=labels4[-1])
        if center:
            labels4.append('Offline center BL')
            values4.append((signal['summary']['final_BL_V'] - center['summary']['final_BL_V']) * 1e3)
            colors4.append('#287d5e')
            ct = arrays(center, 'circuit', 'time') * 1e9
            if ct[0] <= t[mask][0] and ct[-1] >= t[mask][-1]:
                difference = (arrays(signal, 'circuit', 'v(bl)')[mask] - np.interp(t[mask], ct, arrays(center, 'circuit', 'v(bl)'))) * 1e3
                axes[1].plot(t[mask], difference, color=colors4[-1], label=labels4[-1])
    if physical:
        labels4.append('Physical matched REF')
        values4.append(physical['summary']['D_mV'])
        colors4.append('#a85632')
        t = arrays(physical, 'circuit', 'time') * 1e9
        mask = (t >= 3) & (t <= 4)
        d = (arrays(physical, 'circuit', 'v(bl)') - arrays(physical, 'circuit', 'v(ref)')) * 1e3
        axes[1].plot(t[mask], d[mask], '--', color=colors4[-1], label=labels4[-1])
    if alpha_evidence:
        used.append(alpha_evidence)  # Historical evidence only; never appended to D1 cases.
        labels4.append('Prior alpha101\n(different history)')
        values4.append(alpha_evidence['summary']['differential_V'] * 1e3)
        colors4.append('#222222')
        t = arrays(alpha_evidence, 'circuit', 'time') * 1e9
        mask = (t >= 3) & (t <= 4)
        d = (arrays(alpha_evidence, 'circuit', 'v(bl)') - arrays(alpha_evidence, 'circuit', 'v(ref)')) * 1e3
        axes[1].plot(t[mask], d[mask], ':', lw=2, color=colors4[-1], label='Prior alpha101: particle, different history')
    if labels4:
        axes[0].bar(labels4, values4, color=colors4)
        for index, value in enumerate(values4):
            axes[0].annotate(f'{value:.4f}', (index, value), xytext=(0, 5 if value >= 0 else -13), textcoords='offset points', ha='center', fontsize=9)
    else:
        absent(axes[0], 'Signal/reference contrasts not completed')
        absent(axes[1], 'Signal/reference contrasts not completed')
    axes[0].set(ylabel='Diagnostic BL - reference at 4 ns (mV)')
    axes[0].margins(y=.18)
    axes[0].tick_params(axis='x', labelsize=8)
    axes[1].set(xlabel='Time (ns)', ylabel='Diagnostic differential (mV)', xlim=(3, 4))
    for ax in axes:
        ax.axhline(0, color='#888888', lw=.7)
        ax.grid(axis='y', alpha=.2)
    legend(axes[1], fontsize=8)
    fig.suptitle('D1 reference comparison with prior alpha101 | deterministic D1 cases and historical particle evidence')
    save(fig, '04-reference-readout-contrasts', used,
         'L=0.25 um, 50 ps WL ramp, 300 K. D1: no particle, signal target=0.3937277549 V, center target=0.5 V; physical REF adds an access cell.',
         'Prior alpha101: 5 MeV vertical particle, original stored bit 1, different carrier/field history; not a D1 case. Offline center trace uses linear interpolation, not new solver points. Pilot reference and thresholds remain unchanged.')
    return proof


def render_report(design, ledger, statuses, cases, comparisons, prior, original):
    by_tag = {row['case']['tag']: row for row in cases}
    verified = sum(row['state'] == 'VERIFIED' for row in statuses)
    failed = sum(row['state'] == 'FAILED' for row in statuses)
    not_started = sum(row['state'] == 'NOT_STARTED' for row in statuses)
    history = original.get('historical_attempts', [])
    lines = ['# D1 读出偏移诊断结果', '',
             f"当前有效冻结工况{len(design['cases'])}项；active ledger VERIFIED为{verified}项，具备完整呈现导出{len(cases)}项，active FAILED为{failed}项，未开始{not_started}项。另有历史尝试{len(history)}项，单列保留，不增加有效工况数。",
             '本报告呈现已有audit导出，不运行求解、不重新作科学验收。图中只有实际已有数据；缺失项不能视为已完成或零效应。', '',
             '这是无粒子确定性诊断，所有扫描、字线对照和参考支路工况均不是独立粒子事件，不计算概率或置信区间。原v1/v2模型数据、pilot分类和2.5/5/10 mV阈值保持不变。', '',
             '## 完成、失败与未做', '',
             '| tag | ledger状态 | run ID | 失败或呈现缺失原因 |', '|---|---|---|---|']
    if design.get('revision') == 4:
        lines += ['', 'r4为同run中断恢复审计：原执行SSH退出码未知，execution.log因连接中断缺少末尾流标记；完整器件日志、远端exit-code=0、全部输出与输入哈希及科学检验仍通过。原日志未补写，原run没有重跑。恢复快照及证明见该run的collection-recovery目录。', '']
    if any(case['tag'] == 'rodiag1-alpha-match' for case in design['cases']):
        active_file = original.get('active_design_file', 'design-r2.json')
        revision = f'当前采用有效 `{active_file}`。r1→r2只将未提交工况tag `rodiag1-alphaSN` 改为 `rodiag1-alpha-match`；物理条件、执行顺序、阈值与九工况总数不变。'
        if any(case['tag'] == 'rodiag1-matched-ref-r3' for case in design['cases']):
            revision += ' r2→r3只修订匹配参考实例名 `reference→refcell` 及随之改变的原始输出名，node `ref`不变，新active tag为 `rodiag1-matched-ref-r3`。原始输出是 `refcell_device.plt`，已审计CSV导出名仍为 `reference-device.csv`；物理条件、顺序、阈值不变。'
        revision += ' 各版设计、源码快照、旧输入及历史失败run均保留。'
        lines[2:2] = [revision, '']
    for status in statuses:
        reason = (status['failure_reason'] or status['presentation_error'] or '—').replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| {status['tag']} | {status['state']} | {status['run_id'] or '—'} | {reason} |")
    if history:
        lines += ['', '### 历史尝试（不计入当前有效九工况）', '',
                  '| tag | ledger / 原始manifest状态 | run ID | 原始原因与控制器记录 |', '|---|---|---|---|']
        for row in history:
            reason = '；'.join(value for value in (row.get('raw_error_excerpt'), row.get('failure_reason')) if value)
            reason = (reason or '原因未记录，查看原始归档').replace('|', '\\|').replace('\n', ' ')
            lines.append(f"| {row['tag']} | {row['state']} / {row.get('raw_manifest_state') or '未知'} | {row.get('run_id') or '未登记/无法唯一定位'} | {reason} |")
    if ledger.get('failures'):
        lines += ['', f"ledger的failures列表保留{len(ledger['failures'])}条记录；与runs中的同一历史失败不重复计数。历史失败不转写为成功，也不替代active matched-ref-r3结果。"]
    lines += ['', '## 桥接与参考匹配检查', '']
    bridge = by_tag.get('rodiag1-bridge090')
    if bridge and original.get('baseline'):
        difference = bridge['summary']['D_mV'] - original['baseline']['differential_V'] * 1e3
        tolerance = design['gates']['bridge_D_abs_difference_mV']
        lines += [f"bridge ledger状态为VERIFIED（控制器在该状态前执行冻结桥接门槛）。新旧D差为{difference:+.9f} mV；设计门槛为绝对差≤{tolerance:g} mV。该差值是呈现，不新增验收规则。",
                  f"原基准：`{ORIGINAL_BASE}`；新桥接：`{bridge['summary']['run_id']}`。"]
    else:
        lines += ['桥接结果或原基准导出尚不足，不能宣称桥接完成。']
    if comparisons is None:
        lines += ['', '`comparisons.json`尚不存在：physical/offline最终比较未记录，不宣称匹配检查通过。']
    else:
        lines += ['', f"`comparisons.json`记录的 `passed={comparisons.get('passed')}`；该状态直接沿用控制器记录。",
                  f"离线D={comparisons.get('offline_matched_D_mV')} mV，physical D={comparisons.get('physical_matched_D_mV')} mV，差={comparisons.get('difference_mV')} mV，冻结容差={comparisons.get('tolerance_mV')} mV。",
                  f"新alphaSN无粒子工况与原alpha101读前SN匹配误差={comparisons.get('alpha_read_SN_match_error_mV')} mV；只是标量SN匹配，不代表载流子或场历史相同。"]
    lines += ['', '## 实际数据', '',
              '| tag | SN(3 ns)/V | D(4 ns)/mV | 二电容预测/mV | offset/mV | SN+BL净增/fC | gate积分/fC | body积分/fC |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for item in cases:
        s = item['summary']
        lines.append(f"| {item['case']['tag']} | {s['read_SN_V']:.9f} | {s['D_mV']:.6f} | {s['two_capacitor_D_mV']:.6f} | {s['offset_mV']:.6f} | {s['SN_BL_gain_fC']:.9f} | {s['port_integrals_fC']['gate']['TotalCurrent']:.9f} | {s['port_integrals_fC']['body']['TotalCurrent']:.9f} |")
    lines += ['', '电荷关系沿用audit：`ΔQcap=+∫circuit流入dt≈−∫(Is+Id)dt=∫(Ig+Ib)dt`；device端口电流与circuit节点流入方向相反。二电容预测使用实际3 ns的SN、BL、REF，offset解释同时保留终点SN−BL未等势项与REF漂移。WL-off不能假设已经完成电荷共享。', '',
              'gate TotalCurrent与DisplacementCurrent、eCurrent、hCurrent分别列于CSV；栅位移电流不等于载流子穿越栅氧。端口守恒能量化外部交换，但不能唯一拆分内部重叠电容、沟道形成和耗尽变化的各自贡献。', '',
              '## 原alpha101只读依据（本批冻结前已知）', '']
    if prior:
        lines += [f"原alpha101位1`{ORIGINAL_ALPHA}`：3–4 ns理想电容净增{prior['capgain_fC']:.9f} fC；除以110 fF对应{prior['capgain_div_110fF_mV']:.9f} mV，与该run实际BL相对封闭共享值的偏移{prior['BL_minus_ideal_mV']:.9f} mV对应。",
                  f"gate积分{prior['port_BE_integrals_fC']['gate']['TotalCurrent']:+.9f} fC，body积分{prior['port_BE_integrals_fC']['body']['TotalCurrent']:+.9f} fC。这是原始只读取证结果，不计为D1新增结果。"]
    else:
        lines += ['原inspection证据未读取成功；不使用硬编码数值补成已核验结果。']
    if original.get('alpha'):
        lines += [f"原summary记录D={original['alpha']['differential_V'] * 1e3:.9f} mV、读前SN={original['alpha']['read_precharge_SN_V']:.12f} V。"]
    lines += ['', '[原端口证据](../../local_runtime/dram-readout-offset-diagnostic/inspection/sign-check-and-alpha101-charge.json)；'
              f'[原alpha summary](../dram-see-v2/data/tcad/{ORIGINAL_ALPHA}/summary.json)。', '',
              '## 图件、数据与边界', '',
              '- [SN传递与offset](figures/01-sn-transfer-and-offset.png)',
              '- [WL、gate/body电流与BL−REF读出](figures/02-wl-and-terminal-currents.png)',
              '- [端口积分与电荷闭合](figures/03-port-integrals-and-closure.png)',
              '- [理想、离线与physical参考及原alpha101对照](figures/04-reference-readout-contrasts.png)',
              '- [源汇总CSV](data/summary.csv)；[图件来源与SHA-256](figures/figure-evidence.json)；每图同时保留SVG。', '',
              '所有图均标注DATA PLOT、单位、条件与实际run ID；不是Sentaurus Visual截图。离线参考曲线仅对center BL作线性时间插值以相减，不产生新的求解点。04图中的原alpha101实际曲线和4 ns值属于有粒子、不同历史的只读旧证据，其CSV/summary另有哈希和run ID，不计入本批九项，也不修改原pilot判据。CSV保留未开始、失败和缺失状态。', '',
              '未做：新的空间网格/时间步独立性、真实感放锁存/恢复、噪声和失调分布、实际工艺校准、新粒子能量或位置扫描。原alpha与无粒子标量SN相近不证明内部状态相同。不能由本批推出真实DRAM可靠性、辐射截面或误读概率。', '']
    return '\n'.join(lines)


def main():
    design, ledger, statuses, cases, comparisons, prior, original, sources = collect()
    proof = plots(cases, sources, original)
    # Refuse a changing input snapshot; generation should follow controller exit.
    changed = [path for path, digest in sources.items() if sha(ROOT / path) != digest]
    if changed:
        raise RuntimeError('Presentation inputs changed: ' + ', '.join(changed))
    data = HERE / 'data'
    data.mkdir(exist_ok=True)
    history = original.get('historical_attempts', [])
    rows = rows_for_summary(statuses, cases, history)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (data / 'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (HERE / 'report.md').write_text(render_report(design, ledger, statuses, cases, comparisons, prior, original), encoding='utf-8')
    evidence = {'schema': 'dram-readout-offset-d1-presentation', 'source_files_sha256': sources,
                'actual_ledger_verified': sum(row['state'] == 'VERIFIED' for row in statuses),
                'actual_presented_exports': len(cases), 'frozen_case_count': len(design['cases']),
                'active_design_file': original.get('active_design_file'),
                'historical_attempt_count': len(history), 'historical_attempts': history,
                'comparisons_recorded_passed': comparisons.get('passed') if comparisons else None,
                'independent_particle_events_added': 0, 'probability_estimates': False,
                'figures': proof, 'generated_files_sha256': {
                    relative(data / 'summary.csv'): sha(data / 'summary.csv'),
                    relative(HERE / 'report.md'): sha(HERE / 'report.md')},
                'scope': 'Presentation of existing audit outputs; no solver, reclassification, or new acceptance rules.'}
    (HERE / 'figures/figure-evidence.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'presented': len(cases), 'planned': len(design['cases']), 'figures': len(proof),
                      'report': relative(HERE / 'report.md')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
