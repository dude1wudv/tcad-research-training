"""Run and collect one real Geant4 condition via the existing pinned SSH configuration."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shlex
import subprocess
import tarfile
from operate import remote, ROOT, tcad

HERE=Path(__file__).resolve().parent
Q_E=1.602176634e-19

def run(label,length,particle,energy,angle,seed=20261009,events=1):
    if particle not in ('alpha','proton') or not (.15<=length<=.5 and 1<=energy<=10 and angle in (0,30) and 1<=events<=10):
        raise ValueError('Transport outside v1 bounds')
    if not __import__('re').fullmatch('[a-z0-9-]+',label):raise ValueError('Invalid label')
    out=HERE/'data/geant4'/label
    if out.exists():raise ValueError('Immutable event directory exists')
    cfg,ssh,ip=tcad.connection();base=cfg['remote_root']+'/dram-see-v1'
    directory=base+'/events/'+label
    command=' '.join(map(shlex.quote,[base+'/build/transport',str(length),particle,str(energy),str(angle),str(seed),str(events)]))
    script='set -eu\nsource '+shlex.quote(base+'/env.sh')+'\nmkdir -p '+shlex.quote(base+'/events')+'\nmkdir '+shlex.quote(directory)+'\ncd '+shlex.quote(directory)+'\n'+command+'\n'
    record,op=remote('g4-'+label,script,120)
    if record['exit_code']!=0:raise RuntimeError('Geant4 failed; inspect '+str(op))
    if 'TRANSPORT_COMPLETED events='+str(events) not in (op/'stdout.txt').read_text():raise ValueError('Missing transport completion')
    result=subprocess.run(ssh+['tar -cf - -C '+shlex.quote(directory)+' events.csv steps.csv'],capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError('Event collection failed')
    out.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        for name in ('events.csv','steps.csv'):
            (out/name).write_bytes(archive.extractfile(name).read())
    rows=list(csv.DictReader((out/'events.csv').open()))
    steps=list(csv.DictReader((out/'steps.csv').open()))
    if len(rows)!=events:raise ValueError('Wrong event count')
    converted=[]
    for row in rows:
        event=int(row['event']);ed=float(row['ionizing_MeV'])
        total=sum(float(s['ionizing_MeV']) for s in steps if int(s['event'])==event)
        if not (math.isfinite(ed) and 0<ed<=energy and math.isclose(total,ed,rel_tol=1e-10)):
            raise ValueError('Energy accounting failed')
        q=ed*1e6/3.6*Q_E*1e12
        a=math.radians(angle)
        track=min(1.2/math.cos(a),(length+.45)/math.sin(a) if angle else float('inf'))
        converted.append({'event':event,'ionizing_MeV':ed,'charge_pc':q,'track_length_um':track,'let_pc_per_um':q/track,
                          'step_sum_relative_error':abs(total-ed)/ed})
    metadata={'label':label,'gate_length_um':length,'particle':particle,'energy_MeV':energy,'angle_deg':angle,
              'seed':seed,'event_count':events,'conversion_eV_per_pair':3.6,'converted':converted,
              'source_sha256':hashlib.sha256((HERE/'geant4_transport.cc').read_bytes()).hexdigest(),
              'files_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.glob('*.csv')},
              'command':command.replace(base,'${EXPERIMENT_ROOT}'),'operation_exit_code':record['exit_code'],
              'scope':'EM-only slab event, projected to uniform straight track; not full 3D deposition mapping'}
    (out/'event.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    return metadata

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--length',type=float,required=True)
    p.add_argument('--particle',choices=['alpha','proton'],required=True);p.add_argument('--energy',type=float,default=5)
    p.add_argument('--angle',type=float,default=0);p.add_argument('--seed',type=int,default=20261009);p.add_argument('--events',type=int,default=1)
    a=p.parse_args();print(json.dumps(run(a.label,a.length,a.particle,a.energy,a.angle,a.seed,a.events),indent=2))
