"""Manual r3 recovery of a collected parser failure, preserving failed input and logs."""
import hashlib,json,msvcrt
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];LOCAL=ROOT/'local_runtime/dram-readout-offset-d1'
FAILED='20261010T082333Z-rodiag1-matched-ref-a289c12b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,text):
    with p.open('x',encoding='utf8') as f:f.write(text)
def main():
    lock=(LOCAL/'controller.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        old=HERE/'design-r2.json';new=HERE/'design-r3.json'
        if new.exists() or sha(old)!=(LOCAL/'design-r2.sha256').read_text().strip():raise ValueError('Design revision already exists or parent changed')
        d=json.loads(old.read_text());lp=LOCAL/'ledger.json';l=json.loads(lp.read_text());fm=json.loads((ROOT/'local_runtime/runs'/FAILED/'manifest.json').read_text())
        if fm['state']!='FAILED_COLLECTED' or fm['ssh_exit_code']!=5:raise ValueError('Unexpected failed attempt')
        if sum(x['state']=='VERIFIED' for x in l['runs'].values())!=8 or l['runs']['rodiag1-matched-ref']['state']!='FAILED':raise ValueError('Unexpected ledger state')
        import sys;sys.path.insert(0,str(HERE));import run
        run.preflight('r3-before-amendment')
        snapshot=HERE/'source-revisions/r2';snapshot.mkdir(parents=True,exist_ok=False)
        for n,h in d['source_sha256'].items():
            if sha(HERE/n)!=h:raise ValueError('r2 source changed '+n)
            (snapshot/n).write_bytes((HERE/n).read_bytes())
        write_new(LOCAL/'ledger-r2-before-recovery.json',lp.read_text())
        for item in [l['runs']['rodiag1-matched-ref'],*l['failures']]:
            if item['case']['tag']=='rodiag1-matched-ref':item.update(run_id=FAILED,parsed_solver_error='device.cmd line14 offending input reference: syntax error; transient not started')
        run.save(l)
        path=HERE/'build.py';s=path.read_text(encoding='utf8').replace('Cell reference (','Cell refcell (').replace('i(reference,','i(refcell,').replace('reference_device.plt','refcell_device.plt').replace('final_reference_des.tdr','final_refcell_des.tdr')
        s=s.replace('    out.mkdir(parents=True)',"    if variant=='matched_ref':p['reference_instance']='refcell'\n    out.mkdir(parents=True)")
        path.write_text(s,encoding='utf8')
        oldsel="('design-r2.json' if (HERE/'design-r2.json').exists() else 'design.json')"
        newsel="('design-r3.json' if (HERE/'design-r3.json').exists() else ('design-r2.json' if (HERE/'design-r2.json').exists() else 'design.json'))"
        path=HERE/'run.py';s=path.read_text(encoding='utf8').replace(oldsel,newsel).replace("('matched-ref',.393727754888742","('matched-ref-r3',.393727754888742").replace("summaries['rodiag1-matched-ref']","summaries['rodiag1-matched-ref-r3']");path.write_text(s,encoding='utf8')
        path=HERE/'audit.py';s=path.read_text(encoding='utf8').replace(oldsel,newsel)
        s=s.replace("        if p['schema']", "        reference_instance=p.get('reference_instance','reference')\n        if p['schema']",1)
        s=s.replace("read(tf,'reference_device.plt')","read(tf,reference_instance+'_device.plt')")
        for node in ('snr','ref'):
            s=s.replace("'i(reference,"+node+")'","f'i({reference_instance},"+node+")'")
        s=s.replace("b['i(reference,'+node+')']","b['i('+reference_instance+','+node+')']")
        path.write_text(s,encoding='utf8')
        import importlib,build;importlib.reload(build)
        c=d['cases'][8];oldtag=c['tag'];c['tag']='rodiag1-matched-ref-r3';c.pop('input_sha256');out=LOCAL/'inputs'/c['tag'];build.build(c,out)
        prev=LOCAL/'inputs'/oldtag
        for n in ('cell_msh.tdr','geometry.scm'):
            if (prev/n).read_bytes()!=(out/n).read_bytes():raise ValueError('Geometry changed')
        expected=(prev/'device.cmd').read_text().replace('Cell reference (','Cell refcell (').replace('i(reference,','i(refcell,')
        if expected!=(out/'device.cmd').read_text():raise ValueError('Unexpected deck change')
        c['input_sha256']={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}
        d['source_sha256']={n:sha(HERE/n) for n in d['source_sha256']};d['revision']=3;d['previous_amendments']=[d['amendment']]
        d['amendment']={'utc':datetime.now(timezone.utc).isoformat(),'parent_design':'design-r2.json','parent_sha256':sha(old),
          'reason':'Collected parser failure at instance identifier reference; rename to refcell with corresponding current/output identifiers only.',
          'retired_failed_tag':oldtag,'failed_run_id':FAILED,'replacement_tag':c['tag'],'old_instance':'reference','new_instance':'refcell',
          'original_source_snapshot':'source-revisions/r2','physical_conditions_order_thresholds_budget_unchanged':True,
          'inherited_completed_runs':{k:v['run_id'] for k,v in l['runs'].items() if v['state']=='VERIFIED'}}
        write_new(new,json.dumps(d,indent=2)+'\n');write_new(LOCAL/'design-r3.sha256',sha(new)+'\n');print(json.dumps({'design':str(new),'sha256':sha(new),'amendment':d['amendment']},indent=2))
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
