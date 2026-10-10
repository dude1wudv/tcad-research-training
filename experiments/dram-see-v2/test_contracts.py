import unittest,json,hashlib
from statistics import wilson,zero_upper,summarize_classes
from event_audit import validate_bytes,BINARY_SHA,SOURCE_SHA
from audit import classification
from summarize import denominator
class Contracts(unittest.TestCase):
    def test_halfstep_must_preserve_all_registered_threshold_classes(self):
        from numerical_checks import compare_readout
        control={'differential_V':.03,'signed_margin_V':.03}
        for a,b in ((.0026,.0024),(.0051,.0048),(.0102,.0098)):
            coarse={'differential_V':a,'signed_margin_V':a}
            fine={'differential_V':b,'signed_margin_V':b}
            result=compare_readout(coarse,fine,control,control,[2.5,5,10])
            self.assertLess(result['D_difference_mV'],.5)
            self.assertFalse(result['passed'])
            self.assertFalse(result['all_threshold_classes_stable'])
        self.assertTrue(compare_readout(control,control,control,control,[2.5,5,10])['passed'])
    def test_missing_outcomes_do_not_become_zero_flip_confidence(self):
        s=denominator(['correct','uncertain'],4)
        self.assertEqual(s['missing_or_failed_n'],2)
        self.assertEqual(s['planned_flip_uncertain_missing_fraction_upper'],.75)
        self.assertIsNone(s['zero_definite_flip_exact_one_sided_95_upper'])
        self.assertIsNone(s['wilson_95_definite'])
        self.assertFalse(s['complete_planned_stratum'])
    def test_decision_boundary_and_bit_polarity(self):
        with self.assertRaises(ValueError):classification(float('nan'))
        for x in (-.005,0,.005):self.assertEqual(classification(x),'uncertain')
        self.assertEqual(classification(.020),'correct')
        self.assertEqual(classification(-.020),'criterion_logic_flip')
        self.assertEqual(classification((2*0-1)*(-.020)),'correct')
    def test_exact_zero_bound_and_uncertain_not_correct(self):
        self.assertAlmostEqual(zero_upper(1),.95)
        self.assertAlmostEqual(zero_upper(10),.2588655508930523)
        s=summarize_classes(['correct','uncertain'])
        self.assertEqual(s['correct'],1)
        self.assertIsNone(s['zero_flip_or_uncertain_exact_one_sided_95_upper'])
        self.assertEqual(s['n_independent_events'],2)
    def test_wilson_reference_and_invalid_denominator(self):
        self.assertEqual(wilson(0,6)[0],0)
        self.assertEqual(wilson(6,6)[1],1)
        lo,hi=wilson(5,10)
        self.assertAlmostEqual(lo,.236593090512564,places=12)
        self.assertAlmostEqual(hi,.763406909487436,places=12)
        with self.assertRaises(ValueError):wilson(1,0)
    def test_zero_energy_is_retained_and_corruption_rejected(self):
        files={'events.csv':b'event,ionizing_MeV,niel_MeV,primary_path_um\n0,0,0,1.2\n',
               'steps.csv':b'event,track,parent,x_um,y_um,z_um,t_ns,step_um,edep_MeV,niel_MeV,ionizing_MeV\n'}
        ev={'operation_exit_code':0,'event_count':1,'files_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()},
            'particle':'proton','gate_length_um':.25,'energy_MeV':5,'angle_deg':0,'seed':123,
            'binary_sha256':BINARY_SHA,'source_sha256':SOURCE_SHA,'conversion_eV_per_pair':3.6,'launch_position_um':[.7,-.001,0],
            'converted':[{'event':0,'ionizing_MeV':0,'charge_pc':0,'track_length_um':1.2,'let_pc_per_um':0}],
            'surface_impact_um':[.7,0,0],'direction':[0,1,0]}
        self.assertEqual(validate_bytes(json.dumps(ev).encode(),files)['converted'][0]['charge_pc'],0)
        with self.assertRaises(ValueError):validate_bytes(json.dumps(ev).encode(),files,{'seed':124})
        altered=dict(files);altered['events.csv']=b'bad'
        with self.assertRaises(ValueError):validate_bytes(json.dumps(ev).encode(),altered)
if __name__=='__main__':unittest.main()
