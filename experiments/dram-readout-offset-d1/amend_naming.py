"""One-time, naming-only r2 amendment; run only after the sanity controller exits."""
import hashlib,json,msvcrt,re,sys
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
LOCAL=ROOT/'local_runtime/dram-readout-offset-d1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,text):
    with p.open('x',encoding='utf8') as f:f.write(text)
def main():
    lock=(LOCAL/'controller.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        old=HERE/'design.json';new=HERE/'design-r2.json'
        if new.exists():raise ValueError('Amendment already exists')
        if sha(old)!=(LOCAL/'design.sha256').read_text().strip():raise ValueError('Original design changed')
        d=json.loads(old.read_text());ledger=json.loads((LOCAL/'ledger.json').read_text())
        if set(ledger['runs'])!={c['tag'] for c in d['cases'][:2]} or any(x['state']!='VERIFIED' for x in ledger['runs'].values()):raise ValueError('Need exactly two completed sanity runs')
        for c in d['cases'][2:]:
            if list((ROOT/'local_runtime/runs').glob('*-'+c['tag']+'-*')):raise ValueError('Remaining case already dispatched')
        snapshot=HERE/'source-revisions/r1';snapshot.mkdir(parents=True,exist_ok=False)
        for n,h in d['source_sha256'].items():
            if sha(HERE/n)!=h:raise ValueError('r1 source changed '+n)
            (snapshot/n).write_bytes((HERE/n).read_bytes())
        # Only dispatch legality/design selection changes; all physical deck tokens stay unchanged.
        path=HERE/'build.py';s=path.read_text(encoding='utf8').replace('import hashlib,json,sys,tarfile','import hashlib,json,re,sys,tarfile')
        s=s.replace('    out=Path(out)','    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*",case["tag"]):raise ValueError("Unsafe runner project name")\n    out=Path(out)',1)
        path.write_text(s,encoding='utf8')
        path=HERE/'run.py';s=path.read_text(encoding='utf8')
        s=s.replace("DESIGN=HERE/'design.json';LEDGER=LOCAL/'ledger.json'","DESIGN=HERE/('design-r2.json' if (HERE/'design-r2.json').exists() else 'design.json');LEDGER=LOCAL/'ledger.json'")
        s=s.replace("('alphaSN',.393727754888742","('alpha-match',.393727754888742")
        s=s.replace("summaries['rodiag1-alphaSN']","summaries['rodiag1-alpha-match']")
        s=s.replace("sha(DESIGN)!=(LOCAL/'design.sha256').read_text().strip()","sha(DESIGN)!=(LOCAL/(DESIGN.stem+'.sha256')).read_text().strip()")
        path.write_text(s,encoding='utf8')
        path=HERE/'audit.py';s=path.read_text(encoding='utf8')
        s=s.replace("design=json.loads((HERE/'design.json').read_text())","design_path=HERE/('design-r2.json' if (HERE/'design-r2.json').exists() else 'design.json')\n    design=json.loads(design_path.read_text())")
        path.write_text(s,encoding='utf8')
        from build import build
        c=d['cases'][2];oldtag=c['tag'];c['tag']='rodiag1-alpha-match';c.pop('input_sha256')
        output=LOCAL/'inputs'/c['tag'];build(c,output)
        previous=LOCAL/'inputs'/oldtag
        for n in ('device.cmd','cell_msh.tdr','geometry.scm'):
            if (output/n).read_bytes()!=(previous/n).read_bytes():raise ValueError('Physical input differs '+n)
        op=json.loads((previous/'parameters.json').read_text());np=json.loads((output/'parameters.json').read_text())
        op['case']['tag']=c['tag'];op['builder_sha256']=np['builder_sha256']
        if op!=np:raise ValueError('Unexpected parameters change')
        a=json.loads((previous/'project.json').read_text());b=json.loads((output/'project.json').read_text());a['name']=c['tag']
        if a!=b:raise ValueError('Unexpected project change')
        c['input_sha256']={p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}
        d['source_sha256']={n:sha(HERE/n) for n in d['source_sha256']}
        d['revision']=2
        d['amendment']={'utc':datetime.now(timezone.utc).isoformat(),'parent_design':'design.json','parent_sha256':sha(old),
          'reason':'Runner requires lowercase safe project names; r1 contained an uppercase name. Discovered before dispatch; no solver failed.',
          'retired_unsubmitted_tag':oldtag,'replacement_tag':c['tag'],'physical_inputs_identical':True,
          'inherited_completed_runs':{k:x['run_id'] for k,x in ledger['runs'].items()},
          'original_source_snapshot':'source-revisions/r1','physical_conditions_order_thresholds_budget_unchanged':True}
        write_new(new,json.dumps(d,indent=2)+'\n');write_new(LOCAL/'design-r2.sha256',sha(new)+'\n')
        print(json.dumps({'design':str(new),'sha256':sha(new),'amendment':d['amendment']},indent=2))
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
