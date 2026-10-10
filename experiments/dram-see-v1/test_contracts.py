"""Focused failure and accounting contracts; no solver claims from unit tests."""
import unittest
from request_to_matrix import compile_request
from analyze import parse_plt, clean_times, integral

class Contracts(unittest.TestCase):
    def test_distinct_lengths_cannot_alias_one_case(self):
        with self.assertRaisesRegex(ValueError,'collide'):
            compile_request('栅长 0.181,0.184 um；粒子 alpha；能量 5 MeV；角度 0 deg')
    def test_supported_request_and_order(self):
        cases=compile_request('栅长 0.18,0.25 um；粒子 alpha,proton；能量 5 MeV；角度 0,30 deg')
        self.assertEqual(len(cases),8)
        self.assertEqual(cases[0]['gate_length_um'],.18)
        self.assertEqual(cases[-1]['angle_deg'],30)
    def test_ambiguous_or_injected_request_rejected(self):
        for text in ['把粒子能量改高一点','栅长 0.25 um；粒子 alpha；能量 5 MeV；角度 0 deg; rm -rf /']:
            with self.assertRaises(ValueError):compile_request(text)
    def test_bounds_and_budget(self):
        for text in ['栅长 0.01 um；粒子 alpha；能量 5 MeV；角度 0 deg','栅长 0.25 um；粒子 neutron；能量 5 MeV；角度 0 deg','栅长 0.25,0.25 um；粒子 alpha；能量 5 MeV；角度 0 deg']:
            with self.assertRaises(ValueError):compile_request(text)
        with self.assertRaises(ValueError):compile_request('栅长 0.18,0.25 um；粒子 alpha,proton；能量 5 MeV；角度 0,30 deg',max_cases=4)
    def test_truncated_nonfinite_and_missing_data(self):
        for text in ['datasets=["time" "i"] Data {0 1 2}', 'datasets=["time" "i"] Data {0 nan}', 'datasets=["time"]']:
            with self.assertRaises(ValueError):parse_plt(text)
    def test_actual_time_accounting(self):
        names,rows=parse_plt('datasets=["time" "i"] Data {0 0 1 2 3 4}')
        self.assertEqual(names,['time','i'])
        self.assertEqual(integral(rows,'time','i'),7)
        self.assertEqual(integral(rows,'time','i',right=True),10)
        with self.assertRaises(ValueError):clean_times([{'t':1},{'t':0}],'t')

if __name__=='__main__':unittest.main()
