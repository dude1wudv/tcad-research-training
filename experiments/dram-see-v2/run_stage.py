"""Serial, resumable stage controller around the existing authorized runner."""
import argparse,hashlib,importlib.util,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('v2_builder',HERE/'build_case.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
from audit import audit
import transport
LOCAL=ROOT/'local_runtime/dram-see-v2';LEDGER=LOCAL/'ledger.json'
SOLVER_BUDGET_S=14400  # revised before first particle response, based on observed baseline and v1 cost

def now():return datetime.now(timezone.utc).isoformat()
def load():return json.loads(LEDGER.read_text()) if LEDGER.exists() else {'schema':'dram-see-v2','runs':{},'operations':{},'failures':[]}
def save(ledger):
    LOCAL.mkdir(parents=True,exist_ok=True)
    LEDGER.write_text(json.dumps(ledger,indent=2)+'\n')
def charged_budget_s():
    # Sum actual completed solver walls. For interrupted/missing completion use
    # conservative local runner elapsed, which also includes transfer time.
    import re
    total=0.
    for folder in (ROOT/'local_runtime/runs').glob('*-v2-*'):
        mf=folder/'manifest.json'
        if not mf.exists():continue
        m=json.loads(mf.read_text())
        if m['state']=='RUNNING':raise RuntimeError('Another v2 run still active; inspect instead of resubmitting')
        text=(folder/'console.log').read_text(errors='replace') if (folder/'console.log').exists() else ''
        wall=re.findall(r'wallclock:\s*([\d.]+) s',text)
        if wall:total+=sum(map(float,wall))
        else:
            start=datetime.strptime(folder.name[:16],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()
            total+=max(0,mf.stat().st_mtime-start)
    return total
def record_run(tag,length,bit,event=None,parent=None,step=1,mesh=1):
    ledger=load()
    designpath=HERE/'stats-design.json'
    if designpath.exists() and json.loads(designpath.read_text())['solver_budget_s']!=SOLVER_BUDGET_S:
        raise ValueError('Controller budget differs from the immutable design')
    if tag in ledger['runs']:
        item=ledger['runs'][tag]
        if item['state']=='VERIFIED':
            s=audit(item['run_id'],export=False);p=s['parameters']
            if (p['gate_length_um'],p['stored_bit'],p.get('source_event'),p['parent_run'],p['step_scale'],p['mesh_scale'])!=(length,bit,event,parent,step,mesh):
                raise ValueError('Verified tag condition mismatch; refuse incompatible reuse')
            return s
        raise ValueError('Unresolved recorded attempt '+tag+'; inspect before explicit recovery')
    if charged_budget_s()>=SOLVER_BUDGET_S:
        ledger['budget_stop_utc']=now();save(ledger)
        raise RuntimeError('Frozen solver budget exhausted; remaining design items stay incomplete')
    inputs=LOCAL/'inputs'/tag
    if not inputs.exists():builder.build(inputs,length,bit,event,parent,step,mesh)
    p=json.loads((inputs/'parameters.json').read_text())
    if (p['gate_length_um'],p['stored_bit'],p.get('source_event'),p['parent_run'],p['step_scale'],p['mesh_scale'])!=(length,bit,event,parent,step,mesh):raise ValueError('Immutable input mismatch')
    if (inputs/'generator-sha256.txt').read_text().strip()!=hashlib.sha256((HERE/'build_case.py').read_bytes()).hexdigest():
        raise ValueError('Existing inputs use another generator; preserve and choose explicit new version')
    logs=LOCAL/'batch-logs';logs.mkdir(parents=True,exist_ok=True)
    item={'tag':tag,'state':'RUNNING','started_utc':now(),'input_directory':str(inputs.relative_to(ROOT)),
          'length_um':length,'bit':bit,'event':event,'parent':parent,'step':step,'mesh':mesh}
    ledger['runs'][tag]=item;save(ledger)
    with (logs/(tag+'.stdout.txt')).open('wb') as out,(logs/(tag+'.stderr.txt')).open('wb') as err:
        r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/tcad.py'),'run',str(inputs)],cwd=ROOT,stdout=out,stderr=err)
    matches=list((ROOT/'local_runtime/runs').glob('*-'+tag+'-*'))
    if len(matches)!=1:raise ValueError('Run identity ambiguous; no automatic resubmission')
    item.update(run_id=matches[0].name,runner_exit_code=r.returncode,finished_utc=now())
    try:
        if r.returncode:raise RuntimeError('Runner failed')
        s=audit(item['run_id']);item['state']='VERIFIED';item['wallclock_s']=s['wallclock_s']
        if s['wallclock_s']>900:item['single_run_budget_warning']='exceeded 15 min; inspect before continuing'
    except Exception as exc:
        item['state']='FAILED';item['audit_error']=repr(exc);ledger['failures'].append(dict(item));save(ledger)
        raise
    save(ledger)
    print(json.dumps({'tag':tag,'run_id':s['run_id'],'initial_V':s['prestrike_V'],'D_mV':s['differential_V']*1e3,'M_mV':s['signed_margin_V']*1e3,'class':s['classification'],'solver_s':s['wallclock_s']}),flush=True)
    if s['wallclock_s']>900:raise RuntimeError('Single-run inspection budget exceeded; verified result retained, batch halted')
    return s

def baselines():
    for length in (.25,.18,.35,.45):
        for bit in (1,0):record_run(f'v2-base-l{round(length*100):03d}-b{bit}',length,bit)

def particles(pilot=False):
    design=json.loads((HERE/'stats-design.json').read_text())
    if design['generator_sha256']!=hashlib.sha256((HERE/'build_case.py').read_bytes()).hexdigest():raise ValueError('Generator differs from frozen design')
    for ev in design['events']:
        if pilot and ev['replicate']!=0:continue
        label=ev['label'];eventfile=HERE/'data/geant4'/label/'event.json'
        if eventfile.exists():
            meta=json.loads(eventfile.read_text())
            if (meta['seed'],meta['gate_length_um'],meta['particle'])!=(ev['seed'],ev['gate_length_um'],ev['particle']):raise ValueError('Existing source mismatch')
        else:transport.run(label,ev['gate_length_um'],ev['particle'],ev['seed'])
        for bit in (1,0):
            baseline=f'v2-base-l{round(ev["gate_length_um"]*100):03d}-b{bit}'
            state=load()['runs'][baseline]
            if state['state']!='VERIFIED':raise ValueError('Missing baseline')
            base=audit(state['run_id'],export=False)
            with __import__('tarfile').open(ROOT/'local_runtime/runs'/state['run_id']/'inputs.tar') as tf:
                from analyze import read
                if read(tf,'generator-sha256.txt').decode().strip()!=design['generator_sha256']:
                    raise ValueError('Baseline generator differs from frozen design')
            if base['classification']!='correct':raise ValueError('Baseline read not correct; no radiation classification')
            tag=f'v2-{label}-b{bit}'
            record_run(tag,ev['gate_length_um'],bit,str(eventfile.relative_to(ROOT)).replace('\\','/'),state['run_id'])

def freeze_design(n=6):
    out=HERE/'stats-design.json'
    if out.exists():raise ValueError('Design already frozen')
    # An actual particle response would make this a retrospective registration.
    for folder in (ROOT/'local_runtime/runs').glob('*-v2-*'):
        if not (folder/'inputs.tar').exists():continue
        with __import__('tarfile').open(folder/'inputs.tar') as tf:
            from analyze import read
            prior=json.loads(read(tf,'parameters.json'))
        if prior.get('source_event') or prior.get('charge_pc'):
            raise ValueError('Particle response already submitted before freeze; require an explicitly retrospective design')
    ledger=load();controls=[x for x in ledger['runs'].values() if x['state']=='VERIFIED' and x['tag'].startswith('v2-base')]
    expected={(l,b) for l in (.18,.25,.35,.45) for b in (0,1)}
    actual=set()
    for x in controls:
        s=audit(x['run_id'],export=False);p=s['parameters']
        actual.add((p['gate_length_um'],p['stored_bit']))
        if p['parent_run'] or p['charge_pc'] or any((2*p['stored_bit']-1)*s['differential_V']<=eps for eps in (.0025,.005,.010)):
            raise ValueError('Baseline ineligible at a declared sensitivity threshold')
        if not p.get('model_contract_sha256'):raise ValueError('Baseline missing full model contract')
        if p['step_scale']!=1 or p['mesh_scale']!=1:raise ValueError('Need declared coarse baseline grid and step')
        with __import__('tarfile').open(ROOT/'local_runtime/runs'/x['run_id']/'inputs.tar') as tf:
            from analyze import read
            if read(tf,'generator-sha256.txt').decode().strip()!=hashlib.sha256((HERE/'build_case.py').read_bytes()).hexdigest():
                raise ValueError('Frozen baseline generator differs from current design')
    if len(controls)!=8 or actual!=expected:raise ValueError('Need exactly 8 uniform/readable baseline combinations')
    events=[]
    for particle,base in [('alpha',202610101),('proton',202610201)]:
        for j in range(n):
            seed=base+j
            events.append({'label':f'l025-{particle}-s{seed}','gate_length_um':.25,'particle':particle,'energy_MeV':5,
                           'angle_deg':0,'seed':seed,'replicate':j,'event_count':1,'paired_bits':[0,1],
                           'surface_impact_um':[.7,0,0],'direction':[0,1,0],'role':'independent_event_pilot'})
    d={'schema':'dram-see-v2','frozen_utc':now(),'n_per_particle':n,'independent_event_count':2*n,
       'tcad_paired_response_count':4*n,'events':events,'epsilon_mV':[2.5,5,10],'main_epsilon_mV':5,
       'sampling':'fixed position, 5 MeV, vertical; one unique seed per event; paired states not independent events',
       'scope':'small event pilot at L=0.25 um; no cross section or calibrated population probability',
       'solver_budget_s':SOLVER_BUDGET_S,'stopping':'budget or numerical failure only, never observed class; incomplete counts disclosed',
       'resource_basis':f'{n} independent events per particle frozen before any v2 particle response; observed first five v2 controls 352.10-390.08 s, archived v1 focus particles 242.03-271.65 s without the new readout; conservative 450 s per new response plus eight controls, debug and numerical validation within 4 single-core solver hours',
       'generator_sha256':hashlib.sha256((HERE/'build_case.py').read_bytes()).hexdigest(),
       'analysis_sha256_at_freeze':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('audit.py','numerical_checks.py','summarize.py','statistics.py','event_audit.py')},
       'numerical_selection':'closest margin to any registered threshold; require raw, control and corrected D differences <=0.5 mV and all threshold classifications stable; no change to event denominator',
       'prior_transport_exposure':[{ 'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((HERE/'data/geant4').glob('*/event.json'))],
       'prior_transport_exposure_scope':'Existing source energy may have been seen; no v2 particle TCAD response submitted before freeze, no seed excluded or replaced',
       'baseline_run_ids':[x['run_id'] for x in controls],
       'solver_wallclock_before_freeze_s':sum(x.get('wallclock_s',0) for x in controls)}
    with out.open('x') as f:f.write(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['baselines','freeze','pilot','particles']);p.add_argument('--n',type=int,choices=[3,4,6],default=6)
    a=p.parse_args()
    if a.stage=='baselines':baselines()
    elif a.stage=='freeze':freeze_design(a.n)
    else:particles(a.stage=='pilot')
