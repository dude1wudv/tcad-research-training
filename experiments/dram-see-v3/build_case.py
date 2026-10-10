"""Immutable v3 inputs; validated v1 geometry, v2 timing, isolated reference devices.

This module only prepares inputs. It never starts a runner or modifies old inputs.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V1 = HERE.parent / 'dram-see-v1' / 'build_case.py'
V2 = HERE.parent / 'dram-see-v2' / 'build_case.py'
PHYSICS = 'Fermi OldSlotboom Mobility(DopingDep HighFieldSaturation Enormal) SRH(DopingDep) Auger; Digits5 ErrRef1e7; BE Blocked ParDiSo; gate_work_function4.6'
CIRCUIT = 'v2-finite-ramp-rpre100-off1e20-wl0-initialize-read3.05to3.10ns-1.8V-snclamp-release0.6ns'


def _single_device(target, step, ion='', rad='', cur=''):
    # Verbatim v2 template. Archive comparison below protects legacy restarts.
    return f'''Device Cell {{
 File {{ Grid="cell_msh.tdr" Current="device.plt" Plot="device.tdr" }}
 Electrode {{ {{Name="source" Voltage=0}} {{Name="drain" Voltage=0}} {{Name="gate" Voltage=0 WorkFunction=4.6}} {{Name="body" Voltage=0}} }}
 Physics {{ AreaFactor=1 Temperature=300 Fermi EffectiveIntrinsicDensity(OldSlotboom)
 Mobility(DopingDep HighFieldSaturation Enormal) Recombination(SRH(DopingDep) Auger) {ion} }}
}}
File {{ Output="transient" }}
Plot {{ eDensity hDensity Potential ElectricField/Vector Doping TotalCurrent/Vector eCurrent/Vector hCurrent/Vector {rad} }}
{cur}
Math {{ RelErrControl Digits=5 ErrRef(electron)=1e7 ErrRef(hole)=1e7 Iterations=30 Notdamped=100
 Transient=BE Method=Blocked SubMethod=ParDiSo ExitOnFailure }}
System {{
 Cell access ("source"=bl "drain"=sn "gate"=wl "body"=0)
 Vsource_pset vwl (wl 0) {{pwl=(0 0 3.05e-9 0 3.10e-9 1.8 4e-9 1.8)}}
 Vsource_pset vpre (pre 0) {{pwl=(0 0 2.8e-9 0 2.9e-9 0.5 4e-9 0.5)}}
 Resistor_pset rpre (bl pre) {{resistance=100}}
 Capacitor_pset cstore (sn 0) {{capacitance=1e-14}}
 Capacitor_pset cbl (bl 0) {{capacitance=1e-13}}
 Capacitor_pset cref (ref 0) {{capacitance=1e-13}}
 Resistor_pset rsn (sn 0) {{resistance=1e20}}
 Resistor_pset rbl (bl 0) {{resistance=1e20}}
 Resistor_pset rref (ref 0) {{resistance=1e20}}
 Set(sn={target} bl=0 ref=0.5)
 Plot "circuit.plt" (time() v(bl) v(wl) v(sn) v(ref) i(access,sn) i(access,bl)
 i(cstore,sn) i(cbl,bl) i(cref,ref) i(rsn,sn) i(rbl,bl) i(rref,ref) i(rpre,bl))
}}
Solve {{
 Coupled(Iterations=100) {{Poisson}}
 Coupled(Iterations=100) {{Poisson Electron Hole Contact Circuit}}
 Transient(InitialTime=0 FinalTime=0.6e-9 InitialStep=1e-14 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{Coupled {{Poisson Electron Hole Contact Circuit}}}}
 Unset(sn)
 Transient(InitialTime=0.6e-9 FinalTime=0.95e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}}
 Plot(FilePrefix="prestrike" Time=(0.95e-9)) Save(FilePrefix="charged" Time=(0.95e-9))
 }}
 Transient(InitialTime=0.95e-9 FinalTime=1.05e-9 InitialStep={2e-13*step} MinStep=1e-18 MaxStep={1e-12*step} Increment=1.3) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="strike" Time=(1e-9))
 }}
 Transient(InitialTime=1.05e-9 FinalTime=2.8e-9 InitialStep={1e-12*step} MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="hold" Time=(2.8e-9))
 }}
 Unset(bl)
 Transient(InitialTime=2.8e-9 FinalTime=3e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-12*step} Increment=1.4) {{Coupled {{Poisson Electron Hole Contact Circuit}}}}
 Set(rpre."resistance"=1e20)
 Unset(ref)
 Transient(InitialTime=3e-9 FinalTime=4e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="final" Time=(4e-9))
 }}
}}
'''


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json_sha(value):
    # Keep the serialization used by v2 so inherited contract hashes can be checked.
    return _sha(json.dumps(value, sort_keys=True).encode())


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Source execution avoids writing __pycache__ into legacy experiment trees.
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def _replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Ambiguous inherited template token: ' + before)
    return text.replace(before, after)


def _geometry(length, mesh, oxide_nm, workdir):
    """Invoke only v1's no-event generation in an isolated, disposable directory."""
    with tempfile.TemporaryDirectory(prefix='.v3-build-', dir=workdir) as temp:
        legacy = Path(temp) / 'geometry-only'
        _module(V1, '_dram_v3_v1_geometry').build(legacy, length=length, mesh=mesh)
        raw = (legacy / 'geometry.scm').read_bytes()
    # Preserve the established 5 nm grid byte-for-byte for strict baseline reuse.
    if oxide_nm == 5:
        return raw
    text = raw.decode().replace('\r\n', '\n')
    top = -oxide_nm / 1000
    if text.count('-0.005') != 3:
        raise ValueError('Unexpected v1 oxide boundary/contact/window template')
    text = text.replace('-0.005', str(top))
    text = _replace_once(
        text, f'"Silicon" "Oxide" {0.002 * mesh} 1.5',
        f'"Silicon" "Oxide" {0.002 * mesh * oxide_nm / 5} 1.5')
    # The oxide-specific vertical limit follows thickness; lateral geometry and
    # all silicon refinements remain the inherited ones.
    oxide_grid = f'''(sdedr:define-refeval-window "Oxide" "Rectangle" (position 0.3 {top} 0) (position {length + .3} 0 0))
(sdedr:define-refinement-size "Mesh.Oxide" {0.012 * mesh} {oxide_nm / 1000 * .4 * mesh} {0.002 * mesh} {oxide_nm / 1000 * .2 * mesh})
(sdedr:define-refinement-placement "Oxide.Place" "Mesh.Oxide" "Oxide")
'''
    text = _replace_once(text, '(sde:build-mesh "snmesh" "" "cell")',
                         oxide_grid + '(sde:build-mesh "snmesh" "" "cell")')
    return text.encode()


def _physical_device(target, step, ion='', rad='', cur=''):
    """Separate Device definitions are essential: only SignalCell contains ion."""
    deck = _single_device(target, step, ion, rad, cur)
    device_end = deck.index('\nFile { Output=')
    signal = deck[:device_end].replace('Device Cell {', 'Device SignalCell {', 1)
    reference = _single_device(.5, step).split('\nFile { Output=', 1)[0]
    reference = reference.replace('Device Cell {', 'Device ReferenceCell {', 1)
    deck = signal + '\n' + reference + deck[device_end:]
    deck = _replace_once(deck, ' Cell access ', ' SignalCell access ')
    deck = _replace_once(deck, ' Vsource_pset vwl', ''' ReferenceCell refcell ("source"=ref "drain"=snr "gate"=wl "body"=0)
 Capacitor_pset cstoreref (snr 0) {capacitance=1e-14}
 Resistor_pset rsnr (snr 0) {resistance=1e20}
 Resistor_pset rpreref (ref pre) {resistance=100}
 Vsource_pset vwl''')
    deck = _replace_once(deck, f'Set(sn={target} bl=0 ref=0.5)',
                         f'Set(sn={target} bl=0 ref=0 snr=0.5)')
    deck = _replace_once(deck, ' Unset(sn)', ' Unset(sn)\n Unset(snr)')
    deck = _replace_once(deck, ' Unset(bl)', ' Unset(bl)\n Unset(ref)')
    deck = _replace_once(deck, ' Set(rpre."resistance"=1e20)\n Unset(ref)',
                         ' Set(rpre."resistance"=1e20)\n Set(rpreref."resistance"=1e20)')
    deck = _replace_once(deck, 'i(rpre,bl))',
                         'i(rpre,bl) v(snr) i(refcell,snr) i(refcell,ref) '
                         'i(cstoreref,snr) i(rsnr,snr) i(rpreref,ref))')
    return deck


# Matching intentionally ignores stored bit, target, and the implementation of
# the reference. It binds the physical/readout conditions of a signal and its
# separately simulated neutral cell. Full model_contract adds those identities.
MATCHING_KEYS = (
    'gate_length_um', 'oxide_nm', 'mesh_scale', 'step_scale',
    'initialization_tolerance_V', 'capacitance_F', 'bitline_capacitance_F',
    'reference_capacitance_F', 'reference_store_capacitance_F',
    'reference_target_voltage_V', 'precharge_V', 'read_threshold_V',
    'precharge_resistance_on_ohm', 'precharge_resistance_off_ohm',
    'precharge_ramp_end_s', 'precharge_tolerance_V', 'prestrike_s', 'strike_s',
    'hold_end_s', 'precharge_end_s', 'read_sample_s', 'clamp_release_s',
    'wordline_rise_start_s', 'wordline_rise_end_s', 'wordline_read_V',
    'effective_thickness_um', 'temperature_K', 'initialization',
)
LEGACY_CONTRACT_KEYS = (
    'schema', 'gate_length_um', 'stored_bit', 'target_voltage_V',
    'initialization_tolerance_V', 'capacitance_F', 'bitline_capacitance_F',
    'reference_capacitance_F', 'precharge_V', 'read_threshold_V',
    'precharge_resistance_on_ohm', 'precharge_resistance_off_ohm',
    'precharge_ramp_end_s', 'precharge_tolerance_V', 'mesh_scale', 'step_scale',
    'prestrike_s', 'strike_s', 'hold_end_s', 'precharge_end_s', 'read_sample_s',
    'effective_thickness_um', 'temperature_K', 'initialization',
)


def _read(tf, name):
    members = [m for m in tf.getmembers()
               if m.isfile() and m.name.removeprefix('./') == name]
    if len(members) != 1:
        raise ValueError('Missing or ambiguous archive member: ' + name)
    return tf.extractfile(members[0]).read()


def _gaussian_geometry_diagnostic(length, angle, track, radius=.03):
    """A priori transverse-kernel estimate only; never an injected-Q correction."""
    a = math.radians(angle)
    sa, ca, impact, width = math.sin(a), math.cos(a), length + .45, length + .6
    def fraction(s):
        x, y = impact - s * sa, s * ca
        lo, hi = -x / ca, (width - x) / ca
        if sa:
            lo, hi = max(lo, -y / sa), min(hi, (1.2 - y) / sa)
        return max(0., .5 * (math.erf(hi / radius) - math.erf(lo / radius)))
    n = 4096
    h = track / n
    weighted = fraction(0) + fraction(track)
    weighted += sum((4 if i % 2 else 2) * fraction(i * h) for i in range(1, n))
    return {
        'estimated_fraction': weighted / (3 * n),
        'method': 'composite Simpson, 4096 intervals over fixed finite centerline',
        'assumed_kernel': 'exp(-(u/W)^2)/(sqrt(pi)*W), W=0.03 um; transverse only',
        'assumed_support': '0<=s<=track; clip x,y to silicon rectangle; no longitudinal tails',
        'status': 'diagnostic assumption, not independently verified Sentaurus kernel semantics',
        'affects_let_or_target': False,
    }


def _parent_inputs(parent, p, geometry, full_control_deck):
    """Strict state transfer, including legacy schema mapping and actual inputs."""
    if not isinstance(parent, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', parent):
        raise ValueError('Unsafe parent run ID')
    folder = ROOT / 'local_runtime' / 'runs' / parent
    m = json.loads((folder / 'manifest.json').read_text())
    if m.get('state') != 'COLLECTED' or m.get('ssh_exit_code') != 0:
        raise ValueError('Parent requires normal successful collection; no evidence exceptions')
    archive = (folder / 'results.tar').read_bytes()
    if _sha(archive) != m.get('results_sha256'):
        raise ValueError('Parent archive hash mismatch')
    input_hashes = m.get('input_sha256', {})
    if not {'parameters.json', 'geometry.scm', 'device.cmd'} <= set(input_hashes):
        raise ValueError('Incomplete parent frozen-input index')
    with tarfile.open(folder / 'inputs.tar') as inputs, tarfile.open(folder / 'results.tar') as result:
        for name, digest in input_hashes.items():
            if _sha(_read(inputs, name)) != digest or _sha(_read(result, name)) != digest:
                raise ValueError('Parent frozen input mismatch: ' + name)
        if _read(result, 'exit-code.txt').strip() != b'0':
            raise ValueError('Parent remote failure')
        if b'ENGINEERING_RUN_COMPLETED' not in _read(result, 'execution.log'):
            raise ValueError('Parent engineering completion missing')
        if b'Sentaurus Device simulation finished' not in _read(result, 'transient_des.log'):
            raise ValueError('Parent solver completion missing')
        old = json.loads(_read(result, 'parameters.json'))
        if old.get('parent_run') or old.get('charge_pc') != 0 or old.get('source_event'):
            raise ValueError('Parent must be a full, unirradiated baseline')
        if old.get('model_contract_sha256') != _json_sha(old.get('model_contract')):
            raise ValueError('Parent model contract hash mismatch')
        if any(old.get(k) != v for k, v in old['model_contract'].items() if k in old):
            raise ValueError('Parent parameters disagree with frozen contract')
        actual_geometry = _read(result, 'geometry.scm')
        if actual_geometry != geometry or old['model_contract'].get('geometry_sha256') != _sha(geometry):
            raise ValueError('Parent actual geometry/grid specification mismatch')
        old_deck = _read(result, 'device.cmd').decode().replace('\r\n', '\n')
        if old_deck != full_control_deck:
            raise ValueError('Parent actual full device/circuit/initialization/timing deck differs')
        if old.get('schema') == 'dram-see-v2':
            if p['oxide_nm'] != 5 or p['neutral'] or p['reference_mode'] != 'offline':
                raise ValueError('Legacy parent supports only the original 5 nm signal cell')
            expected = {k: p[k] for k in LEGACY_CONTRACT_KEYS}
            expected.update(schema='dram-see-v2', geometry_sha256=_sha(geometry),
                            physics=PHYSICS, circuit_revision=CIRCUIT)
            if old['model_contract'] != expected:
                raise ValueError('Legacy parent actual model contract mismatch')
            for k in ('temperature_K', 'effective_thickness_um', 'angle_deg'):
                if old.get(k) != (0 if k == 'angle_deg' else p[k]):
                    raise ValueError('Legacy parent condition mismatch: ' + k)
            mapping = 'v2 physical inputs exactly reproduced; schema identity is not required'
        elif old.get('schema') == 'dram-see-v3':
            if old.get('model_contract') != p['model_contract']:
                raise ValueError('v3 parent complete model contract mismatch')
            mapping = 'v3 complete model contract and actual inputs identical'
        else:
            raise ValueError('Unsupported parent schema')
        copied = {name: _read(result, name) for name in
                  ('cell_msh.tdr', 'charged_access_des.sav', 'charged_circuit_des.sav')}
        if any(not content for content in copied.values()):
            raise ValueError('Empty parent mesh/save state')
    provenance = {
        'parent_run': parent, 'archive_sha256': m['results_sha256'],
        'time_s': p['prestrike_s'], 'parent_schema': old['schema'],
        'parent_model_contract_sha256': old['model_contract_sha256'],
        'matching_policy': mapping, 'actual_full_control_deck_sha256': _sha(full_control_deck.encode()),
        'parent_input_sha256': input_hashes,
        'copied_sha256': {name: _sha(data) for name, data in copied.items()},
    }
    return copied, provenance


def build(out, length=.25, bit=1, event=None, parent=None, step=1., mesh=1.,
          oxide_nm=5., reference='offline', neutral=False):
    """Build once under v3 paths; event is an immutable v3 event.json path.

    neutral=True builds the single-device SN=0.5 V neutral curve. physical
    always initializes both distinct devices from DC; it never accepts parent.
    """
    out = Path(out).resolve()
    allowed = (HERE, ROOT / 'local_runtime' / 'dram-see-v3')
    if not any(out.is_relative_to(base) and out != base for base in allowed):
        raise ValueError('Inputs must be placed in a v3-only directory')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', out.name):
        raise ValueError('Unsafe runner project name')
    if out.exists():
        raise ValueError('Immutable input already exists')
    if (length not in (.18, .25, .35, .45) or isinstance(bit, bool) or bit not in (0, 1)
            or step not in (1., .5) or mesh not in (1., .7)
            or oxide_nm not in (4., 5., 6.) or reference not in ('offline', 'physical')
            or not isinstance(neutral, bool)):
        raise ValueError('Outside frozen v3 conditions')
    if oxide_nm != 5 and length != .25:
        raise ValueError('Oxide extension is frozen at L=0.25 um')
    if neutral and (event is not None or reference != 'offline' or parent is not None):
        raise ValueError('Neutral reference requires full single-cell no-particle initialization')
    if parent is not None and reference == 'physical':
        raise ValueError('Physical reference requires full initialization of both devices')
    length, step, mesh, oxide_nm = map(float, (length, step, mesh, oxide_nm))
    target = .5 if neutral else (.1 if bit == 0 else .9)
    p = dict(
        schema='dram-see-v3', gate_length_um=length, oxide_nm=oxide_nm,
        stored_bit=None if neutral else bit, neutral=neutral, target_voltage_V=target,
        reference_mode=reference, reference_instance='refcell' if reference == 'physical' else None,
        reference_target_voltage_V=.5, reference_store_capacitance_F=1e-14,
        initialization_tolerance_V=.001, capacitance_F=1e-14,
        bitline_capacitance_F=1e-13, reference_capacitance_F=1e-13,
        precharge_V=.5, read_threshold_V=.005, sensitivity_thresholds_V=[.0025, .005, .01],
        precharge_resistance_on_ohm=100, precharge_resistance_off_ohm=1e20,
        precharge_ramp_end_s=2.9e-9, precharge_tolerance_V=1e-5,
        mesh_scale=mesh, step_scale=step, prestrike_s=.95e-9, strike_s=1e-9,
        hold_end_s=2.8e-9, precharge_end_s=3e-9, read_sample_s=4e-9,
        clamp_release_s=.6e-9, wordline_rise_start_s=3.05e-9,
        wordline_rise_end_s=3.10e-9, wordline_read_V=1.8,
        effective_thickness_um=1, temperature_K=300, charge_pc=0., angle_deg=0,
        parent_run=parent, source_event=None,
        initialization='ideal SN clamp released at 0.6 ns; not calibrated transistor write',
        interpretation='uncalibrated 1T1C, criterion readout error; no latch or restoration',
    )
    copied, ion, rad, cur = {}, '', '', ''
    if event is not None:
        evpath = (ROOT / event).resolve()
        if evpath.name != 'event.json' or not evpath.is_relative_to(HERE / 'data' / 'geant4'):
            raise ValueError('Need a frozen v3 event.json from data/geant4')
        metadata = evpath.read_bytes()
        files = {name: (evpath.parent / name).read_bytes() for name in ('steps.csv', 'events.csv')}
        ev = _module(HERE / 'event_audit.py', '_dram_v3_event_audit').validate_bytes(
            metadata, files, {'gate_length_um': length})
        q, track = (ev['converted'][0][key] for key in ('charge_pc', 'track_length_um'))
        angle = ev['angle_deg']
        if angle not in (0, 30) or not math.isfinite(q) or q < 0:
            raise ValueError('Invalid event source')
        a = math.radians(angle)
        direction = [-math.sin(a), math.cos(a), 0]
        exit_point = [length + .45 + track * direction[0], track * direction[1], 0]
        side_exit = angle != 0 and (length + .45) / math.sin(a) < 1.2 / math.cos(a)
        p.update(charge_pc=q, track_length_um=track, let_pc_per_um=q / track,
                 source_event=evpath.relative_to(ROOT).as_posix(), angle_deg=angle,
                 seed=ev['seed'], particle=ev['particle'], energy_MeV=ev['energy_MeV'],
                 event_id=0, impact_x_um=length + .45, direction=direction, track_radius_um=.03,
                 source_normalization_factor=1., source_exit_boundary='left' if side_exit else 'bottom',
                 source_exit_point_um=exit_point,
                 source_integral_contract={
                     'target_charge_pc': q, 'relative_tolerance': .05,
                     'normalization': 'none; LET=Geant4 silicon Q/finite track length',
                     'gaussian_truncation': 'finite silicon rectangle clips lateral Gaussian near entry/exit; actual spatial/time integral must pass',
                     'side_exit': side_exit, 'target_modified_for_truncation': False,
                     'zero_deposition': q == 0,
                 }, source_gaussian_diagnostic=_gaussian_geometry_diagnostic(length, angle, track))
        copied = {'source-event.json': metadata,
                  'source-steps.csv': files['steps.csv'], 'source-events.csv': files['events.csv']}
        p['source_evidence_sha256'] = {name: _sha(data) for name, data in copied.items()}
        if q > 0:
            ion = (f'HeavyIon ( StartPoint=({length + .45},0) '
                   f'Direction=({direction[0]},{direction[1]}) Time=1e-9 Length={track} '
                   f'Wt_hi=0.03 LET_f={q / track} Gaussian PicoCoulomb )')
            rad = 'HeavyIonChargeDensity HeavyIonGeneration'
            cur = 'CurrentPlot { HeavyIonGeneration(Integrate(Semiconductor)) }'
    out.parent.mkdir(parents=True, exist_ok=True)
    geometry = _geometry(length, mesh, oxide_nm, out.parent)
    renderer = _physical_device if reference == 'physical' else _single_device
    deck = renderer(target, step, ion, rad, cur)
    control_deck = renderer(target, step)
    matching = {key: p[key] for key in MATCHING_KEYS}
    matching.update(geometry_sha256=_sha(geometry), physics=PHYSICS, circuit_revision=CIRCUIT)
    p['matching_contract'] = matching
    p['matching_contract_sha256'] = _json_sha(matching)
    contract = dict(matching, schema=p['schema'], stored_bit=p['stored_bit'],
                    target_voltage_V=target, neutral=neutral, reference_mode=reference,
                    reference_instance=p['reference_instance'],
                    full_control_deck_sha256=_sha(control_deck.encode()))
    p['model_contract'] = contract
    p['model_contract_sha256'] = _json_sha(contract)
    p['source_code_sha256'] = {
        path.relative_to(ROOT).as_posix(): _sha(path.read_bytes())
        for path in (Path(__file__), V1, V2, HERE.parent / 'dram-readout-offset-d1' / 'build.py')
    }
    if event is not None:
        p['source_code_sha256'][(HERE / 'event_audit.py').relative_to(ROOT).as_posix()] = _sha((HERE / 'event_audit.py').read_bytes())
    p['parameter_sources'] = {
        'geometry_doping_physics_timing_capacitance': 'Inherited uncalibrated v1 geometry and v2 controlled initialization/readout; source_code_sha256 binds exact source',
        'reference': 'plan.md matched neutral SN=0.5 V, Cstore=10 fF and Cbitline=100 fF; D1 matched_ref circuit topology with independently scoped devices',
        'oxide_5nm': 'Inherited exploratory v1 model; not foundry calibration',
        'oxide_4_6nm': 'plan.md controlled +/-20% sensitivity assumption at L=0.25 um; fixed silicon-entry transport',
        'thresholds': 'Unchanged main +/-5 mV; sensitivity +/-2.5 and +/-10 mV',
        'particle': 'Frozen event.json and exact raw CSV hashes; legal zero deposition preserved' if event is not None else 'No particle',
    }
    if parent is not None:
        inherited, provenance = _parent_inputs(parent, p, geometry, control_deck)
        copied.update(inherited)
        copied['restart-provenance.json'] = (json.dumps(provenance, indent=2) + '\n').encode()
        prefix = deck[:deck.index('Solve {')]
        prefix = _replace_once(prefix, f' Set(sn={target} bl=0 ref=0.5)\n', '')
        tail = deck[deck.index(' Transient(InitialTime=0.95e-9'):]
        deck = prefix + 'Solve {\n Load(FilePrefix="charged")\n Set(bl=0 ref=0.5)\n Plot(FilePrefix="prestrike")\n' + tail
    outputs = ['circuit.plt', 'access_device.plt', 'transient_des.log', 'final_access_des.tdr']
    if reference == 'physical':
        outputs += ['refcell_device.plt', 'final_refcell_des.tdr']
    steps = [{'tool': 'sde', 'args': ['-e', '-l', 'geometry.scm'], 'outputs': ['cell_msh.tdr']}]
    if parent is not None:
        steps = []
    steps.append({'tool': 'sdevice', 'args': ['device.cmd'], 'outputs': outputs})
    copied.update({
        'geometry.scm': geometry, 'device.cmd': deck.encode(),
        'parameters.json': (json.dumps(p, indent=2) + '\n').encode(),
        'project.json': (json.dumps({'name': out.name, 'steps': steps}, indent=2) + '\n').encode(),
        'generator-sha256.txt': (_sha(Path(__file__).read_bytes()) + '\n').encode(),
        'geometry-generator-sha256.txt': (_sha(V1.read_bytes()) + '\n').encode(),
    })
    # All semantic checks finish before the exclusive creation of the input.
    out.mkdir()
    for name, data in copied.items():
        with (out / name).open('xb') as stream:
            stream.write(data)
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--length', type=float, default=.25)
    parser.add_argument('--bit', type=int, default=1)
    parser.add_argument('--event')
    parser.add_argument('--parent')
    parser.add_argument('--step', type=float, default=1.)
    parser.add_argument('--mesh', type=float, default=1.)
    parser.add_argument('--oxide-nm', type=float, default=5.)
    parser.add_argument('--reference', choices=['offline', 'physical'], default='offline')
    parser.add_argument('--neutral', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.length, args.bit, args.event, args.parent,
                           args.step, args.mesh, args.oxide_nm, args.reference, args.neutral), indent=2))
