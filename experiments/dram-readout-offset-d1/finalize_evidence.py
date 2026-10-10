"""Index completed D1 evidence and preservation checks; no simulation dispatch."""
import json,sys,hashlib
from pathlib import Path
from datetime import datetime,timezone
from run import check_preservation
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];LOCAL=ROOT/'local_runtime/dram-readout-offset-d1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    d=json.loads((HERE/'design-r4.json').read_text());l=json.loads((LOCAL/'ledger.json').read_text());v=json.loads((HERE/'validation/independent-final.json').read_text())
    if v['status']!='passed' or any(l['runs'][c['tag']]['state']!='VERIFIED' for c in d['cases']):raise ValueError('Unverified batch')
    p=check_preservation();(HERE/'validation/preservation.json').write_text(json.dumps(p,indent=2)+'\n')
    sys.path.insert(0,str(ROOT/'scripts'));import tcad
    _,ssh,_=tcad.connection();command="ps -eo pid,ppid,stat,etime,comm,args | awk '$5 ~ /^(sdevice|sde|snmesh|transport)$/ {print}'; true"
    r=tcad.remote(ssh,command,capture_output=True,text=True,timeout=45)
    process={'utc':datetime.now(timezone.utc).isoformat(),'command':command,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'owned_SVisual_intentionally_left_open':True}
    (LOCAL/'final-processes.json').write_text(json.dumps(process,indent=2)+'\n')
    if r.stdout.strip():raise ValueError('Unexpected active solver')
    (LOCAL/'session-state.json').write_text(json.dumps({'updated_utc':datetime.now(timezone.utc).isoformat(),'stage':'complete','effective_design':'design-r4.json','verified_count':9,'historical_parser_failures':1,'particle_events_added':0,'active_solver_count':0,'tool_session':None,'next':[]},indent=2)+'\n')
    paths=[p for p in HERE.rglob('*') if p.is_file() and p.name!='delivery-index.json']
    paths += [p for p in LOCAL.rglob('*') if p.is_file() and p.name not in ('controller.lock','delivery-index.sha256')]
    private=ROOT/'local_runtime/dram-readout-offset-diagnostic'
    paths += [p for p in private.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.csv','.md','.log','.txt')]
    attempts=[]
    for tag,item in l['runs'].items():
        rid=item['run_id'];folder=ROOT/'local_runtime/runs'/rid;m=json.loads((folder/'manifest.json').read_text())
        paths += [p for p in folder.rglob('*') if p.is_file()]
        attempts.append({'tag':tag,'run_id':rid,'ledger_state':item['state'],'manifest_state':m['state'],
          'active_design_case':tag in {c['tag'] for c in d['cases']},'solver_s':item.get('solver_s'),
          'original_execution_ssh_exit_code':m.get('original_execution_ssh_exit_code',m.get('ssh_exit_code')),
          'ssh_exit_code':m.get('ssh_exit_code'),'ssh_exit_code_scope':m.get('ssh_exit_code_scope','original_execution'),
          'results_sha256':m.get('results_sha256')})
    files={p.relative_to(ROOT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(paths))}
    result={'schema':'dram-readout-offset-d1-delivery','utc':datetime.now(timezone.utc).isoformat(),'active_design':'design-r4.json',
       'active_design_sha256':sha(HERE/'design-r4.json'),'verified_cases':9,'historical_parser_failures':1,'independent_particle_events_added':0,
       'solver_seconds':v['batch_metrics']['solver_seconds_total'],'newton_retries':0,'preservation':json.loads((HERE/'validation/preservation.json').read_text()),
       'attempts':attempts,'files':files,'scope':'Deterministic model diagnosis, not device calibration or error probability. Raw stream interruption remains documented; no log marker fabricated.'}
    target=HERE/'delivery-index.json';target.write_text(json.dumps(result,indent=2)+'\n');(LOCAL/'delivery-index.sha256').write_text(sha(target)+'\n')
    print(json.dumps({'files_indexed':len(files),'runs':len(attempts),'verified':9,'preservation':result['preservation'],'index_sha256':sha(target)}))
if __name__=='__main__':main()
