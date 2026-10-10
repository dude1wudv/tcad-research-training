"""Continue the authorized serial batch after the existing baseline job finishes."""
import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
LOCAL=ROOT/'local_runtime/dram-see-v2';LOG=LOCAL/'continuation.json'
record={'started_utc':datetime.now(timezone.utc).isoformat(),'stages':[],'status':'waiting_for_existing_baselines'}
def save():LOG.write_text(json.dumps(record,indent=2)+'\n')
def stage(name,args):
    row={'name':name,'started_utc':datetime.now(timezone.utc).isoformat(),'command':args};record['stages'].append(row);save()
    print('STAGE '+name,flush=True)
    result=subprocess.run(args,cwd=ROOT)
    row.update(exit_code=result.returncode,finished_utc=datetime.now(timezone.utc).isoformat());save()
    if result.returncode:raise RuntimeError(name+' failed; preserve evidence and inspect before continuing')
def main(n):
    save();deadline=time.monotonic()+5400
    expected={f'v2-base-l{round(l*100):03d}-b{b}' for l in (.18,.25,.35,.45) for b in (0,1)}
    while True:
        try:ledger=json.loads((LOCAL/'ledger.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):ledger={'runs':{}}
        states={tag:x['state'] for tag,x in ledger['runs'].items() if tag in expected}
        if any(x=='FAILED' for x in states.values()):raise RuntimeError('Existing baseline attempt failed; no automatic resubmission')
        if set(states)==expected and all(x=='VERIFIED' for x in states.values()):break
        if time.monotonic()>deadline:raise RuntimeError('Baseline wait expired; inspect existing VM jobs, do not resubmit')
        time.sleep(10)
    py=sys.executable;run=lambda script,*args:[py,'-B',str(HERE/script),*args]
    design=HERE/'stats-design.json'
    if not design.exists():stage('freeze',run('run_stage.py','freeze','--n',str(n)))
    elif json.loads(design.read_text())['n_per_particle']!=n:raise ValueError('Existing immutable design has another sample count')
    record['status']='executing';save()
    stage('first-paired-events',run('run_stage.py','pilot'))
    stage('full-restart-equivalence',run('numerical_checks.py','equivalence'))
    stage('remaining-frozen-events',run('run_stage.py','particles'))
    stage('matched-halfstep-check',run('numerical_checks.py','refine'))
    record['status']='completed'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--n',type=int,choices=[3,4,6],required=True);a=p.parse_args()
    try:main(a.n)
    except Exception as exc:record.update(status='needs_inspection',error=repr(exc));print(repr(exc),file=sys.stderr)
    finally:
        for name in ('summarize.py','make_report.py'):
            try:stage('analysis-'+name,[sys.executable,'-B',str(HERE/name)])
            except Exception as exc:record['analysis_error']=repr(exc)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()
    if record['status']!='completed':sys.exit(1)
