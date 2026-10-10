"""Strict, read-only v3 archive and numerical audit; export is explicitly opt-in.

COLLECTED is an engineering state, never a scientific acceptance decision.
No solver calls, archive extraction, legacy exports, or recovered-run exceptions.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
THRESHOLDS_V = (.0025, .005, .010)


def module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # A read-only legacy dependency must not gain __pycache__ as a side effect.
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), module.__dict__)
    return module


# These original functions only parse bytes/numbers. Importing analyze has no
# filesystem writes and does not import the legacy builders or event modules.
_parser = module_from_path('_v3_original_raw_parser', HERE.parent / 'dram-see-v1/analyze.py')
read, parse_plt, integral = _parser.read, _parser.parse_plt, _parser.integral


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def json_hash(value):
    return sha_bytes(json.dumps(value, sort_keys=True).encode())


def classification(margin, epsilon=.005):
    if not math.isfinite(margin) or epsilon not in THRESHOLDS_V:
        raise ValueError('Nonfinite margin or nonregistered threshold')
    return 'correct' if margin > epsilon else 'criterion_logic_flip' if margin < -epsilon else 'critical'


def clean(rows, first=False):
    output = []
    for row in rows:
        if not all(math.isfinite(value) for value in row.values()):
            raise ValueError('Nonfinite raw solver data')
        if output and row['time'] < output[-1]['time']:
            raise ValueError('Time went backwards')
        if output and row['time'] == output[-1]['time']:
            if row['time'] > 0 and any(abs(row[key] - output[-1][key]) > 1e-6
                                      for key in row if key.startswith('v(')):
                raise ValueError('Discontinuous voltage at duplicate timestamp')
            if not first:
                output[-1] = row
        else:
            output.append(row)
    if len(output) < 2:
        raise ValueError('Insufficient transient data')
    return output


def segment(rows, start, end, first=False):
    result = clean([row for row in rows if start - 1e-20 <= row['time'] <= end + 1e-20], first)
    if abs(result[0]['time'] - start) > 1e-18 or abs(result[-1]['time'] - end) > 1e-18:
        raise ValueError('Missing phase endpoints')
    return result


def sample(rows, key, time):
    """Linear interpolation only inside the observed interval; never extrapolate."""
    for row in rows:
        if abs(row['time'] - time) <= 1e-20:
            return row[key]
    return _parser.at(rows, 'time', key, time)


def run_folder(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', run_id):
        raise ValueError('Unsafe or empty run ID')
    return ROOT / 'local_runtime/runs' / run_id


def manifest_checked(run_id):
    folder = run_folder(run_id)
    m = json.loads((folder / 'manifest.json').read_text(encoding='utf8'))
    if m.get('run_id') != run_id or m.get('state') != 'COLLECTED' or m.get('ssh_exit_code') != 0:
        raise ValueError('Run is not successfully COLLECTED: ' + run_id)
    if m.get('ssh_exit_code_scope') or m.get('original_execution_ssh_exit_code', 0) != 0:
        raise ValueError('Recovery exception is not part of the v3 contract')
    if sha(folder / 'results.tar') != m.get('results_sha256'):
        raise ValueError('Result archive hash mismatch')
    if not {'parameters.json', 'geometry.scm', 'device.cmd', 'project.json'} <= set(m.get('input_sha256', {})):
        raise ValueError('Incomplete frozen input manifest')
    with tarfile.open(folder / 'inputs.tar') as archive:
        for name, digest in m['input_sha256'].items():
            if sha_bytes(read(archive, name)) != digest:
                raise ValueError('Frozen input hash mismatch: ' + name)
    return folder, m


def completion_checked(tf, m):
    for name, digest in m['input_sha256'].items():
        if sha_bytes(read(tf, name)) != digest:
            raise ValueError('Archived input differs: ' + name)
    if read(tf, 'exit-code.txt').strip() != b'0':
        raise ValueError('Nonzero remote runner exit')
    if b'ENGINEERING_RUN_COMPLETED' not in read(tf, 'execution.log'):
        raise ValueError('Missing original engineering completion marker')
    log = read(tf, 'transient_des.log').decode(errors='replace')
    if 'Sentaurus Device simulation finished' not in log:
        raise ValueError('Missing solver completion')
    project = json.loads(read(tf, 'project.json'))
    if m.get('steps') != project.get('steps'):
        raise ValueError('Manifest steps differ from archived project')
    for step in m['steps']:
        for output in step['outputs']:
            if not read(tf, output):
                raise ValueError('Empty required output: ' + output)
    return log


MATCH_REQUIRED = {
    'gate_length_um', 'oxide_nm', 'mesh_scale', 'step_scale',
    'capacitance_F', 'bitline_capacitance_F', 'reference_capacitance_F',
    'reference_store_capacitance_F', 'reference_target_voltage_V',
    'prestrike_s', 'strike_s', 'hold_end_s', 'precharge_ramp_end_s',
    'precharge_end_s', 'read_sample_s', 'precharge_V',
    'precharge_resistance_on_ohm', 'precharge_resistance_off_ohm',
    'effective_thickness_um', 'temperature_K', 'geometry_sha256', 'physics',
    'circuit_revision', 'initialization_tolerance_V', 'precharge_tolerance_V',
    'read_threshold_V', 'clamp_release_s', 'wordline_rise_start_s',
    'wordline_rise_end_s', 'wordline_read_V', 'initialization',
}


def matching_key(p):
    """Reject partial matching contracts, even when the omitted values look default."""
    contract = p.get('matching_contract')
    if not isinstance(contract, dict) or not MATCH_REQUIRED <= set(contract):
        raise ValueError('Incomplete matching contract')
    if p.get('matching_contract_sha256') != json_hash(contract):
        raise ValueError('Matching contract hash mismatch')
    for key, value in contract.items():
        if key in p and p[key] != value:
            raise ValueError('Matching contract/parameter mismatch: ' + key)
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError('Nonfinite matching parameter')
    if {'stored_bit', 'target_voltage_V', 'neutral', 'reference_mode'} & set(contract):
        raise ValueError('State-specific fields in common matching contract')
    return contract


def parameters_checked(p, tf):
    if p.get('schema') != 'dram-see-v3':
        raise ValueError('Wrong schema; legacy evidence requires an explicit compatibility bridge')
    key = matching_key(p)
    model = p.get('model_contract')
    if not isinstance(model, dict) or json_hash(model) != p.get('model_contract_sha256'):
        raise ValueError('Missing/invalid model contract')
    if any(p[k] != value for k, value in model.items() if k in p):
        raise ValueError('Model contract/parameter mismatch')
    if sha_bytes(read(tf, 'geometry.scm')) != key['geometry_sha256'] or model.get('geometry_sha256') != key['geometry_sha256']:
        raise ValueError('Geometry contract mismatch')
    if p['gate_length_um'] not in (.18, .25, .35, .45) or p['oxide_nm'] not in (4, 5, 6):
        raise ValueError('Outside registered geometry')
    if p['step_scale'] not in (.5, 1) or p['mesh_scale'] not in (.7, 1):
        raise ValueError('Outside registered numerical settings')
    if p.get('reference_mode') not in ('offline', 'physical') or type(p.get('neutral')) is not bool:
        raise ValueError('Incomplete reference configuration')
    expected = {
        'capacitance_F': 1e-14, 'bitline_capacitance_F': 1e-13,
        'reference_capacitance_F': 1e-13, 'reference_store_capacitance_F': 1e-14,
        'reference_target_voltage_V': .5, 'precharge_V': .5,
        'prestrike_s': .95e-9, 'strike_s': 1e-9, 'hold_end_s': 2.8e-9,
        'precharge_ramp_end_s': 2.9e-9, 'precharge_end_s': 3e-9,
        'read_sample_s': 4e-9, 'initialization_tolerance_V': .001,
        'precharge_tolerance_V': 1e-5, 'read_threshold_V': .005,
    }
    for name, value in expected.items():
        if p.get(name) != value:
            raise ValueError('Frozen parameter differs: ' + name)
    target = .5 if p['neutral'] else .1 if p.get('stored_bit') == 0 else .9
    if (p['neutral'] and p.get('stored_bit') is not None) or (not p['neutral'] and p.get('stored_bit') not in (0, 1)):
        raise ValueError('Invalid original stored bit')
    if p.get('target_voltage_V') != target:
        raise ValueError('Invalid initialization target')
    if p['reference_mode'] == 'physical' and (p.get('parent_run') or p['neutral'] or p.get('reference_instance') != 'refcell'):
        raise ValueError('Physical reference requires complete independent initialization')
    return key


def legacy_parameters(tf, original, run_id):
    """Explicit v2 no-particle/D1 center bridge, bound to actual archived decks.

    This does not change the source parameters or import any old classifications.
    D1 recovered twins and all legacy particle responses are deliberately excluded.
    """
    builder = module_from_path('_v3_builder_for_exact_legacy_contract', HERE / 'build_case.py')
    neutral = original.get('schema') == 'dram-readout-offset-d1'
    if neutral:
        if (run_id != '20261010T073750Z-rodiag1-center050-2fde80ba'
                or original.get('variant') != 'standard' or original.get('sn_target_V') != .5
                or original.get('case', {}).get('tag') != 'rodiag1-center050'):
            raise ValueError('Only the complete D1 center050 neutral curve has a v3 bridge')
        old = original['inherited_v2_parameters']
        base_folder, base_manifest = manifest_checked(original['base_run_id'])
        if base_manifest['results_sha256'] != original['base_results_sha256']:
            raise ValueError('D1 inherited archive changed')
        with tarfile.open(base_folder / 'results.tar') as parent:
            completion_checked(parent, base_manifest)
            if json.loads(read(parent, 'parameters.json')) != old:
                raise ValueError('D1 inherited parameters differ from original archive')
            for name in ('geometry.scm', 'cell_msh.tdr'):
                if read(parent, name) != read(tf, name):
                    raise ValueError('D1 inherited geometry/mesh differs')
        if sha_bytes(read(tf, 'cell_msh.tdr')) != original['frozen_mesh_sha256']:
            raise ValueError('D1 frozen mesh hash mismatch')
    elif original.get('schema') == 'dram-see-v2':
        old = original
    else:
        raise ValueError('Unsupported legacy schema')
    if old.get('schema') != 'dram-see-v2' or old.get('parent_run') or old.get('charge_pc') != 0 or old.get('source_event') or old.get('particle'):
        raise ValueError('Legacy bridge requires full no-particle baseline')
    if old.get('model_contract_sha256') != json_hash(old.get('model_contract')):
        raise ValueError('Legacy model contract hash mismatch')
    if any(old.get(k) != v for k, v in old['model_contract'].items() if k in old):
        raise ValueError('Legacy contract/parameter mismatch')
    geometry = sha_bytes(read(tf, 'geometry.scm'))
    expected = {key: old[key] for key in builder.LEGACY_CONTRACT_KEYS}
    expected.update(geometry_sha256=geometry, physics=builder.PHYSICS, circuit_revision=builder.CIRCUIT)
    if old['model_contract'] != expected:
        raise ValueError('Legacy physical model cannot be exactly mapped')
    target = .5 if neutral else old['target_voltage_V']
    full_deck = builder._single_device(target, old['step_scale'])
    if read(tf, 'device.cmd').decode().replace('\r\n', '\n') != full_deck:
        raise ValueError('Legacy device/circuit/timing differs from exact v3 single-cell template')
    p = dict(old)
    p.update(schema='dram-see-v3', oxide_nm=5., stored_bit=None if neutral else old['stored_bit'],
             neutral=neutral, target_voltage_V=target, reference_mode='offline', reference_instance=None,
             reference_target_voltage_V=.5, reference_store_capacitance_F=1e-14,
             clamp_release_s=.6e-9, wordline_rise_start_s=3.05e-9, wordline_rise_end_s=3.10e-9,
             wordline_read_V=1.8, sensitivity_thresholds_V=[.0025, .005, .01], source_event=None)
    matching = {key: p[key] for key in builder.MATCHING_KEYS}
    matching.update(geometry_sha256=geometry, physics=builder.PHYSICS, circuit_revision=builder.CIRCUIT)
    model = dict(matching, schema='dram-see-v3', stored_bit=p['stored_bit'], target_voltage_V=target,
                 neutral=neutral, reference_mode='offline', reference_instance=None,
                 full_control_deck_sha256=sha_bytes(full_deck.encode()))
    p.update(matching_contract=matching, matching_contract_sha256=json_hash(matching),
             model_contract=model, model_contract_sha256=json_hash(model))
    return p, {'source_schema': original['schema'], 'source_parameters_sha256': sha_bytes(read(tf, 'parameters.json')),
               'policy': 'exact archived single-device deck, geometry, model and full initialization; numerical observables re-audited; legacy classifications not reused',
               'normalization_only': True, 'original_parameters': original}


def device_definitions(deck):
    result = {}
    for match in re.finditer(r'\bDevice\s+(\w+)\s*\{', deck):
        depth = 1
        position = match.end()
        end = position
        while depth and end < len(deck):
            depth += (deck[end] == '{') - (deck[end] == '}')
            end += 1
        if depth or match.group(1) in result:
            raise ValueError('Malformed/duplicate Device definition')
        result[match.group(1)] = deck[position:end - 1]
    return result


def source_checked(tf, p, m, device, refdevice):
    q = p.get('charge_pc')
    if not isinstance(q, (int, float)) or not math.isfinite(q) or q < 0:
        raise ValueError('Invalid event charge')
    particle = bool(p.get('source_event') or p.get('particle'))
    evidence = p.get('source_evidence_sha256', {})
    if bool(evidence) != particle or (q > 0 and not particle):
        raise ValueError('Incomplete source identity, including zero-deposition events')
    if p['neutral'] and (particle or q):
        raise ValueError('Neutral reference cannot be irradiated')
    if particle:
        names = {'source-event.json', 'source-steps.csv', 'source-events.csv'}
        if set(evidence) != names:
            raise ValueError('Incomplete frozen source evidence')
        files = {name: read(tf, name) for name in names}
        for name, data in files.items():
            if sha_bytes(data) != evidence[name] or evidence[name] != m['input_sha256'].get(name):
                raise ValueError('Frozen source hash mismatch: ' + name)
        validator = module_from_path('_v3_source_validator', HERE / 'event_audit.py')
        event = validator.validate_bytes(files['source-event.json'],
            {'steps.csv': files['source-steps.csv'], 'events.csv': files['source-events.csv']},
            {name: p[name] for name in ('gate_length_um', 'particle', 'energy_MeV', 'seed', 'angle_deg')})
        if not math.isclose(event['converted'][0]['charge_pc'], q, rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError('Wrong injected event charge')
        for key, expected in (('track_length_um', event['converted'][0]['track_length_um']),
                              ('let_pc_per_um', event['converted'][0]['let_pc_per_um'])):
            if not math.isclose(p.get(key, math.nan), expected, rel_tol=1e-12, abs_tol=1e-15):
                raise ValueError('Source transport/TCAD geometry mismatch: ' + key)
        if p.get('direction') != event['direction'] or p.get('impact_x_um') != event['surface_impact_um'][0]:
            raise ValueError('Source direction/impact differs')
        contract = p.get('source_integral_contract', {})
        if (p.get('source_normalization_factor') != 1 or contract.get('target_charge_pc') != q
                or contract.get('relative_tolerance') != .05 or contract.get('target_modified_for_truncation') is not False):
            raise ValueError('Source charge must not be renormalized for Gaussian clipping')
    deck = read(tf, 'device.cmd').decode()
    builder = module_from_path('_v3_builder_for_actual_deck', HERE / 'build_case.py')
    renderer = builder._physical_device if p['reference_mode'] == 'physical' else builder._single_device
    ion = rad = cur = ''
    if q:
        ion = (f"HeavyIon ( StartPoint=({p['impact_x_um']},0) "
               f"Direction=({p['direction'][0]},{p['direction'][1]}) Time=1e-9 Length={p['track_length_um']} "
               f"Wt_hi=0.03 LET_f={p['let_pc_per_um']} Gaussian PicoCoulomb )")
        rad = 'HeavyIonChargeDensity HeavyIonGeneration'
        cur = 'CurrentPlot { HeavyIonGeneration(Integrate(Semiconductor)) }'
    expected_deck = renderer(p['target_voltage_V'], p['step_scale'], ion, rad, cur)
    if p.get('parent_run'):
        prefix = expected_deck[:expected_deck.index('Solve {')]
        prefix = prefix.replace(f" Set(sn={p['target_voltage_V']} bl=0 ref=0.5)\n", '')
        tail = expected_deck[expected_deck.index(' Transient(InitialTime=0.95e-9'):]
        expected_deck = prefix + 'Solve {\n Load(FilePrefix="charged")\n Set(bl=0 ref=0.5)\n Plot(FilePrefix="prestrike")\n' + tail
    if deck.replace('\r\n', '\n') != expected_deck:
        raise ValueError('Archived Device/source/circuit/timing differs from declared v3 contract')
    if p['model_contract'].get('full_control_deck_sha256') != sha_bytes(renderer(p['target_voltage_V'], p['step_scale']).encode()):
        raise ValueError('Declared full-control deck hash differs')
    definitions = device_definitions(deck)
    instance = re.search(r'\b(\w+)\s+access\s*\(', deck)
    if not instance or instance[1] not in definitions:
        raise ValueError('No signal Device instance')
    signal_type = instance[1]
    signal_sources = len(re.findall(r'\bHeavyIon\s*\(', definitions[signal_type]))
    if signal_sources != int(q > 0) or len(re.findall(r'\bHeavyIon\s*\(', deck)) != signal_sources:
        raise ValueError('Unexpected HeavyIon source scope/count')
    reference_zero = None
    if p['reference_mode'] == 'physical':
        instance = re.search(r'\b(\w+)\s+refcell\s*\(', deck)
        if not instance or instance[1] == signal_type or instance[1] not in definitions:
            raise ValueError('Reference must have a separate Device definition')
        if re.search(r'\bHeavyIon\s*\(', definitions[instance[1]]):
            raise ValueError('Particle source leaked into reference')
        reference_zero = True
    source_names = [name for name in device[0] if 'HeavyIonGeneration' in name]
    if q > 0 and len(source_names) != 1:
        raise ValueError('Missing unique source-generation integral')
    generated = integral(device, 'time', source_names[0]) * 1e-12 * 1.602176634e-19 if source_names else 0.
    if any(row[name] < 0 for name in source_names for row in device):
        raise ValueError('Negative HeavyIon generation')
    error = abs(generated - q * 1e-12) / (q * 1e-12) if q else None
    if q > 0 and error > .05:
        raise ValueError('Source integral exceeds 5%: ' + str(error))
    if q == 0 and any(row[name] != 0 for name in source_names for row in device):
        raise ValueError('Nonzero generation in unirradiated/zero-deposition signal')
    if refdevice is not None:
        reference_names = [name for name in refdevice[0] if 'HeavyIonGeneration' in name]
        if len(reference_names) > 1 or any(row[name] < 0 for name in reference_names for row in refdevice):
            raise ValueError('Ambiguous/negative reference generation')
        reference_charge_fC = (integral(refdevice, 'time', reference_names[0]) * 1e-12 * 1.602176634e-19 * 1e15
                               if reference_names else 0.)
        if reference_charge_fC > 1e-12:
            raise ValueError('Nonzero reference generation exceeds 1e-12 fC')
        # When no generation dataset exists, the independently defined source-
        # free reference Physics is the structural zero-source evidence.
        reference_zero = {'verified': True, 'definition_source_count': 0,
                          'generation_datasets': reference_names,
                          'generated_fC': reference_charge_fC, 'tolerance_fC': 1e-12,
                          'evidence': 'raw zero generation plus source-free Device' if reference_names else 'source-free independent Device; no generation dataset'}
    return {'particle_event': particle, 'target_fC': q * 1e3,
            'generated_fC': generated * 1e15, 'relative_error': error,
            'reference_source_zero': reference_zero}


def conservation(raw, devices, p):
    phases = {'hold': segment(raw, .95e-9, 2.8e-9, True),
              'precharge': segment(raw, 2.8e-9, 3e-9, True),
              'read': segment(raw, 3e-9, 4e-9)}
    nodes = [('sn', p['capacitance_F'], ['i(access,sn)', 'i(rsn,sn)'], 'i(cstore,sn)'),
             ('bl', p['bitline_capacitance_F'], ['i(access,bl)', 'i(rbl,bl)', 'i(rpre,bl)'], 'i(cbl,bl)')]
    physical = p['reference_mode'] == 'physical'
    if physical:
        nodes += [('snr', p['reference_store_capacitance_F'], ['i(refcell,snr)', 'i(rsnr,snr)'], 'i(cstoreref,snr)'),
                  ('ref', p['reference_capacitance_F'], ['i(refcell,ref)', 'i(rref,ref)', 'i(rpreref,ref)'], 'i(cref,ref)')]
    else:
        nodes += [('ref', p['reference_capacitance_F'], ['i(rref,ref)'], 'i(cref,ref)')]
    balances, kcl, ports, closure = {}, {}, {}, {}
    for phase, rows in phases.items():
        for node, cap, terms, capkey in nodes:
            if phase == 'hold' and node not in ('sn', 'snr'):
                continue
            if phase == 'precharge' and node == 'ref' and not physical:
                continue
            values = [[row[key] for key in terms + [capkey]] for row in rows[1:]]
            if any(abs(sum(current)) > 1e-12 + .001 * sum(map(abs, current)) for current in values):
                raise ValueError('Local KCL mismatch: ' + phase + '_' + node)
            kcl[phase + '_' + node] = max(abs(sum(current)) for current in values)
            gain = cap * (rows[-1]['v(' + node + ')'] - rows[0]['v(' + node + ')']) * 1e15
            inflow = sum(integral(rows, 'time', key, right=True) for key in terms) * 1e15
            residual = abs(gain - inflow)
            if residual > max(.001, .001 * abs(gain)):
                raise ValueError('BE charge mismatch: ' + phase + '_' + node)
            balances[phase + '_' + node] = {'capacitor_gain_fC': gain, 'terminal_inflow_fC': inflow, 'residual_fC': residual}
    for instance, device in devices.items():
        rows = segment(device, 3e-9, 4e-9)
        circuit = phases['read']
        if len(rows) != len(circuit) or any(abs(a['time'] - b['time']) > 1e-20 for a, b in zip(rows, circuit)):
            raise ValueError('Device/circuit time-grid mismatch: ' + instance)
        mappings = [('source', 'bl'), ('drain', 'sn')] if instance == 'access' else [('source', 'ref'), ('drain', 'snr')]
        for row, c in zip(rows[1:], circuit[1:]):
            total = [row[port + ' TotalCurrent'] for port in ('source', 'drain', 'gate', 'body')]
            if abs(sum(total)) > 1e-12 + .001 * sum(map(abs, total)):
                raise ValueError('Four-terminal KCL: ' + instance)
            for port in ('source', 'drain', 'gate', 'body'):
                current = row[port + ' TotalCurrent']
                components = sum(row[port + ' ' + name] for name in ('eCurrent', 'hCurrent', 'DisplacementCurrent'))
                if abs(current - components) > 1e-12 + .001 * abs(current):
                    raise ValueError('Current-component closure: ' + instance + '_' + port)
            for port, node in mappings:
                value = row[port + ' TotalCurrent']
                if abs(value + c['i(' + instance + ',' + node + ')']) > 1e-12 + .001 * abs(value):
                    raise ValueError('Device/circuit port sign: ' + instance)
        ports[instance] = {port: {name: integral(rows, 'time', port + ' ' + name, right=True) * 1e15
                                  for name in ('TotalCurrent', 'eCurrent', 'hCurrent', 'DisplacementCurrent')}
                           for port in ('source', 'drain', 'gate', 'body')}
        gain = sum(balances['read_' + node]['capacitor_gain_fC'] for _, node in mappings)
        source_drain = -sum(ports[instance][port]['TotalCurrent'] for port in ('source', 'drain'))
        gate_body = sum(ports[instance][port]['TotalCurrent'] for port in ('gate', 'body'))
        residual = max(abs(gain - source_drain), abs(gate_body - source_drain))
        if residual > max(.002, .001 * abs(gain)):
            raise ValueError('Four-terminal integrated closure: ' + instance)
        closure[instance] = {'capacitor_gain_fC': gain, 'source_drain_inflow_fC': source_drain,
                             'gate_body_inflow_fC': gate_body, 'residual_fC': residual}
    return phases, balances, kcl, ports, closure


def restart_checked(tf, p):
    parent_id = p.get('parent_run')
    if not parent_id:
        return None
    if p['reference_mode'] != 'offline' or p['neutral']:
        raise ValueError('Restart prohibited for physical/neutral reference')
    lineage = json.loads(read(tf, 'restart-provenance.json'))
    folder, manifest = manifest_checked(parent_id)
    if lineage.get('parent_run') != parent_id or lineage.get('time_s') != .95e-9 or lineage.get('archive_sha256') != manifest['results_sha256']:
        raise ValueError('Restart provenance identity/hash/time differs')
    copied = lineage.get('copied_sha256', {})
    if set(copied) != {'cell_msh.tdr', 'charged_access_des.sav', 'charged_circuit_des.sav'}:
        raise ValueError('Restart requires mesh and both saved states')
    with tarfile.open(folder / 'results.tar') as parent:
        completion_checked(parent, manifest)
        old = json.loads(read(parent, 'parameters.json'))
        if old.get('schema') not in ('dram-see-v2', 'dram-see-v3') or old.get('parent_run') or old.get('charge_pc') or old.get('source_event'):
            raise ValueError('Parent must be a complete unirradiated compatible control')
        for key in ('gate_length_um', 'stored_bit', 'target_voltage_V', 'mesh_scale', 'step_scale',
                    'capacitance_F', 'bitline_capacitance_F', 'reference_capacitance_F',
                    'prestrike_s', 'strike_s', 'hold_end_s', 'precharge_end_s', 'read_sample_s'):
            if old.get(key) != p.get(key):
                raise ValueError('Restart parameter mismatch: ' + key)
        if old['schema'] == 'dram-see-v3':
            if matching_key(old) != matching_key(p) or old['model_contract_sha256'] != p['model_contract_sha256']:
                raise ValueError('Parent v3 model contract mismatch')
        elif p['oxide_nm'] != 5 or old.get('model_contract', {}).get('geometry_sha256') != p['matching_contract']['geometry_sha256']:
            raise ValueError('Legacy parent only supports exact original 5 nm geometry')
        builder = module_from_path('_v3_builder_for_restart_contract', HERE / 'build_case.py')
        full_control = builder._single_device(p['target_voltage_V'], p['step_scale'])
        if read(parent, 'device.cmd').decode().replace('\r\n', '\n') != full_control:
            raise ValueError('Restart parent actual control deck differs')
        if lineage.get('actual_full_control_deck_sha256') != sha_bytes(full_control.encode()):
            raise ValueError('Restart full-control provenance hash differs')
        if (lineage.get('parent_schema') != old['schema']
                or lineage.get('parent_model_contract_sha256') != old.get('model_contract_sha256')
                or lineage.get('parent_input_sha256') != manifest['input_sha256']):
            raise ValueError('Restart parent metadata provenance differs')
        if old['schema'] == 'dram-see-v2':
            mapped, _ = legacy_parameters(parent, old, parent_id)
            if mapped['model_contract'] != p['model_contract']:
                raise ValueError('Legacy parent complete mapped model differs')
        if sha_bytes(read(parent, 'geometry.scm')) != sha_bytes(read(tf, 'geometry.scm')):
            raise ValueError('Restart geometry mismatch')
        for name, digest in copied.items():
            if sha_bytes(read(parent, name)) != digest or sha_bytes(read(tf, name)) != digest:
                raise ValueError('Copied restart state hash mismatch')
    parent_audit = audit(parent_id, export=False)
    return {'parent_run': parent_id, 'archive_sha256': manifest['results_sha256'],
            'parent_audit_status': parent_audit['audit_status'], 'copied_sha256': copied}


def audit(run_id, export=False):
    folder, manifest = manifest_checked(run_id)
    with tarfile.open(folder / 'results.tar') as archive:
        log = completion_checked(archive, manifest)
        p = json.loads(read(archive, 'parameters.json'))
        bridge = None
        if p.get('schema') != 'dram-see-v3':
            p, bridge = legacy_parameters(archive, p, run_id)
        parameters_checked(p, archive)
        _, raw = parse_plt(read(archive, 'circuit.plt').decode())
        circuit = clean(raw)
        _, access_raw = parse_plt(read(archive, 'access_device.plt').decode())
        devices = {'access': clean(access_raw)}
        if p['reference_mode'] == 'physical':
            _, ref_raw = parse_plt(read(archive, 'refcell_device.plt').decode())
            devices['refcell'] = clean(ref_raw)
        for rows in (circuit, *devices.values()):
            if abs(rows[-1]['time'] - 4e-9) > 1e-18:
                raise ValueError('Solver did not reach 4 ns')
        phases, balances, kcl, ports, closure = conservation(raw, devices, p)
        hold, precharge = phases['hold'], phases['precharge']
        if abs(hold[0]['v(sn)'] - p['target_voltage_V']) > .001:
            raise ValueError('Initial SN target error exceeds 1 mV')
        if any(max(abs(row['v(wl)']), abs(row['v(bl)'])) > 1e-8 for row in hold[:-1]):
            raise ValueError('Hold waveform differs')
        if abs(precharge[-1]['v(bl)'] - .5) > 1e-5 or abs(precharge[-1]['v(ref)'] - .5) > 1e-5:
            raise ValueError('Precharge error exceeds 10 uV')
        for row in circuit:
            expected_wl = 1.8 * min(1, max(0, (row['time'] - 3.05e-9) / .05e-9))
            if abs(row['v(wl)'] - expected_wl) > 1e-7:
                raise ValueError('Read wordline waveform differs')
        if 'refcell' in devices:
            if abs(hold[0]['v(snr)'] - .5) > .001 or any(abs(row['v(ref)']) > 1e-8 for row in hold[:-1]):
                raise ValueError('Physical reference initialization/hold differs')
        radiation = source_checked(archive, p, manifest, devices['access'], devices.get('refcell'))
        lineage = restart_checked(archive, p)
        tdr_names = ['cell_msh.tdr', 'prestrike_access_des.tdr', 'strike_access_des.tdr', 'hold_access_des.tdr', 'final_access_des.tdr']
        if 'refcell' in devices:
            tdr_names.append('final_refcell_des.tdr')
        tdr_hashes = {name: sha_bytes(read(archive, name)) for name in tdr_names}
        wall = re.search(r'wallclock:\s*([\d.]+) s', log)
        if not wall or not math.isfinite(float(wall[1])) or float(wall[1]) <= 0:
            raise ValueError('Missing/invalid solver wallclock')
        result = {'schema': 'dram-see-v3-audit', 'run_id': run_id,
                  'archive_sha256': manifest['results_sha256'], 'input_sha256': manifest['input_sha256'],
                  'parameters': p, 'engineering_state': 'COLLECTED',
                  'audit_status': 'NUMERICAL_CONTRACT_PASSED',
                  'response_validity': 'pending_matching_reference_and_numerical_sensitivity',
                  'final_time_s': circuit[-1]['time'], 'wallclock_s': float(wall[1]),
                  'solver_s': float(wall[1]), 'legacy_bridge': bridge,
                  'curve_loader': 'audit.load_curves(run_id); rechecks original archive; no legacy exports',
                  'initial_SN_V': hold[0]['v(sn)'], 'initial_error_V': hold[0]['v(sn)'] - p['target_voltage_V'],
                  'hold_end_SN_V': hold[-1]['v(sn)'], 'final_SN_V': circuit[-1]['v(sn)'],
                  'final_BL_V': circuit[-1]['v(bl)'], 'final_REF_V': circuit[-1]['v(ref)'],
                  'max_kcl_A': kcl, 'BE_charge_checks': balances, 'port_integrals_fC': ports,
                  'four_terminal_closure': closure, 'radiation': radiation, 'restart': lineage,
                  'tdr_sha256': tdr_hashes, 'mesh_sha256': tdr_hashes['cell_msh.tdr'],
                  'tdr_field_inspection': 'pending native TDR/Visual field inspection',
                  'newton_retries': log.count("Newton didn't converge"),
                  'boundary_current_reprints': 'first incoming endpoint for hold/precharge; last outgoing endpoint for read; phase-start KCL excluded',
                  'scope': 'Raw archive and registered numerical contracts; no latch/restore, calibrated upset probability, or automatic scientific validity'}
    if export:
        destination = HERE / 'data/tcad' / run_id
        destination.mkdir(parents=True, exist_ok=True)
        for name, rows in [('circuit.csv', circuit), ('circuit-raw.csv', raw), ('device.csv', devices['access'])]:
            csvout(destination / name, rows)
        if 'refcell' in devices:
            csvout(destination / 'reference-device.csv', devices['refcell'])
        (destination / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    return result


def csvout(path, rows):
    with Path(path).open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_curves(run_id):
    """Audited curve bundle for metrics; every call verifies original archive bytes."""
    summary = audit(run_id, export=False)
    with tarfile.open(run_folder(run_id) / 'results.tar') as archive:
        _, raw = parse_plt(read(archive, 'circuit.plt').decode())
    return {'summary': summary, 'parameters': summary['parameters'], 'circuit': clean(raw)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.run_id, args.export), indent=2))
