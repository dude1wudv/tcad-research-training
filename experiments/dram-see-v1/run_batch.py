"""Serial v1 orchestration. Real TCAD execution is delegated only to scripts/tcad.py."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from analyze import analyze,ROOT,HERE
from build_case import build
from transport import run as transport
from event_contract import validate_event

STATE=ROOT/'local_runtime/dram-see-v1/batch-state.json'

def execute_case(key,params,state):
    if key in state['runs']:
        record=state['runs'][key]
        if record['state']!='VERIFIED':raise RuntimeError('Unresolved prior attempt: '+key)
        return record['run_id']
    inputs=ROOT/'local_runtime/dram-see-v1/inputs'/key
    build(inputs,**params)
    started=datetime.now(timezone.utc).isoformat()
    record={'state':'RUNNING','started_utc':started,'input_directory':str(inputs.relative_to(ROOT))}
    state['runs'][key]=record;save(state)
    logs=ROOT/'local_runtime/dram-see-v1/batch-logs';logs.mkdir(exist_ok=True)
    with (logs/(key+'.txt')).open('wb') as stream:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/tcad.py'),'run',str(inputs)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    records=[]
    for file in (ROOT/'local_runtime/runs').glob('*-'+key+'-*/manifest.json'):
        records.append(json.loads(file.read_text()))
    if len(records)!=1:raise RuntimeError('Cannot identify unique new run '+key)
    m=records[0];record.update(run_id=m['run_id'],runner_exit_code=result.returncode,finished_utc=datetime.now(timezone.utc).isoformat())
    if result.returncode:
        record['state']='FAILED';save(state);raise RuntimeError('Real tool failure: '+key)
    try:
        summary=analyze(m['run_id'])
    except Exception as exc:
        record.update(state='QUALITY_REJECTED',error=str(exc));save(state);raise
    record['state']='VERIFIED';record['voltage_drop_V']=summary['voltage_drop_V'];save(state)
    print(json.dumps({'key':key,'run_id':record['run_id'],'drop_V':summary['voltage_drop_V'],'status':record['state']}),flush=True)
    return record['run_id']

def save(state):STATE.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--pilot-run',required=True);p.add_argument('--only',nargs='*');a=p.parse_args()
    matrix=json.loads((HERE/'matrix.json').read_text())
    matrix_sha=hashlib.sha256((HERE/'matrix.json').read_bytes()).hexdigest()
    state=json.loads(STATE.read_text()) if STATE.exists() else {'matrix_sha256':matrix_sha,'runs':{},'cases':{},'parents':{'0.25':a.pilot_run}}
    if state['matrix_sha256']!=matrix_sha:raise ValueError('Frozen matrix changed')
    analyze(a.pilot_run)
    selected=[c for c in matrix['cases'] if not a.only or c['id'] in a.only]
    if a.only and len(selected)!=len(set(a.only)):raise ValueError('Unknown case selection')
    for c in selected:
        l=c['gate_length_um'];lk=str(l)
        if lk not in state['parents']:
            rid=execute_case(f'baseline-l{round(l*100):03d}',{'length':l},state)
            state['parents'][lk]=rid;save(state)
        parent=state['parents'][lk]
        baseline_key=f'control-l{round(l*100):03d}'
        baseline=execute_case(baseline_key,{'length':l,'restart_run':parent},state)
        event_path=HERE/'data/geant4'/c['id']/'event.json'
        if event_path.exists():
            event=validate_event(event_path)
        else:
            event=transport(c['id'],l,c['particle'],c['energy_MeV'],c['angle_deg'],c['seed'],c['events'])
        event=validate_event(event_path,{'label':c['id'],'gate_length_um':l,'particle':c['particle'],
            'energy_MeV':c['energy_MeV'],'angle_deg':c['angle_deg'],'seed':c['seed'],'event_count':c['events']})
        params={'length':l,'charge_pc':event['converted'][0]['charge_pc'],'angle':c['angle_deg'],
                'event':event_path.relative_to(ROOT).as_posix(),'restart_run':parent}
        rid=execute_case('see-'+c['id'],params,state)
        state['cases'][c['id']]={'run_id':rid,'baseline_run':baseline,'split':c['split'],'event':params['event']}
        save(state)
    print('SELECTED_BATCH_COMPLETED',flush=True)

if __name__=='__main__':main()
