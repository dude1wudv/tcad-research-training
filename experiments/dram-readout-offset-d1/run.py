"""Frozen serial diagnostic controller; solver execution stays in scripts/tcad.py."""
import argparse,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from build import build,sha,BASE
from audit import audit
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];LOCAL=ROOT/'local_runtime/dram-readout-offset-d1'
DESIGN=HERE/('design-r4.json' if (HERE/'design-r4.json').exists() else ('design-r3.json' if (HERE/'design-r3.json').exists() else ('design-r2.json' if (HERE/'design-r2.json').exists() else 'design.json')));LEDGER=LOCAL/'ledger.json'
def now():return datetime.now(timezone.utc).isoformat()
def load():return json.loads(LEDGER.read_text()) if LEDGER.exists() else {'runs':{},'failures':[]}
def save(l):
    temp=LEDGER.with_suffix('.tmp');temp.write_text(json.dumps(l,indent=2)+'\n');os.replace(temp,LEDGER)
def preservation():
    paths=[p for name in ('dram-see-v1','dram-see-v2') for p in (HERE.parent/name).rglob('*') if p.is_file()]
    index=json.loads((HERE.parent/'dram-see-v2/data/summary/delivery-index.json').read_text(encoding='utf8'))
    paths += [ROOT/f['path'] for r in index['runs'] for f in r['files'].values() if f['present']]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
def check_preservation():
    expected=json.loads((LOCAL/'preservation-before.json').read_text());actual=preservation()
    changed=[n for n in set(expected)|set(actual) if expected.get(n)!=actual.get(n)]
    if changed:raise ValueError('Original experiment changed: '+repr(changed))
    return {'files_checked':len(expected),'changed':changed,'passed':True}
def freeze():
    if DESIGN.exists():raise ValueError('Design already frozen')
    LOCAL.mkdir(parents=True,exist_ok=True)
    cases=[('bridge090',.9,'standard'),('center050',.5,'standard'),('alpha-match',.393727754888742,'standard'),
           ('scan035',.35,'standard'),('scan045',.45,'standard'),('scan055',.55,'standard'),
           ('wl-off',.5,'wl_off'),('wl-slow',.5,'wl_slow'),('matched-ref-r3',.393727754888742,'matched_ref')]
    cases=[{'tag':'rodiag1-'+n,'sn_target_V':v,'variant':k,'order':i} for i,(n,v,k) in enumerate(cases)]
    for c in cases:
        if list((ROOT/'local_runtime/runs').glob('*-'+c['tag']+'-*')):raise ValueError('Pre-freeze diagnostic run exists')
    before=preservation();(LOCAL/'preservation-before.json').write_text(json.dumps(before,indent=2)+'\n')
    for c in cases:
        path=LOCAL/'inputs'/c['tag'];build(c,path)
        c['input_sha256']={p.name:sha(p) for p in sorted(path.iterdir()) if p.is_file()}
    d={'schema':'dram-readout-offset-d1','frozen_utc':now(),'cases':cases,'new_run_count':len(cases),
       'solver_budget_s':5400,'single_run_inspection_s':1200,'serial_threads':1,'original_baseline':BASE,
       'original_pilot_design_sha256':sha(HERE.parent/'dram-see-v2/stats-design.json'),
       'source_sha256':{n:sha(HERE/n) for n in ('build.py','audit.py','run.py')},
       'dependency_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (HERE.parent/'dram-see-v1/analyze.py',HERE.parent/'dram-see-v2/audit.py',ROOT/'scripts/tcad.py')},
       'prior_evidence':'v2 observed alpha small positive D; raw port-charge inspection preceded this diagnostic freeze; this is not prospective particle sampling',
       'hypotheses':['WL actuation supplies a substantial gate-displacement contribution to SN+BL net charge; quantify body and carrier terms separately',
                     'ideal REF omits an access-cell read common-mode response; compare one physical matched reference with offline center-trace subtraction'],
       'gates':{'bridge_D_abs_difference_mV':.01,'initial_tolerance_mV':1,'matched_reference_vs_offline_tolerance_mV':.1,'conservation':'KCL 1pA+0.1% local current; BE max(0.001fC,0.1% gain); four-port closure max(0.002fC,0.1% gain)','hypothesis_outcomes':'negative/null mechanism contrasts are valid results, not grounds to change samples'},
       'analysis_plan':{'scan':'D at4ns versus actual SN at3ns; two-capacitor prediction uses actual BL3/REF3; no fit extrapolation',
           'ports':'BE right-endpoint integrals over3–4ns of total/e/h/displacement for source/drain/gate/body; device current opposite circuit node inflow',
           'reference':'ideal REF drift; offline Dmatched=BLcase4-BLcenter4; physical twin reference neutral SN=.5 with identical BL precharge and WL; no calibrated sense latch',
           'wl':'same SN=.5, WL held0 and same-start 200ps rise compared with50ps rise; compare gate peak and total/net charge',
           'alpha_match':'compare no-particle scalar SN=.393727754888742 with original alpha101 read SN; carrier/field histories are not assumed equal'},
       'pilot_unchanged':True,'particle_event_count':0,'no_new_probability_estimates':True}
    with DESIGN.open('x',encoding='utf8') as f:json.dump(d,f,indent=2);f.write('\n')
    with (LOCAL/'design.sha256').open('x') as f:f.write(sha(DESIGN)+'\n')
    print(json.dumps({'frozen':str(DESIGN),'sha256':sha(DESIGN),'cases':len(cases)}))
def preflight(tag):
    # No second controller/solver or unresolved archive is silently reused.
    for folder in (ROOT/'local_runtime/runs').iterdir():
        p=folder/'manifest.json'
        if p.exists() and json.loads(p.read_text()).get('state') in ('RUNNING','PREPARED','EXECUTED'):raise ValueError('Unsettled run '+folder.name)
    sys.path.insert(0,str(ROOT/'scripts'));import tcad
    _,ssh,_=tcad.connection()
    command="ps -eo pid,ppid,stat,etime,comm,args | awk '$5 ~ /^(sdevice|sde|snmesh|transport)$/ {print}'; true"
    result=tcad.remote(ssh,command,capture_output=True,text=True,timeout=45)
    op=LOCAL/'preflight';op.mkdir(exist_ok=True)
    (op/(tag+'.json')).write_text(json.dumps({'utc':now(),'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
    if result.returncode or result.stdout.strip():raise ValueError('VM active/unknown; inspect without resubmission')
def stage(which):
    import msvcrt
    LOCAL.mkdir(parents=True,exist_ok=True)
    lock=(LOCAL/'controller.lock').open('a+b');lock.seek(0)
    if not lock.read(1):lock.write(b'0');lock.flush()
    lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        if sha(DESIGN)!=(LOCAL/(DESIGN.stem+'.sha256')).read_text().strip():raise ValueError('Frozen design hash changed')
        d=json.loads(DESIGN.read_text())
        for n,h in d['source_sha256'].items():
            if sha(HERE/n)!=h:raise ValueError('Frozen source changed '+n)
        for n,h in d['dependency_sha256'].items():
            if sha(ROOT/n)!=h:raise ValueError('Frozen dependency changed '+n)
        check_preservation();l=load()
        if which=='remaining' and any(l['runs'].get(c['tag'],{}).get('state')!='VERIFIED' for c in d['cases'][:2]):raise ValueError('Need sanity stage first')
        for c in (d['cases'][:2] if which=='sanity' else d['cases'][2:]):
            l=load();tag=c['tag']
            if tag in l['runs']:
                if l['runs'][tag]['state']=='VERIFIED':continue
                raise ValueError('Unresolved attempt '+tag)
            if sum(x.get('solver_s',x.get('elapsed_s',0)) for x in l['runs'].values())>=d['solver_budget_s']:raise ValueError('Frozen diagnostic budget exhausted')
            preflight(tag);inputs=LOCAL/'inputs'/tag
            if {p.name:sha(p) for p in inputs.iterdir() if p.is_file()}!=c['input_sha256']:raise ValueError('Immutable inputs differ')
            item={'state':'RUNNING','case':c,'started_utc':now()};l['runs'][tag]=item;save(l)
            logs=LOCAL/'batch-logs';logs.mkdir(exist_ok=True);t=time.monotonic()
            with (logs/(tag+'.stdout.log')).open('wb') as out,(logs/(tag+'.stderr.log')).open('wb') as err:
                r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/tcad.py'),'run',str(inputs)],cwd=ROOT,stdout=out,stderr=err)
            item.update(runner_exit_code=r.returncode,elapsed_s=time.monotonic()-t,finished_utc=now())
            matches=list((ROOT/'local_runtime/runs').glob('*-'+tag+'-*'))
            try:
                if len(matches)!=1 or r.returncode:raise ValueError('Runner failure/ambiguous identity')
                item['run_id']=matches[0].name;s=audit(item['run_id']);item['solver_s']=s['solver_s']
                if tag=='rodiag1-bridge090':
                    base=json.loads((HERE.parent/'dram-see-v2/data/tcad'/BASE/'summary.json').read_text())
                    if abs(s['D_mV']-base['differential_V']*1e3)>d['gates']['bridge_D_abs_difference_mV']:raise ValueError('Bridge does not reproduce frozen baseline')
                item['state']='VERIFIED';save(l)
            except Exception as exc:
                item['state']='FAILED';item['failure_reason']=repr(exc);l['failures'].append(dict(item));save(l);raise
            print(json.dumps({'tag':tag,'run_id':item['run_id'],'D_mV':s['D_mV'],'offset_mV':s['offset_mV'],'net_fC':s['SN_BL_gain_fC'],'solver_s':s['solver_s']}),flush=True)
            if s['solver_s']>d['single_run_inspection_s']:raise ValueError('Run completed but inspection threshold exceeded; stop before next')
        if which=='remaining':
            l=load();summaries={k:audit(v['run_id'],export=False) for k,v in l['runs'].items() if v['state']=='VERIFIED'}
            signal=summaries['rodiag1-alpha-match'];center=summaries['rodiag1-center050'];matched=summaries['rodiag1-matched-ref-r3']
            expected=(signal['final_BL_V']-center['final_BL_V'])*1e3;delta=abs(matched['D_mV']-expected)
            original=json.loads((HERE.parent/'dram-see-v2/data/tcad/20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa/summary.json').read_text())
            sn_error=(signal['read_SN_V']-original['read_precharge_SN_V'])*1e3
            comparison={'offline_matched_D_mV':expected,'physical_matched_D_mV':matched['D_mV'],'difference_mV':delta,
                'tolerance_mV':d['gates']['matched_reference_vs_offline_tolerance_mV'],'alpha_read_SN_match_error_mV':sn_error,
                'scalar_match_only_not_carrier_history':True,'passed':delta<=d['gates']['matched_reference_vs_offline_tolerance_mV'] and abs(sn_error)<=1,
                'run_ids':{k:v['run_id'] for k,v in summaries.items()}}
            (HERE/'comparisons.json').write_text(json.dumps(comparison,indent=2)+'\n')
            if not comparison['passed']:raise ValueError('Diagnostic pairing check failed; retain all results')
            print(json.dumps(comparison),flush=True)
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['freeze','sanity','remaining']);args=a.parse_args()
    freeze() if args.action=='freeze' else stage(args.action)
