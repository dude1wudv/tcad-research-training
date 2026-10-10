"""Read-only archive audit; writes only its validation JSON beside this file."""
import hashlib,json,math,re,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RID='20261010T013752Z-v2-pilot-control-l025-b1-r4-6f25f848'
F=ROOT/'local_runtime/runs'/RID
def sha(b):return hashlib.sha256(b).hexdigest()
def member(tf,n):
    ms=[m for m in tf.getmembers() if m.isfile() and m.name.removeprefix('./')==n]
    assert len(ms)==1,n
    return tf.extractfile(ms[0]).read()
manifest=json.loads((F/'manifest.json').read_bytes())
assert manifest['state']=='COLLECTED' and manifest['ssh_exit_code']==0
assert sha((F/'results.tar').read_bytes())==manifest['results_sha256']
with tarfile.open(F/'inputs.tar') as t:
    inputs={n:member(t,n) for n in manifest['input_sha256']}
    assert all(sha(b)==manifest['input_sha256'][n] for n,b in inputs.items())
with tarfile.open(F/'results.tar') as t:
    assert all(member(t,n)==b for n,b in inputs.items())
    assert member(t,'exit-code.txt').strip()==b'0'
    assert b'ENGINEERING_RUN_COMPLETED' in member(t,'execution.log')
    log=member(t,'transient_des.log').decode()
    assert 'Sentaurus Device simulation finished' in log
    plt=member(t,'circuit.plt').decode()
    p=json.loads(member(t,'parameters.json'))
names=re.findall(r'"([^"]+)"',re.search(r'datasets\s*=\s*\[(.*?)\]',plt,re.S)[1])
vals=list(map(float,re.search(r'\bData\s*\{(.*?)\}',plt,re.S)[1].split()))
assert len(vals)%len(names)==0 and all(math.isfinite(x) for x in vals)
rows=[dict(zip(names,vals[i:i+len(names)])) for i in range(0,len(vals),len(names))]
assert all(b['time']>=a['time'] for a,b in zip(rows,rows[1:]))
groups={}
for r in rows:groups.setdefault(r['time'],[]).append(r)
duplicates=[]
for tm,rr in groups.items():
    if len(rr)>1:
        jumps={n:max(r[n] for r in rr)-min(r[n] for r in rr) for n in names if n.startswith('v(')}
        duplicates.append({'time':tm,'count':len(rr),'voltage_ranges':jumps})
        if tm>0:assert max(jumps.values())<=1e-6
def phase(lo,hi,cap,node,keys):
    rr=[rr for tm,rr in groups.items() if lo-1e-20<=tm<=hi+1e-20]
    out={}
    for mode in ('first','last'):
        r=[x[0 if mode=='first' else -1] for x in rr]
        delta=cap*(r[0]['v('+node+')']-r[-1]['v('+node+')'])
        integ=-sum((b['time']-a['time'])*sum(b[k] for k in keys) for a,b in zip(r,r[1:]))
        currents=keys+['i('+{'sn':'cstore','bl':'cbl','ref':'cref'}[node]+','+node+')']
        kcl=[sum(x[k] for k in currents) for x in r]
        idx=max(range(len(r)),key=lambda i:abs(kcl[i]))
        pointscale=max(abs(r[idx][k]) for k in currents)
        globalscale=max(abs(x[k]) for x in r for k in currents)
        out[mode]={'samples':len(r),'delta_C':delta,'BE_terminal_C':integ,'residual_C':abs(delta-integ),
          'residual_as_node_voltage_V':abs(delta-integ)/cap,'max_kcl_A':abs(kcl[idx]),
          'max_kcl_time_s':r[idx]['time'],'max_kcl_row':r[idx],
          'point_scale_A':pointscale,'global_scale_A':globalscale,
          'kcl_excluding_first_A':max(abs(v) for v in kcl[1:]),
          'kcl_excluding_both_endpoints_A':max(abs(v) for v in kcl[1:-1]),
          'BE_tolerance_C':max(1e-18,.001*abs(delta))}
    return out
sn=['i(access,sn)','i(rsn,sn)'];bl=['i(access,bl)','i(rbl,bl)','i(rpre,bl)']
phases={name:phase(lo,hi,c,n,k) for name,lo,hi,c,n,k in [
 ('sn_hold',.95e-9,2.8e-9,1e-14,'sn',sn),('sn_precharge',2.8e-9,3e-9,1e-14,'sn',sn),
 ('bl_precharge',2.8e-9,3e-9,1e-13,'bl',bl),('sn_read',3e-9,4e-9,1e-14,'sn',sn),
 ('bl_read',3e-9,4e-9,1e-13,'bl',bl)]}
last=rows[-1];d=last['v(bl)']-last['v(ref)']
out={'run_id':RID,'archive_sha256':manifest['results_sha256'],'input_count':len(inputs),
 'parameters':p,'samples':len(rows),'unique_times':len(groups),'duplicates':duplicates,
 'endpoint_rows':{str(tm):rr for tm,rr in groups.items() if any(abs(tm-v)<1e-20 for v in (.6e-9,.95e-9,2.8e-9,3e-9,4e-9))},
 'phases':phases,'D_V':d,'threshold_classes':{str(e):('correct' if d>e else 'uncertain' if d>=-e else 'flip') for e in (.0025,.005,.010)},
 'solver_finish':[x for x in log.splitlines() if 'Sentaurus Device simulation finished' in x],
 'script_sha256':sha(Path(__file__).read_bytes())}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'archive':out['archive_sha256'],'samples':len(rows),'unique_times':len(groups),'duplicates':duplicates,
 'D_V':d,'thresholds':out['threshold_classes'],'phase_summary':{n:{m:{k:v for k,v in a.items() if k!='max_kcl_row'} for m,a in z.items()} for n,z in phases.items()},
 'endpoint_3ns':out['endpoint_rows'].get('3e-09')},indent=2))
