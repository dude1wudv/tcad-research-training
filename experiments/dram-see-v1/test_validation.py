"""Read-only contracts over event binding and frozen pilot archives."""
import hashlib
import json
import tempfile
import tarfile
import unittest
from pathlib import Path
from analyze import ROOT, analyze, clean_times, parse_plt, read
from build_case import build
from event_contract import validate_bytes, validate_event

PILOT = '20261009T165901Z-pilot-alpha5-l025-a0-r4-078fde99'
CONTROL = '20261009T170632Z-control-l025-cd6c15bc'
EVENT = ROOT / 'experiments' / 'dram-see-v1' / 'data' / 'geant4' / 'pilot-alpha5-l025-a0' / 'event.json'
EXPECTED = {'label': 'pilot-alpha5-l025-a0', 'gate_length_um': 0.25,
            'particle': 'alpha', 'energy_MeV': 5.0, 'angle_deg': 0.0,
            'seed': 20261009, 'event_count': 1}


def event_files():
    return {name: (EVENT.parent / name).read_bytes()
            for name in ('steps.csv', 'events.csv')}


class EventBindingContracts(unittest.TestCase):
    def test_changed_particle_angle_or_seed_is_rejected(self):
        files = event_files()
        original = json.loads(EVENT.read_text())
        for key, value in [('particle', 'proton'), ('angle_deg', 30), ('seed', 20261010)]:
            with self.subTest(key=key):
                changed = dict(original)
                changed[key] = value
                with self.assertRaises(ValueError):
                    validate_bytes(json.dumps(changed).encode(), files, EXPECTED)

    def test_changed_converted_charge_with_unchanged_csv_is_rejected(self):
        changed = json.loads(EVENT.read_text())
        changed['converted'][0]['charge_pc'] += 1e-5
        with self.assertRaisesRegex(ValueError, 'Converted value mismatch: charge_pc'):
            validate_bytes(json.dumps(changed).encode(), event_files(), EXPECTED)

    def test_build_copies_hash_bound_source_evidence_and_rejects_wrong_charge(self):
        event = validate_event(EVENT, EXPECTED)
        charge = event['converted'][0]['charge_pc']
        source = EVENT.relative_to(ROOT).as_posix()
        with tempfile.TemporaryDirectory(prefix='dram-see-binding-') as tmp:
            output = Path(tmp) / 'bound-input'
            params = build(output, length=.25, charge_pc=charge, angle=0, event=source)
            mapping = {'source-event.json': EVENT.name,
                       'source-steps.csv': 'steps.csv',
                       'source-events.csv': 'events.csv'}
            self.assertEqual(set(params['source_evidence_sha256']), set(mapping))
            for dest, src in mapping.items():
                content = (EVENT.parent / src).read_bytes()
                self.assertEqual((output / dest).read_bytes(), content)
                self.assertEqual(params['source_evidence_sha256'][dest],
                                 hashlib.sha256(content).hexdigest())
            with self.assertRaisesRegex(ValueError, 'TCAD charge does not match Geant4 event'):
                build(Path(tmp) / 'wrong-charge', length=.25,
                      charge_pc=charge + 1e-5, angle=0, event=source)

    def test_legacy_pilot_is_labeled_external_event_crosscheck(self):
        summary = analyze(PILOT, export=False)
        self.assertEqual(summary['event_binding'],
                         'legacy_external_event_crosscheck; metadata was not frozen in TCAD input')


class ArchivedPipelineContracts(unittest.TestCase):
    def test_pilot_backward_euler_charge_and_source_integral(self):
        summary = analyze(PILOT, export=False)
        archive = ROOT / 'local_runtime' / 'runs' / PILOT / 'results.tar'
        with tarfile.open(archive) as tf:
            names, rows = parse_plt(read(tf, 'circuit.plt').decode())
        rows = clean_times(rows, 'time')
        hold = [r for r in rows if r['time'] >= .95e-9 - 1e-20]
        q_be = -sum((b['time'] - a['time']) * b['i(access,sn)']
                    for a, b in zip(hold, hold[1:]))
        self.assertIn('i(access,sn)', names)
        self.assertAlmostEqual(q_be, summary['terminal_loss_C'], delta=1e-25)
        residual = abs(summary['capacitor_loss_C'] - q_be)
        self.assertLessEqual(residual, max(1e-18, .001 * abs(summary['capacitor_loss_C'])))
        self.assertLessEqual(summary['radiation']['source_integral_relative_error'], .05)

    def test_control_restart_provenance_and_no_particle_match(self):
        parent = analyze(PILOT, export=False)
        control = analyze(CONTROL, export=False)
        self.assertEqual(control['parameters']['charge_pc'], 0)
        self.assertFalse(control['radiation'])
        self.assertLessEqual(abs(control['prestrike_voltage_V'] - parent['prestrike_voltage_V']), 1e-6)
        self.assertLess(abs(control['voltage_drop_V']), 1e-6)

        folder = ROOT / 'local_runtime' / 'runs' / CONTROL
        manifest = json.loads((folder / 'manifest.json').read_text())
        with tarfile.open(folder / 'results.tar') as tf:
            provenance = json.loads(read(tf, 'restart-provenance.json'))
            self.assertEqual(provenance['parent_run'], PILOT)
            self.assertEqual(provenance['archive_sha256'], parent['archive_sha256'])
            for name, digest in provenance['copied_sha256'].items():
                self.assertEqual(hashlib.sha256(read(tf, name)).hexdigest(), digest)
                self.assertEqual(manifest['input_sha256'].get(name), digest)

if __name__ == '__main__':
    unittest.main()
