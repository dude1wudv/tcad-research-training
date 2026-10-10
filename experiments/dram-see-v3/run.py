"""Serial v3 stage controller using the existing TCAD runner and immutable inputs."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from common import HERE, ROOT, LOCAL, now, sha, write_json, controller_lock, preflight, check_preservation

LEDGER = LOCAL/'ledger.json'
DESIGN = HERE/'stats-design.json'

def module(name):
    spec=importlib.util.spec_from_file_location('v3_'+name,HERE/(name+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

def design():
    if sha(DESIGN)!=(LOCAL/'stats-design.sha256').read_text().strip(): raise ValueError('Frozen design changed')
    return json.loads(DESIGN.read_text(encoding='utf8'))

def load():
    return json.loads(LEDGER.read_text(encoding='utf8')) if LEDGER.exists() else {'schema':'dram-see-v3','runs':{},'stages':{},'failures':[]}

def save(value): write_json(LEDGER,value)

def tag_base(length,bit,oxide=5,step=1,mesh=1):
    return f'v3-control-l{round(length*100):03d}-b{bit}-ox{oxide:g}-s{step:g}-m{mesh:g}'

def tag_neutral(length,oxide=5,step=1,mesh=1):
    return f'v3-neutral-l{round(length*100):03d}-ox{oxide:g}-s{step:g}-m{mesh:g}'

def safe_tag(value):
    return value.replace('.','p')

def resolve(tag):
    row=load()['runs'].get(safe_tag(tag))
    if not row or row['state']!='VERIFIED': raise ValueError('Required verified run missing: '+tag)
    return row['run_id']

def budget():
    total=0.
    ledger=load()
    known={x.get('run_id') for x in ledger['runs'].values()}
    orphan=[p.parent.name for p in (ROOT/'local_runtime/runs').glob('*-v3-*/manifest.json') if p.parent.name not in known]
    if orphan:raise ValueError('Unreconciled v3 archive; account and inspect before dispatch: '+repr(orphan))
    for item in ledger['runs'].values():
        if item.get('inherited'): continue
        if item['state']=='RUNNING': raise ValueError('Unsettled v3 attempt; inspect without resubmission')
        total+=item.get('charged_solver_s',item.get('elapsed_s',0))
    return total

def source_hashes():
    paths=[HERE/(n+'.py') for n in ('common','design','run','build_case','transport','event_audit','audit','metrics')]+[ROOT/'scripts/tcad.py',HERE.parent/'dram-see-v1/build_case.py',HERE.parent/'dram-see-v1/analyze.py',HERE.parent/'dram-see-v1/geant4_transport.cc',HERE.parent/'dram-see-v2/audit.py',HERE.parent/'dram-see-v2/build_case.py',HERE.parent/'dram-readout-offset-d1/audit.py']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}

def freeze_execution(label,prepared):
    out=LOCAL/'execution-freezes'/(label+'.json')
    body={'utc':now(),'design_sha256':sha(DESIGN),'source_sha256':source_hashes(),'inputs':prepared}
    write_json(out,body,exclusive=True)
    return out

def check_execution(path):
    d=json.loads(Path(path).read_text(encoding='utf8'))
    if d['design_sha256']!=sha(DESIGN): raise ValueError('Execution/design mismatch')
    for n,h in d['source_sha256'].items():
        if sha(ROOT/n)!=h: raise ValueError('Frozen execution source changed '+n)
    for tag,hashes in d['inputs'].items():
        folder=LOCAL/'inputs'/tag
        if {p.name:sha(p) for p in folder.iterdir() if p.is_file()}!=hashes: raise ValueError('Frozen input changed '+tag)
    return d

def prepare(tag,**kwargs):
    tag=safe_tag(tag);folder=LOCAL/'inputs'/tag
    if folder.exists(): raise ValueError('Input already exists; use original execution freeze or explicit revised tag: '+tag)
    module('build_case').build(folder,**kwargs)
    return {p.name:sha(p) for p in folder.iterdir() if p.is_file()}

def record(tag,execution,estimate_s=600):
    tag=safe_tag(tag);frozen=check_execution(execution);l=load()
    if tag not in frozen['inputs']: raise ValueError('Input absent from execution freeze')
    if tag in l['runs']:
        if l['runs'][tag]['state']=='VERIFIED': return module('audit').audit(l['runs'][tag]['run_id'],export=False)
        raise ValueError('Unresolved prior attempt '+tag)
    if any(x['state']=='RUNNING' for x in l['runs'].values()): raise ValueError('Unsettled ledger')
    used=budget()
    if used+estimate_s>design()['execution']['solver_budget_s']:
        l['budget_stop']={'utc':now(),'used_s':used,'next_estimate_s':estimate_s,'unsubmitted_tag':tag};save(l)
        raise RuntimeError('Budget insufficient for next frozen item; retain planned denominator')
    folder=LOCAL/'inputs'/tag;p=json.loads((folder/'parameters.json').read_text())
    # Defense in depth: test particle responses cannot bypass the model freeze.
    if p.get('source_event') and p['gate_length_um'] in (.25,.45): check_prediction_freeze()
    if list((ROOT/'local_runtime/runs').glob('*-'+tag+'-*')): raise ValueError('Existing archive tag not reconciled; do not duplicate')
    preflight(tag)
    item={'state':'RUNNING','tag':tag,'started_utc':now(),'input_directory':folder.relative_to(ROOT).as_posix(),
          'execution_freeze':Path(execution).relative_to(ROOT).as_posix(),'execution_freeze_sha256':sha(execution),
          'input_sha256':frozen['inputs'][tag], 'parameters':p,'inherited':False}
    l['runs'][tag]=item;save(l)
    logs=LOCAL/'batch-logs';logs.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    command=[sys.executable,'-B',str(ROOT/'scripts/tcad.py'),'run',str(folder)];item['command']=command;save(l)
    with (logs/(tag+'.stdout.log')).open('xb') as out,(logs/(tag+'.stderr.log')).open('xb') as err:
        result=subprocess.run(command,cwd=ROOT,stdout=out,stderr=err)
    item.update(runner_exit_code=result.returncode,elapsed_s=time.monotonic()-started,finished_utc=now())
    matches=list((ROOT/'local_runtime/runs').glob('*-'+tag+'-*'))
    if len(matches)==1: item['run_id']=matches[0].name
    try:
        if len(matches)!=1 or result.returncode: raise RuntimeError('Runner failed or ambiguous identity; preserve original attempt')
        summary=module('audit').audit(item['run_id'],export=True)
        item['charged_solver_s']=summary.get('solver_s',summary.get('wallclock_s',item['elapsed_s']))
        item['state']='VERIFIED';item['audit_archive_sha256']=summary.get('archive_sha256');save(l)
    except Exception as exc:
        item['state']='FAILED';item['failure_reason']=repr(exc)
        # Charge actual solver log if available even when physics audit fails.
        wall=[]
        if len(matches)==1 and (matches[0]/'console.log').exists():
            wall=re.findall(r'wallclock:\s*([\d.]+) s',(matches[0]/'console.log').read_text(errors='replace'))
        item['charged_solver_s']=sum(map(float,wall)) if wall else item['elapsed_s']
        l['failures'].append(dict(item));save(l);raise
    print(json.dumps({'tag':tag,'run_id':item['run_id'],'state':item['state'],'solver_s':item['charged_solver_s'],'budget_used_s':budget()}),flush=True)
    return summary

def adopt_baselines():
    l=load();a=module('audit')
    v2=json.loads((ROOT/'local_runtime/dram-see-v2/ledger.json').read_text())
    for length in (.18,.25,.35,.45):
        for bit in (0,1):
            old=v2['runs'][f'v2-base-l{round(length*100):03d}-b{bit}'];tag=safe_tag(tag_base(length,bit))
            if tag in l['runs']: continue
            result=a.audit(old['run_id'],export=True)
            l['runs'][tag]={'state':'VERIFIED','run_id':old['run_id'],'inherited':True,'charged_solver_s':0,
                'audited_utc':now(),'role':'baseline','length_um':length,'bit':bit,'archive_sha256':result['archive_sha256']};save(l)
    d1=json.loads((ROOT/'local_runtime/dram-readout-offset-d1/ledger.json').read_text())
    old=d1['runs']['rodiag1-center050'];tag=safe_tag(tag_neutral(.25))
    if tag not in l['runs']:
        result=a.audit(old['run_id'],export=True)
        l['runs'][tag]={'state':'VERIFIED','run_id':old['run_id'],'inherited':True,'charged_solver_s':0,
            'audited_utc':now(),'role':'neutral','length_um':.25,'archive_sha256':result['archive_sha256']};save(l)
    print(json.dumps({'inherited_baselines':8,'inherited_neutral':1,'new_solver_s':0}),flush=True)

def prepare_references(label):
    design();check_preservation();prepared={}
    for length in (.18,.35,.45):
        tag=safe_tag(tag_neutral(length));prepared[tag]=prepare(tag,length=length,neutral=True)
    for length in (.18,.25,.35,.45):
        for bit in (0,1):
            tag=f'v3-physical-l{round(length*100):03d}-b{bit}'
            prepared[tag]=prepare(tag,length=length,bit=bit,reference='physical')
    path=freeze_execution(label,prepared);print(path)

def references(label,limit=None):
    execution=LOCAL/'execution-freezes'/(label+'.json');check_execution(execution);check_preservation();adopt_baselines();count=0
    for length in (.18,.35,.45):
        tag=tag_neutral(length)
        if safe_tag(tag) not in load()['runs']:
            if limit is not None and count>=limit:return
            record(tag,execution);count+=1
    for length in (.18,.25,.35,.45):
        for bit in (0,1):
            tag=f'v3-physical-l{round(length*100):03d}-b{bit}'
            if tag not in load()['runs']:
                if limit is not None and count>=limit:return
                record(tag,execution,1000);count+=1
            result=module('metrics').compare_reference(resolve(tag),resolve(tag_base(length,bit)),resolve(tag_neutral(length)))
            write_json(HERE/'data/reference-validation'/(tag+'.json'),result)
            if not result['passed']:raise ValueError('Physical/offline reference comparison failed')
    l=load();l['stages']['references']={'state':'VERIFIED','utc':now(),'physical_pairs':8};save(l)

def check_prediction_freeze():
    p=HERE/'data/predictions/freeze.json'
    if not p.exists():raise ValueError('Test TCAD blocked: models and per-event predictions not frozen')
    d=json.loads(p.read_text())
    if d.get('design_sha256')!=sha(DESIGN): raise ValueError('Prediction freeze/design mismatch')
    for name,h in d['files_sha256'].items():
        if sha(ROOT/name)!=h:raise ValueError('Frozen prediction artifact changed '+name)
    return d

def particle_stage(stage,label):
    d=design();l=load()
    if l['stages'].get('references',{}).get('state')!='VERIFIED': raise ValueError('Reference gate incomplete')
    if stage!='pilot' and l['stages'].get('pilot',{}).get('state')!='VERIFIED': raise ValueError('Pilot/source-isolation gate incomplete')
    if stage=='test':check_prediction_freeze()
    rows=[e for e in d['events'] if (e['pilot'] if stage=='pilot' else e['split']=='train' if stage=='train' else e['split']!='train')]
    prepared={};t=module('transport')
    for ev in rows:
        event=HERE/'data/geant4'/ev['label']/'event.json'
        if not event.exists():
            preflight('transport-'+ev['label']);t.run(ev['label'],ev['gate_length_um'],ev['particle'],ev['seed'],ev['angle_deg'])
        for bit in (0,1):
            tag='v3-'+ev['label']+f'-b{bit}'
            if tag in load()['runs']:
                if load()['runs'][tag]['state']!='VERIFIED': raise ValueError('Unresolved response '+tag)
                continue
            prepared[tag]=prepare(tag,length=ev['gate_length_um'],bit=bit,event=event.relative_to(ROOT).as_posix(),parent=resolve(tag_base(ev['gate_length_um'],bit)))
    # Source-isolation runs are fixed in design, share same events but initialize twins fully.
    if stage=='pilot':
        for particle,angle,bit in (('alpha',30,1),('proton',0,0)):
            ev=next(e for e in rows if e['particle']==particle and e['angle_deg']==angle)
            tag=f'v3-isolation-{particle}-a{angle}-b{bit}'
            prepared[tag]=prepare(tag,length=.18,bit=bit,event=(HERE/'data/geant4'/ev['label']/'event.json').relative_to(ROOT).as_posix(),reference='physical')
    execution=freeze_execution(label,prepared)
    for tag in prepared:
        record(tag,execution,1000 if tag.startswith('v3-isolation') else 600)
    for ev in rows:
        for bit in (0,1):
            tag='v3-'+ev['label']+f'-b{bit}'
            m=module('metrics').paired_metrics(resolve(tag),resolve(tag_base(ev['gate_length_um'],bit)),resolve(tag_neutral(ev['gate_length_um'])))
            write_json(HERE/'data/metrics'/(tag+'.json'),m)
    if stage=='pilot':
        for particle,angle,bit in (('alpha',30,1),('proton',0,0)):
            ev=next(e for e in rows if e['particle']==particle and e['angle_deg']==angle)
            tag=f'v3-isolation-{particle}-a{angle}-b{bit}'
            comparison=module('metrics').compare_reference(resolve(tag),resolve('v3-'+ev['label']+f'-b{bit}'),resolve(tag_neutral(.18)))
            write_json(HERE/'data/reference-validation'/(tag+'.json'),comparison)
            if not comparison['passed']:raise ValueError('Source isolation reference mismatch')
    l=load();l['stages'][stage]={'state':'VERIFIED','utc':now(),'planned_events':len(rows)};save(l)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-references','adopt','references','pilot','train','test','status']);p.add_argument('--label',default='reference-r1');p.add_argument('--limit',type=int);a=p.parse_args()
    if a.action=='status':print(json.dumps(load(),indent=2));return
    with controller_lock():
        if a.action=='prepare-references':prepare_references(a.label)
        elif a.action=='adopt':adopt_baselines()
        elif a.action=='references':references(a.label,a.limit)
        else:particle_stage(a.action,a.label)

if __name__=='__main__':main()
