"""Reuse verified installed Geant4 executable in immutable v2 event directories."""
import argparse,csv,hashlib,io,json,math,shlex,subprocess,tarfile
from pathlib import Path
from operate import remote,ROOT,tcad
from event_audit import validate_bytes
HERE=Path(__file__).resolve().parent
BINARY_SHA='830cd8480bc11a27b243f6662d0e64a71d5b382a45bfd1e80f8e199bfdfdb67f'
def run(label,length,particle,seed):
    if length not in (.18,.25,.35,.45) or particle not in ('alpha','proton') or not 0<seed<2147483647:raise ValueError('Bad condition')
    if not __import__('re').fullmatch('[a-z0-9-]+',label):raise ValueError('Bad label')
    out=HERE/'data/geant4'/label
    if out.exists():raise ValueError('Immutable event exists')
    cfg,ssh,_=tcad.connection();old=cfg['remote_root']+'/dram-see-v1';base=cfg['remote_root']+'/dram-see-v2'
    directory=base+'/events/'+label
    command=' '.join(map(shlex.quote,[old+'/build/transport',str(length),particle,'5','0',str(seed),'1']))
    script='set -eu\nsource '+shlex.quote(old+'/env.sh')+'\nactual=$(sha256sum '+shlex.quote(old+'/build/transport')+' | cut -d " " -f1)\ntest "$actual" = '+BINARY_SHA+'\nmkdir -p '+shlex.quote(base+'/events')+'\nmkdir '+shlex.quote(directory)+'\ncd '+shlex.quote(directory)+'\n'+command+'\n'
    rec,op=remote('g4-'+label,script,120)
    if rec['exit_code']!=0 or 'TRANSPORT_COMPLETED events=1' not in (op/'stdout.txt').read_text():raise ValueError('Transport failed')
    result=subprocess.run(ssh+['tar -cf - -C '+shlex.quote(directory)+' events.csv steps.csv'],capture_output=True,timeout=60,check=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tf:
        files={n:tf.extractfile(n).read() for n in ('steps.csv','events.csv')}
    rows=list(csv.DictReader(io.StringIO(files['events.csv'].decode())))
    if len(rows)!=1:raise ValueError('Bad count')
    e=float(rows[0]['ionizing_MeV']);q=e*1e6/3.6*1.602176634e-19*1e12
    meta={'schema':'dram-see-v2','label':label,'gate_length_um':length,'particle':particle,'energy_MeV':5.,'angle_deg':0,
          'seed':seed,'event_count':1,'surface_impact_um':[length+.45,0,0],'launch_position_um':[length+.45,-.001,0],
          'direction':[0,1,0],'conversion_eV_per_pair':3.6,'converted':[{'event':0,'ionizing_MeV':e,'charge_pc':q,'track_length_um':1.2,'let_pc_per_um':q/1.2}],
          'source_sha256':hashlib.sha256((HERE.parent/'dram-see-v1/geant4_transport.cc').read_bytes()).hexdigest(),
          'binary_sha256':BINARY_SHA,'files_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()},
          'operation_exit_code':rec['exit_code'],'operation_label':rec['label'],'command':command.replace(old,'${V1_INSTALLED_ROOT}'),
          'scope':'independent random seed; fixed position/energy/angle; EM-only uniform equivalent track'}
    validate_bytes(json.dumps(meta).encode(),files)
    out.mkdir(parents=True)
    for n,b in files.items():(out/n).write_bytes(b)
    (out/'event.json').write_text(json.dumps(meta,indent=2)+'\n')
    return meta
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('label');a.add_argument('--length',type=float,required=True);a.add_argument('--particle',required=True)
    a.add_argument('--seed',type=int,required=True);v=a.parse_args();print(json.dumps(run(v.label,v.length,v.particle,v.seed),indent=2))
