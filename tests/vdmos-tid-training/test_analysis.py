"""Tests for the VDMOS archived-result analysis contracts."""
from pathlib import Path
import sys
import math
import tarfile
import unittest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402


class ParsePltTests(unittest.TestCase):
    def test_parses_real_dfise_column_names_and_rows(self):
        text = '''DF-ISE text
Info { datasets = [ "time" "gate OuterVoltage" "drain TotalCurrent" ] }
Data { 1.0 0.55 -2.0e-6 2.0 1.55 -3.0e-6 }
'''
        names, rows = analyze.parse_plt(text)
        self.assertEqual(names, ['time', 'gate OuterVoltage', 'drain TotalCurrent'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            'time': 1.0, 'gate OuterVoltage': 0.55, 'drain TotalCurrent': -2.0e-6,
        })
        self.assertEqual(rows[1]['gate OuterVoltage'], 1.55)

    def test_rejects_truncated_and_nonfinite_data(self):
        prefix = 'Info { datasets = [ "gate OuterVoltage" "drain TotalCurrent" ] }\n'
        for data in ('Data { 0.0 1.0 2.0 }', 'Data { 0.0 NaN }'):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    analyze.parse_plt(prefix + data)


class NumericalContractTests(unittest.TestCase):
    def test_log_current_crossing_interpolates_in_log_space(self):
        result = analyze.first_crossing(
            [{'v': 0.0, 'i': 1e-8}, {'v': 2.0, 'i': 1e-4}], 'v', 'i', 1e-6,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['value'], 1.0)
        self.assertEqual(result['bracket'], [[0.0, 1e-8], [2.0, 1e-4]])

    def test_crossing_not_found_returns_none(self):
        self.assertIsNone(analyze.first_crossing(
            [{'v': 0.0, 'i': 1e-8}, {'v': 1.0, 'i': 2e-8}], 'v', 'i', 1e-6,
        ))

    def test_terminal_current_balance_passes_and_fails(self):
        passing = [
            {'source TotalCurrent': -1e-6, 'drain TotalCurrent': 0.9e-6, 'gate TotalCurrent': 0.1e-6},
        ]
        result = analyze.current_balance(passing)
        self.assertLessEqual(result['worst_fraction_of_tolerance'], 1.0)

        failing = [
            {'source TotalCurrent': -1e-6, 'drain TotalCurrent': 0.8e-6, 'gate TotalCurrent': 0.1e-6},
        ]
        with self.assertRaisesRegex(ValueError, 'conservation exceeded tolerance'):
            analyze.current_balance(failing)


class ArchivedRunIntegrationTests(unittest.TestCase):
    def test_real_pilot_archive_contracts(self):
        run_id = '20261002T044057Z-vdmos-tid-pilot-v1-d408ee62'
        summary, (transfer_names, transfer), (breakdown_names, breakdown) = analyze.analyze_run(run_id)

        self.assertEqual(summary['run_id'], run_id)
        self.assertIn('Contact current exceeded limit:', self._breakdown_log(run_id))
        self.assertGreaterEqual(abs(breakdown[-1]['drain TotalCurrent']), 5e-6)

        # Sentaurus records gate OuterVoltage, including the 0.55 V barrier offset.
        self.assertIn('gate OuterVoltage', transfer_names)
        self.assertIn('gate InnerVoltage', transfer_names)
        for row in transfer:
            self.assertAlmostEqual(row['gate InnerVoltage'] - row['gate OuterVoltage'], 0.55, delta=1e-7)

        self.assertEqual(summary['transfer_sources'][0], 'transfer_des.plt:last actual drain-initialization sample')
        self.assertAlmostEqual(transfer[0]['gate OuterVoltage'], 0.0, delta=1e-7)
        self.assertAlmostEqual(transfer[0]['drain InnerVoltage'], 0.1, delta=1e-7)

        self.assert_bracket_contains(summary['vth'], 1e-7)
        self.assert_bracket_contains(summary['bv_current_criterion'], 1e-6)
        self.assertIn('drain TotalCurrent', breakdown_names)
        bracket_voltages = [point[0] for point in summary['bv_current_criterion']['bracket']]
        bracket_samples = [
            sample for sample in summary['avalanche_samples']
            if sample['internal_vds_V'] in bracket_voltages
        ]
        self.assertEqual(
            [sample['internal_vds_V'] for sample in bracket_samples],
            bracket_voltages,
        )
        for sample in bracket_samples:
            self.assertGreaterEqual(sample['generation_to_drain_current_ratio'], 0.9)
            self.assertLessEqual(sample['generation_to_drain_current_ratio'], 1.05)

        peak_fields = list(summary['last_semiconductor_peak_field'].values())
        self.assertTrue(peak_fields)
        self.assertTrue(all(math.isfinite(field) for field in peak_fields))
        self.assertGreater(max(peak_fields), 0)

    def test_resolution_comparison_thresholds_and_physical_inputs(self):
        parameters = {
            'dose_krad_SiO2': 0,
            'not_cm2': 1e11,
            'nit_total_cm2': 2e11,
            'area_factor': 3.0,
            'generator_sha256': 'fixture-hash',
        }
        reference = {
            'kind': 'production', 'run_id': 'reference', 'parameters': parameters,
            'vth': {'value': 1.0}, 'id_vg10_A_per_um': 10.0,
            'bv_current_criterion': {'value': 100.0},
        }
        verification = {
            **reference,
            'kind': 'verification',
            'run_id': 'verification',
            'parameters': {**parameters, 'mesh_scale': 0.5, 'step_scale': 0.5},
            'vth': {'value': 1.04},
            'id_vg10_A_per_um': 10.4,
            'bv_current_criterion': {'value': 104.0},
        }

        result = analyze.compare_resolution([reference, verification])
        self.assertTrue(result[0]['passed'])

        over_limit = {**verification, 'bv_current_criterion': {'value': 106.0}}
        result = analyze.compare_resolution([reference, over_limit])
        self.assertFalse(result[0]['passed'])

        changed_physics = {
            **verification,
            'parameters': {**verification['parameters'], 'area_factor': 4.0},
        }
        with self.assertRaisesRegex(ValueError, 'changed physical input: area_factor'):
            analyze.compare_resolution([reference, changed_physics])

    @staticmethod
    def _breakdown_log(run_id):
        archive = analyze.ROOT / 'local_runtime/runs' / run_id / 'results.tar'
        with tarfile.open(archive) as tf:
            matches = [m for m in tf.getmembers() if m.isfile() and m.name.removeprefix('./') == 'breakdown_des.log']
            if len(matches) != 1:
                raise AssertionError(f'expected one breakdown_des.log, found {len(matches)}')
            member = tf.extractfile(matches[0])
            if member is None:
                raise AssertionError('breakdown_des.log could not be read from real results archive')
            return member.read().decode(errors='replace')

    def assert_bracket_contains(self, crossing, threshold):
        self.assertIsNotNone(crossing)
        before, after = crossing['bracket']
        self.assertLess(before[1], threshold)
        self.assertGreaterEqual(after[1], threshold)
        self.assertGreaterEqual(crossing['value'], min(before[0], after[0]))
        self.assertLessEqual(crossing['value'], max(before[0], after[0]))


if __name__ == '__main__':
    unittest.main()
