"""Prospective v3 design, deterministic event enumeration and bounded NL interface."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from common import HERE, ROOT, LOCAL, now, sha, write_json

CANONICAL_REQUEST = '扫描栅长0.18、0.25、0.35、0.45 um；粒子alpha、proton；能量5 MeV；方向0、30度；每工况4个独立事件；每事件配对0/1；累计求解预算24小时；焦点0.25 um氧化层4、5、6 nm。'

def events():
    rows = []
    for li, length in enumerate((.18,.25,.35,.45)):
        for pi, particle in enumerate(('alpha','proton')):
            for ai, angle in enumerate((0,30)):
                c = 4*li + 2*pi + ai
                theta = math.radians(angle)
                for r in range(1,5):
                    seed = 202610300 + 10*c + r
                    rows.append({'label': f'l{round(length*100):03d}-{particle}-a{angle}-s{seed}',
                        'condition_id': c, 'replicate': r, 'seed': seed, 'gate_length_um': length,
                        'particle': particle, 'energy_MeV': 5., 'angle_deg': angle, 'event_count': 1,
                        'paired_bits': [0,1], 'surface_impact_um': [length+.45,0,0],
                        'launch_position_um': [length+.45+.001*math.tan(theta),-.001,0],
                        'direction': [-math.sin(theta),math.cos(theta),0],
                        'split': 'train' if length in (.18,.35) else ('holdout' if length==.25 else 'extrapolation'),
                        'pilot': length==.18 and r==1})
    return rows

def parse_request(text):
    """Deliberately bounded Chinese template, no arbitrary shell/LLM execution."""
    normalized = re.sub(r'\s+', '', text).replace('μm','um').replace('µm','um').replace('，','、').rstrip('。')
    pattern = (r'扫描栅长(?P<lengths>[\d.、]+)um；粒子(?P<particles>[a-z、]+)；能量(?P<energy>[\d.]+)MeV；'
               r'方向(?P<angles>[\d.、]+)度；每工况(?P<n>\d+)个独立事件；每事件配对0/1；'
               r'累计求解预算(?P<hours>[\d.]+)小时；焦点(?P<focus>[\d.]+)um氧化层(?P<oxides>[\d.、]+)nm')
    match = re.fullmatch(pattern, normalized)
    if not match:
        raise ValueError('Ambiguous or unsupported request: use the documented bounded template with explicit units')
    q = match.groupdict()
    config = {'lengths': list(map(float,q['lengths'].split('、'))), 'particles': q['particles'].split('、'),
              'energy': float(q['energy']), 'angles': list(map(float,q['angles'].split('、'))),
              'n': int(q['n']), 'hours': float(q['hours']), 'focus': float(q['focus']),
              'oxides': list(map(float,q['oxides'].split('、')))}
    expected = {'lengths':[.18,.25,.35,.45], 'particles':['alpha','proton'], 'energy':5.,
                'angles':[0.,30.], 'n':4, 'hours':24., 'focus':.25, 'oxides':[4.,5.,6.]}
    if config != expected:
        raise ValueError('Request exceeds or differs from authorized frozen matrix/budget; no inputs or queue generated')
    return events()

def make_design():
    rows = events()
    old_seeds = set()
    for name in ('dram-see-v1','dram-see-v2'):
        for p in (HERE.parent/name/'data').rglob('event.json'):
            x=json.loads(p.read_text(encoding='utf8'))
            if 'seed' in x: old_seeds.add(x['seed'])
    if old_seeds.intersection(x['seed'] for x in rows):
        raise ValueError('Seed overlaps historical event')
    if len(rows)!=64 or len({x['seed'] for x in rows})!=64:
        raise ValueError('Event contract')
    return {
        'schema':'dram-see-v3', 'revision':1, 'frozen_utc':now(),
        'scope':'Uncalibrated 2D 1T1C; conditional simulation response, not commercial DRAM reliability or radiation cross section',
        'git_commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        'plan_sha256':sha(HERE/'plan.md'), 'handoff_sha256':sha(HERE/'handoff.md'),
        'preservation_sha256':sha(LOCAL/'preservation-before.json'), 'design_generator_sha256':sha(__file__),
        'independent_event_count':64, 'tcad_paired_response_count':128, 'events':rows,
        'historical_event_seeds_checked':sorted(old_seeds), 'pilot_counts_towards_main_matrix':True,
        'thresholds_mV':[2.5,5.,10.], 'main_threshold_mV':5.,
        'metrics':{'deltaQ_fC':'1e15*Cstore*(SN_event(2.8ns)-SN_matched_control(2.8ns)); signed',
            'D_mV':'1000*(BL_signal-BL_matched_neutral)', 'M_mV':'(2*stored_bit-1)*D(4ns)',
            'deltaM_mV':'M_matched_control-M_event; positive is margin loss',
            'read_window_ns':[3.8,4.], 'read_window_report':['M_min','M_max','M_end_minus_start'],
            'classification':'M>epsilon correct; M<-epsilon criterion_error; closed interval critical'},
        'reference':{'target_V':.5,'storage_capacitance_F':1e-14,'bitline_capacitance_F':1e-13,
            'mode':'per-condition full neutral BL curve; real twin branch validation',
            'physical_devices':['SignalCell','ReferenceCell'], 'signal_instance':'access', 'reference_instance':'refcell',
            'heavyion_scope':'signal device only; reference zero source', 'physical_initialization':'full, no single-branch sav',
            'matching_fields':['length','oxide','geometry/mesh','time-step','physics','timing','capacitances'],
            'constant_offset_subtraction':False},
        'gates':{'initial_error_mV':1.,'precharge_error_uV':10.,'end_time_ns':4.,'source_relative_error_max':.05,
            'reference_source_charge_max_fC':1e-12,
            'kcl':'1e-12 A + 0.001*local absolute current scale',
            'be':'max(0.001 fC, 0.001*absolute capacitor charge change)',
            'four_terminal':'max(0.002 fC, 0.001*absolute charge change)',
            'physical_offline_each_voltage_and_D_mV':.1,'physical_offline_classifications_all_thresholds_equal':True,
            'numerical_readout_change_mV':.5,'numerical_deltaQ_change_fC':.01},
        'source':{'energy_MeV':5.,'track_radius_um':.03,'charge_conversion_eV_per_pair':3.6,
            'let':'Qdep_pC/track_length_um; normalization factor 1',
            'track_length':'angle0:1.2; angle30:min(1.2/cos(theta),(L+0.45)/sin(theta))',
            'gaussian_truncation':'report geometry-based estimate separately; actual integral compared to original total Qdep, never retarget Qdep*F',
            'zero_deposition':'legal, retain event and paired responses; no replacement'},
        'statistics':{'strata':['length','particle','angle','stored_bit','threshold'], 'planned_n_each':4,
            'counts':['valid','correct','criterion_error','critical','numerically_uncertain','failed','missing'],
            'point_bounds':'[k_error/N,(k_error+k_critical+k_uncertain+k_failed+k_missing)/N]',
            'interval':'Wilson 95% two-sided with z=1.959963984540054; envelope over best/worst unresolved assignments using planned N',
            'interval_endpoints_clamped':[0,1],
            'zero_event_upper':'1-0.05**(1/N) only if all planned responses determinate and k_error=0',
            'paired_any_bit':'optional; collapse by event first, never double N',
            'no_multiple_testing_claim':'descriptive intervals, not simultaneous coverage or significance claims'},
        'prediction':{'train_lengths_um':[.18,.35],'holdout_lengths_um':[.25],'extrapolation_lengths_um':[.45],
            'models':['training_mean','ridge'], 'targets':['deltaQ_fC','deltaM_mV'], 'separate_model_per_bit_and_target':True,
            'features':['Qdep_fC','Qdep_fC/L_um','Qdep_fC*sin(theta)'], 'ridge_candidates':[0.,.01,.1,1.,10.],
            'cv':'leave-one-physical-condition-out over 8 training (L,particle,angle) groups; all four repeats and both bits stay grouped',
            'selection_score':'arithmetic mean of per-fold RMSE for each bit/target independently',
            'tie_break':'lowest alpha among scores within 1e-12 target units of minimum',
            'standardization':'training fold population mean/std only; zero std replaced with1; final fit uses all training data',
            'ridge_objective':'sum_squared_error + alpha*sum(coef**2); intercept unpenalized; alpha0 via least-squares',
            'required_training':'all 64 training bit responses audited; unresolved outcome blocks prediction freeze',
            'freeze_before_test':'model coefficients/scalers/config, all test input Geant4 events and matched baselines, per-event predictions and SHA256 before any holdout/extrapolation TCAD response',
            'metrics':['MAE','RMSE','max_absolute_error','stratified_residuals'],
            'scope':'predict TCAD response given actual Geant4 deposition and known unirradiated baselines; oxide extension excluded from length prediction scores'},
        'numerical':{'preregistered':{'length_um':.18,'particle':'alpha','angle_deg':30,'replicate':1,'stored_bit':1},
            'variations':[{'step':.5,'mesh':1.},{'step':1.,'mesh':.7}],
            'matching':'event, own control and neutral reference at each variation',
            'additional_count':2,'distance':'min over epsilon in2.5,5,10 of abs(M-epsilon),abs(M+epsilon)',
            'selection':'all main-matrix responses; sort by(distance,condition_id,replicate,stored_bit); choose first two unique response IDs; reuse if preregistered point selected',
            'near_boundary_mV':.5, 'unresolved_near_boundary':'mark numerically_uncertain at affected threshold until matching refinement confirms stable classification',
            'crossing':'preserve raw classes and mark numerically_uncertain, never change threshold or seed'},
        'oxide_extension':{'length_um':.25,'oxide_nm':[4.,5.,6.], 'baseline_nm':5., 'angle_deg':0,'particles':['alpha','proton'],
            'replicate':1,'paired_bits':[0,1], 'new_thicknesses_require':['rebuilt_geometry_mesh','bit0_control','bit1_control','neutral_reference'],
            'additional_independent_events':0,'source':'controlled assumption ±20% about existing uncalibrated5nm model',
            'transport_scope':'fixed silicon-entry events; Geant4 material stack remains silicon/vacuum'},
        'execution':{'serial_threads':1,'solver_budget_s':86400,'kill_on_budget':False,
            'stage_order':['freeze','reference_and_baselines','pilot_and_source_isolation','training','model_and_prediction_freeze','holdout_and_extrapolation','oxide_and_numerics','delivery'],
            'initial_reserve_s':{'main_responses':55000,'reference_validation':7300,'numerics':13000,'oxide':6200,'failure_and_margin':4900},
            'accounting':'all new v3 solver wallclock including failed/validation runs; missing solver time uses conservative runner elapsed; inherited runs cost0',
            'submission_stop':'before next run if elapsed+conservative_next_estimate>86400; retain fixed planned denominator, no seed replacement',
            'long_run':'preserve running solver; inspection before next dispatch, no automatic kill or retry'},
        'course_pending':['actual2-3student_roles','teacher_review','lab_resource_handoff','defense','final_assessment'],
        'old_pilot_and_thresholds_unchanged':True,
        'source_freeze_policy':'Before each stage dispatch, immutable execution-freeze manifest binds source/dependency hashes and prepared inputs; revised code gets a new manifest, never rewrites prior evidence'
    }

def freeze():
    if (HERE/'stats-design.json').exists(): raise ValueError('Design already frozen')
    if list((ROOT/'local_runtime/runs').glob('*-v3-*')): raise ValueError('v3 response exists before design freeze')
    d=make_design()
    assert parse_request(CANONICAL_REQUEST)==d['events']
    write_json(HERE/'stats-design.json',d,exclusive=True)
    (LOCAL/'stats-design.sha256').write_text(sha(HERE/'stats-design.json')+'\n')
    return {'events':64,'responses':128,'sha256':sha(HERE/'stats-design.json')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','request']);p.add_argument('--text',default=CANONICAL_REQUEST);a=p.parse_args()
    print(json.dumps(freeze() if a.action=='freeze' else parse_request(a.text),indent=2,ensure_ascii=False))
