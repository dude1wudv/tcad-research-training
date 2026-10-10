"""Independent no-particle diagnosis, derived from immutable archived v2 baseline."""
import hashlib,json,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'dram-see-v1'))
from analyze import read
BASE='20261010T014743Z-v2-base-l025-b1-143253c7'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(case,out):
    out=Path(out)
    if out.exists():raise ValueError('Immutable input already exists')
    folder=ROOT/'local_runtime/runs'/BASE;m=json.loads((folder/'manifest.json').read_text())
    if m['state']!='COLLECTED' or m['ssh_exit_code'] or sha(folder/'results.tar')!=m['results_sha256']:raise ValueError('Baseline provenance')
    with tarfile.open(folder/'results.tar') as tf:
        deck=read(tf,'device.cmd').decode().replace('\r\n','\n');source={n:read(tf,n) for n in ('geometry.scm','cell_msh.tdr')}
        original=json.loads(read(tf,'parameters.json'))
    target=case['sn_target_V'];variant=case['variant']
    if variant not in ('standard','wl_off','wl_slow','matched_ref') or not 0<target<1:raise ValueError('Unknown diagnostic condition')
    assert deck.count('Set(sn=0.9 bl=0 ref=0.5)')==1
    deck=deck.replace('Set(sn=0.9 bl=0 ref=0.5)',f'Set(sn={target:.16g} bl=0 ref=0.5)')
    def replace_once(old,new):
        nonlocal deck
        if deck.count(old)!=1:raise ValueError('Ambiguous inherited template token '+old)
        deck=deck.replace(old,new)
    if variant=='wl_off':replace_once('3.10e-9 1.8 4e-9 1.8','3.10e-9 0 4e-9 0')
    if variant=='wl_slow':replace_once('3.10e-9 1.8','3.25e-9 1.8')
    if variant=='matched_ref':
        replace_once(' Vsource_pset vwl', ''' Cell reference ("source"=ref "drain"=snr "gate"=wl "body"=0)
 Capacitor_pset cstoreref (snr 0) {capacitance=1e-14}
 Resistor_pset rsnr (snr 0) {resistance=1e20}
 Resistor_pset rpreref (ref pre) {resistance=100}
 Vsource_pset vwl''')
        replace_once(f'Set(sn={target:.16g} bl=0 ref=0.5)',f'Set(sn={target:.16g} bl=0 ref=0 snr=0.5)')
        replace_once(' Unset(sn)',' Unset(sn)\n Unset(snr)')
        replace_once(' Unset(bl)',' Unset(bl)\n Unset(ref)')
        replace_once(' Set(rpre."resistance"=1e20)\n Unset(ref)',' Set(rpre."resistance"=1e20)\n Set(rpreref."resistance"=1e20)')
        replace_once('i(rpre,bl))','i(rpre,bl) v(snr) i(reference,snr) i(reference,ref) i(cstoreref,snr) i(rsnr,snr) i(rpreref,ref))')
    p={'schema':'dram-readout-offset-d1','case':case,'base_run_id':BASE,'base_results_sha256':m['results_sha256'],
       'inherited_v2_parameters':original,'sn_target_V':target,'variant':variant,'particle':None,
       'reference_cell_SN_target_V':.5 if variant=='matched_ref' else None,
       'independent_particle_events':0,'scope':'deterministic diagnostic; does not replace pilot or its thresholds',
       'frozen_geometry_sha256':hashlib.sha256(source['geometry.scm']).hexdigest(),
       'frozen_mesh_sha256':hashlib.sha256(source['cell_msh.tdr']).hexdigest(),
       'builder_sha256':sha(__file__)}
    out.mkdir(parents=True)
    for n,b in source.items():(out/n).write_bytes(b)
    (out/'device.cmd').write_text(deck,encoding='utf8')
    (out/'parameters.json').write_text(json.dumps(p,indent=2)+'\n')
    outputs=['circuit.plt','access_device.plt','transient_des.log','final_access_des.tdr']
    if variant=='matched_ref':outputs+=['reference_device.plt','final_reference_des.tdr']
    (out/'project.json').write_text(json.dumps({'name':case['tag'],'steps':[{'tool':'sdevice','args':['device.cmd'],'outputs':outputs}]},indent=2)+'\n')
    return p
