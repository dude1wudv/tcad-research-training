"""Immutable v2 inputs, controlled initialization and finite-bitline readout."""
import argparse,hashlib,json,math,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'dram-see-v1'))
import build_case as v1_builder
# When executed as a script this import is v1; callers use importlib for this module.
from analyze import read
sys.path.insert(0,str(HERE))
from event_audit import validate_bytes

def build(out,length=.25,bit=1,event=None,parent=None,step=1.,mesh=1.):
    out=Path(out)
    if length not in (.18,.25,.35,.45) or bit not in (0,1) or step not in (1.,.5) or mesh not in (1.,.7):
        raise ValueError('Outside frozen v2 conditions')
    if out.exists():raise ValueError('Immutable input exists')
    v1_builder.build(out,length=length,mesh=mesh,step=step)
    target=.1 if bit==0 else .9
    p=dict(schema='dram-see-v2',gate_length_um=length,stored_bit=bit,target_voltage_V=target,
           initialization_tolerance_V=.001,capacitance_F=1e-14,bitline_capacitance_F=1e-13,
           reference_capacitance_F=1e-13,precharge_V=.5,read_threshold_V=.005,
           precharge_resistance_on_ohm=100,precharge_resistance_off_ohm=1e20,
           precharge_ramp_end_s=2.9e-9,precharge_tolerance_V=1e-5,
           mesh_scale=mesh,step_scale=step,prestrike_s=.95e-9,strike_s=1e-9,
           hold_end_s=2.8e-9,precharge_end_s=3e-9,read_sample_s=4e-9,
           effective_thickness_um=1,temperature_K=300,charge_pc=0.,angle_deg=0,
           parent_run=parent,initialization='ideal SN clamp released at 0.6 ns; not calibrated transistor write',
           interpretation='uncalibrated 1T1C, criterion readout error; no latch or restoration')
    ion='';rad='';cur=''
    if event:
        evpath=(ROOT/event).resolve()
        if not evpath.is_relative_to(HERE/'data/geant4'):raise ValueError('Need v2 event')
        data={n:(evpath.parent/n).read_bytes() for n in ('steps.csv','events.csv')}
        ev=validate_bytes(evpath.read_bytes(),data,{'gate_length_um':length,'angle_deg':0})
        q=ev['converted'][0]['charge_pc'];track=ev['converted'][0]['track_length_um']
        p.update(charge_pc=q,track_length_um=track,let_pc_per_um=q/track,source_event=event,
                 seed=ev['seed'],particle=ev['particle'],energy_MeV=ev['energy_MeV'],event_id=0,
                 impact_x_um=length+.45,direction=[0,1,0],track_radius_um=.03)
        p['source_evidence_sha256']={}
        for src,dst in [('event.json','source-event.json'),('steps.csv','source-steps.csv'),('events.csv','source-events.csv')]:
            b=(evpath.parent/src).read_bytes();(out/dst).write_bytes(b)
            p['source_evidence_sha256'][dst]=hashlib.sha256(b).hexdigest()
        if q>0:
            ion=f'HeavyIon ( StartPoint=({length+.45},0) Direction=(0,1) Time=1e-9 Length={track} Wt_hi=0.03 LET_f={q/track} Gaussian PicoCoulomb )'
            rad='HeavyIonChargeDensity HeavyIonGeneration';cur='CurrentPlot { HeavyIonGeneration(Integrate(Semiconductor)) }'
    device=f'''Device Cell {{
 File {{ Grid="cell_msh.tdr" Current="device.plt" Plot="device.tdr" }}
 Electrode {{ {{Name="source" Voltage=0}} {{Name="drain" Voltage=0}} {{Name="gate" Voltage=0 WorkFunction=4.6}} {{Name="body" Voltage=0}} }}
 Physics {{ AreaFactor=1 Temperature=300 Fermi EffectiveIntrinsicDensity(OldSlotboom)
 Mobility(DopingDep HighFieldSaturation Enormal) Recombination(SRH(DopingDep) Auger) {ion} }}
}}
File {{ Output="transient" }}
Plot {{ eDensity hDensity Potential ElectricField/Vector Doping TotalCurrent/Vector eCurrent/Vector hCurrent/Vector {rad} }}
{cur}
Math {{ RelErrControl Digits=5 ErrRef(electron)=1e7 ErrRef(hole)=1e7 Iterations=30 Notdamped=100
 Transient=BE Method=Blocked SubMethod=ParDiSo ExitOnFailure }}
System {{
 Cell access ("source"=bl "drain"=sn "gate"=wl "body"=0)
 Vsource_pset vwl (wl 0) {{pwl=(0 0 3.05e-9 0 3.10e-9 1.8 4e-9 1.8)}}
 Vsource_pset vpre (pre 0) {{pwl=(0 0 2.8e-9 0 2.9e-9 0.5 4e-9 0.5)}}
 Resistor_pset rpre (bl pre) {{resistance=100}}
 Capacitor_pset cstore (sn 0) {{capacitance=1e-14}}
 Capacitor_pset cbl (bl 0) {{capacitance=1e-13}}
 Capacitor_pset cref (ref 0) {{capacitance=1e-13}}
 Resistor_pset rsn (sn 0) {{resistance=1e20}}
 Resistor_pset rbl (bl 0) {{resistance=1e20}}
 Resistor_pset rref (ref 0) {{resistance=1e20}}
 Set(sn={target} bl=0 ref=0.5)
 Plot "circuit.plt" (time() v(bl) v(wl) v(sn) v(ref) i(access,sn) i(access,bl)
 i(cstore,sn) i(cbl,bl) i(cref,ref) i(rsn,sn) i(rbl,bl) i(rref,ref) i(rpre,bl))
}}
Solve {{
 Coupled(Iterations=100) {{Poisson}}
 Coupled(Iterations=100) {{Poisson Electron Hole Contact Circuit}}
 Transient(InitialTime=0 FinalTime=0.6e-9 InitialStep=1e-14 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{Coupled {{Poisson Electron Hole Contact Circuit}}}}
 Unset(sn)
 Transient(InitialTime=0.6e-9 FinalTime=0.95e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}}
 Plot(FilePrefix="prestrike" Time=(0.95e-9)) Save(FilePrefix="charged" Time=(0.95e-9))
 }}
 Transient(InitialTime=0.95e-9 FinalTime=1.05e-9 InitialStep={2e-13*step} MinStep=1e-18 MaxStep={1e-12*step} Increment=1.3) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="strike" Time=(1e-9))
 }}
 Transient(InitialTime=1.05e-9 FinalTime=2.8e-9 InitialStep={1e-12*step} MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="hold" Time=(2.8e-9))
 }}
 Unset(bl)
 Transient(InitialTime=2.8e-9 FinalTime=3e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-12*step} Increment=1.4) {{Coupled {{Poisson Electron Hole Contact Circuit}}}}
 Set(rpre."resistance"=1e20)
 Unset(ref)
 Transient(InitialTime=3e-9 FinalTime=4e-9 InitialStep=1e-13 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
 Coupled {{Poisson Electron Hole Contact Circuit}} Plot(FilePrefix="final" Time=(4e-9))
 }}
}}
'''
    if parent:
        folder=ROOT/'local_runtime/runs'/parent
        m=json.loads((folder/'manifest.json').read_text())
        if m['state']!='COLLECTED' or m['ssh_exit_code']!=0:raise ValueError('Unsuccessful parent')
        if hashlib.sha256((folder/'results.tar').read_bytes()).hexdigest()!=m['results_sha256']:raise ValueError('Parent hash')
        with tarfile.open(folder/'results.tar') as tf:
            old=json.loads(read(tf,'parameters.json'))
            for key in ('schema','gate_length_um','stored_bit','mesh_scale','step_scale','target_voltage_V','bitline_capacitance_F','read_threshold_V'):
                if old[key]!=p[key]:raise ValueError('Parent incompatible '+key)
            if old['parent_run'] or old['charge_pc']:raise ValueError('Need full unirradiated parent')
            copied={}
            for name in ('cell_msh.tdr','charged_access_des.sav','charged_circuit_des.sav'):
                data=read(tf,name);(out/name).write_bytes(data);copied[name]=hashlib.sha256(data).hexdigest()
        (out/'restart-provenance.json').write_text(json.dumps({'parent_run':parent,'archive_sha256':m['results_sha256'],'time_s':.95e-9,'copied_sha256':copied},indent=2)+'\n')
        start=device.index('Solve {')
        prefix=device[:start].replace(f' Set(sn={target} bl=0 ref=0.5)\n','')
        tail=device[device.index(' Transient(InitialTime=0.95e-9'):]
        device=prefix+'Solve {\n Load(FilePrefix="charged")\n Set(bl=0 ref=0.5)\n Plot(FilePrefix="prestrike")\n'+tail
    (out/'device.cmd').write_text(device,encoding='utf8')
    contract={k:p[k] for k in ('schema','gate_length_um','stored_bit','target_voltage_V','initialization_tolerance_V',
        'capacitance_F','bitline_capacitance_F','reference_capacitance_F','precharge_V','read_threshold_V',
        'precharge_resistance_on_ohm','precharge_resistance_off_ohm','precharge_ramp_end_s','precharge_tolerance_V',
        'mesh_scale','step_scale','prestrike_s','strike_s','hold_end_s','precharge_end_s','read_sample_s',
        'effective_thickness_um','temperature_K','initialization')}
    contract['geometry_sha256']=hashlib.sha256((out/'geometry.scm').read_bytes()).hexdigest()
    contract['physics']='Fermi OldSlotboom Mobility(DopingDep HighFieldSaturation Enormal) SRH(DopingDep) Auger; Digits5 ErrRef1e7; BE Blocked ParDiSo; gate_work_function4.6'
    contract['circuit_revision']='v2-finite-ramp-rpre100-off1e20-wl0-initialize-read3.05to3.10ns-1.8V-snclamp-release0.6ns'
    p['model_contract_sha256']=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
    p['model_contract']=contract
    if parent and old.get('model_contract_sha256')!=p['model_contract_sha256']:
        raise ValueError('Full frozen model contract differs from parent')
    (out/'parameters.json').write_text(json.dumps(p,indent=2)+'\n')
    spec=json.loads((out/'project.json').read_text());spec['steps'][-1]['outputs']=['circuit.plt','transient_des.log','final_access_des.tdr']
    if parent:spec['steps']=spec['steps'][1:]
    (out/'project.json').write_text(json.dumps(spec,indent=2)+'\n')
    (out/'generator-sha256.txt').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()+'\n')
    (out/'geometry-generator-sha256.txt').write_text(hashlib.sha256((HERE.parent/'dram-see-v1/build_case.py').read_bytes()).hexdigest()+'\n')
    return p

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('out',type=Path);a.add_argument('--length',type=float,default=.25)
    a.add_argument('--bit',type=int,default=1);a.add_argument('--event');a.add_argument('--parent')
    a.add_argument('--step',type=float,default=1);a.add_argument('--mesh',type=float,default=1)
    args=a.parse_args();print(json.dumps(build(args.out,args.length,args.bit,args.event,args.parent,args.step,args.mesh),indent=2))
