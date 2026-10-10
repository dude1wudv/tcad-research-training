"""Generate one immutable, explicitly simplified 1T1C TCAD experiment input."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent

def build(out, length=.25, charge_pc=0., angle=0., mesh=1., step=1., event=None, restart_run=None):
    if out.exists():
        raise ValueError('Refuse to overwrite an existing input directory')
    if not (.15 <= length <= .5 and 0 <= charge_pc <= .1 and angle in (0,30) and .4 <= mesh <= 1 and .25 <= step <= 1):
        raise ValueError('Outside v1 approved exploratory parameter domain')
    out.mkdir(parents=True)
    width=length+.6; impact=length+.45; a=math.radians(angle)
    track=min(1.2/math.cos(a),impact/math.sin(a) if angle else float('inf'))
    params=dict(gate_length_um=length,charge_pc=charge_pc,angle_deg=angle,
        mesh_scale=mesh,step_scale=step,track_length_um=track,
        let_pc_per_um=charge_pc/track,capacitance_F=1e-14,
        effective_thickness_um=1,temperature_K=300,track_radius_um=.03,
        source_event=event,restart_run=restart_run,interpretation='Uncalibrated planar 1T1C prototype; not a process node')
    if charge_pc:
        from event_contract import validate_event
        root=HERE.parents[1]
        source=(root/event).resolve() if event else None
        if source is None or not source.is_relative_to(HERE/'data/geant4'):
            raise ValueError('Particle case requires a repository Geant4 event')
        actual=validate_event(source,{'gate_length_um':length,'angle_deg':angle})
        if not math.isclose(actual['converted'][0]['charge_pc'],charge_pc,rel_tol=1e-12):
            raise ValueError('TCAD charge does not match Geant4 event')
        copied={}
        for name,destination in [('event.json','source-event.json'),('steps.csv','source-steps.csv'),('events.csv','source-events.csv')]:
            content=(source.parent/name).read_bytes();(out/destination).write_bytes(content)
            copied[destination]=hashlib.sha256(content).hexdigest()
        params['source_evidence_sha256']=copied
    (out/'parameters.json').write_text(json.dumps(params,indent=2)+'\n',encoding='utf8')
    geometry=f'''; Original simplified planar access NMOS. Coordinates: um.
(sde:clear)
(sdegeo:set-default-boolean "ABA")
(sdegeo:create-rectangle (position 0 0 0) (position {width} 1.2 0) "Silicon" "R.Si")
(sdegeo:create-rectangle (position 0.3 -0.005 0) (position {length+.3} 0 0) "Oxide" "R.Ox")
(sdegeo:define-contact-set "source" 4 (color:rgb 1 0 0) "##")
(sdegeo:define-contact-set "drain" 4 (color:rgb 0 0 1) "##")
(sdegeo:define-contact-set "gate" 4 (color:rgb 0 1 0) "##")
(sdegeo:define-contact-set "body" 4 (color:rgb 0 0 0) "##")
(sdegeo:set-contact (find-edge-id (position 0.1 0 0)) "source")
(sdegeo:set-contact (find-edge-id (position {length+.5} 0 0)) "drain")
(sdegeo:set-contact (find-edge-id (position {length/2+.3} -0.005 0)) "gate")
(sdegeo:set-contact (find-edge-id (position {width/2} 1.2 0)) "body")
(sdedr:define-constant-profile "P.Body" "BoronActiveConcentration" 1e17)
(sdedr:define-constant-profile-region "P.Body.Place" "P.Body" "R.Si")
(sdedr:define-refeval-window "S.Base" "Line" (position 0 0 0) (position 0.27 0 0))
(sdedr:define-refeval-window "D.Base" "Line" (position {length+.33} 0 0) (position {width} 0 0))
(sdedr:define-gaussian-profile "N.SD" "ArsenicActiveConcentration" "PeakPos" 0 "PeakVal" 1e20 "ValueAtDepth" 1e17 "Depth" 0.12 "Gauss" "Factor" 0.4)
(sdedr:define-analytical-profile-placement "S.Place" "N.SD" "S.Base" "Positive" "NoReplace" "Eval")
(sdedr:define-analytical-profile-placement "D.Place" "N.SD" "D.Base" "Positive" "NoReplace" "Eval")
(sdedr:define-refeval-window "All" "Rectangle" (position 0 -0.005 0) (position {width} 1.2 0))
(sdedr:define-refinement-size "Mesh.All" {0.035*mesh} {0.035*mesh} {0.003*mesh} {0.002*mesh})
(sdedr:define-refinement-function "Mesh.All" "DopingConcentration" "MaxTransDiff" 1)
(sdedr:define-refinement-function "Mesh.All" "MaxLenInt" "Silicon" "Oxide" {0.002*mesh} 1.5 "DoubleSide")
(sdedr:define-refinement-placement "All.Place" "Mesh.All" "All")
(sdedr:define-refeval-window "Surface" "Rectangle" (position 0 0 0) (position {width} 0.16 0))
(sdedr:define-refinement-size "Mesh.Surface" {0.012*mesh} {0.008*mesh} {0.002*mesh} {0.001*mesh})
(sdedr:define-refinement-placement "Surface.Place" "Mesh.Surface" "Surface")
(sde:build-mesh "snmesh" "" "cell")
'''
    ion=f'''HeavyIon (
      StartPoint=({impact},0) Direction=({-math.sin(a)},{math.cos(a)})
      Time=1e-9 Length={track} Wt_hi=0.03 LET_f={charge_pc/track}
      Gaussian PicoCoulomb
    )''' if charge_pc else ''
    radiation_plots='HeavyIonChargeDensity HeavyIonGeneration' if charge_pc else ''
    radiation_current='CurrentPlot { HeavyIonGeneration(Integrate(Semiconductor)) }' if charge_pc else ''
    device=f'''Device Cell {{
 File {{ Grid="cell_msh.tdr" Current="device.plt" Plot="device.tdr" }}
 Electrode {{
  {{Name="source" Voltage=0}} {{Name="drain" Voltage=0}}
  {{Name="gate" Voltage=1.8 WorkFunction=4.6}} {{Name="body" Voltage=0}}
 }}
 Physics {{
  AreaFactor=1 Temperature=300 Fermi
  EffectiveIntrinsicDensity(OldSlotboom)
  Mobility(DopingDep HighFieldSaturation Enormal)
  Recombination(SRH(DopingDep) Auger)
  {ion}
 }}
}}
File {{ Output="transient" }}
Plot {{ eDensity hDensity Potential ElectricField/Vector Doping
 TotalCurrent/Vector eCurrent/Vector hCurrent/Vector
 {radiation_plots} }}
{radiation_current}
Math {{
 RelErrControl Digits=5 ErrRef(electron)=1e7 ErrRef(hole)=1e7
 Iterations=30 Notdamped=100 Transient=BE Method=Blocked SubMethod=ParDiSo
 ExitOnFailure
}}
System {{
 Cell access ("source"=bl "drain"=sn "gate"=wl "body"=0)
 Vsource_pset vbl (bl 0) {{ pwl=(0 1 0.4e-9 1 0.45e-9 0 3e-9 0) }}
 Vsource_pset vwl (wl 0) {{ pwl=(0 1.8 0.3e-9 1.8 0.35e-9 0 3e-9 0) }}
 Capacitor_pset cstore (sn 0) {{capacitance=1e-14}}
 Resistor_pset rleak (sn 0) {{resistance=1e20}}
 Set(sn=0)
 Plot "circuit.plt" (time() v(bl) v(wl) v(sn) i(access,sn) i(cstore,sn) i(rleak,sn))
}}
Solve {{
 Coupled(Iterations=100) {{ Poisson }}
 Coupled(Iterations=100) {{ Poisson Electron Hole Contact Circuit }}
 Unset(sn)
 Transient(InitialTime=0 FinalTime=0.95e-9 InitialStep=1e-14 MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
  Coupled {{ Poisson Electron Hole Contact Circuit }}
  Plot(FilePrefix="prestrike" Time=(0.95e-9))
  Save(FilePrefix="charged" Time=(0.95e-9))
 }}
 Transient(InitialTime=0.95e-9 FinalTime=1.05e-9 InitialStep={2e-13*step} MinStep=1e-18 MaxStep={1e-12*step} Increment=1.3) {{
  Coupled {{ Poisson Electron Hole Contact Circuit }}
  Plot(FilePrefix="strike" Time=(1e-9))
 }}
 Transient(InitialTime=1.05e-9 FinalTime=3e-9 InitialStep={1e-12*step} MinStep=1e-18 MaxStep={1e-11*step} Increment=1.4) {{
  Coupled {{ Poisson Electron Hole Contact Circuit }}
  Plot(FilePrefix="final" Time=(3e-9))
 }}
}}
'''
    if restart_run:
        import sys
        sys.path.insert(0,str(HERE))
        from analyze import read
        root=HERE.parents[1]
        run=root/'local_runtime/runs'/restart_run
        manifest=json.loads((run/'manifest.json').read_text())
        if manifest.get('state')!='COLLECTED' or manifest.get('ssh_exit_code')!=0:
            raise ValueError('Restart requires successfully archived parent')
        if hashlib.sha256((run/'results.tar').read_bytes()).hexdigest()!=manifest['results_sha256']:
            raise ValueError('Parent archive hash mismatch')
        with tarfile.open(run/'results.tar') as tf:
            parent=json.loads(read(tf,'parameters.json'))
            if parent.get('restart_run') or parent['gate_length_um']!=length or parent['mesh_scale']!=mesh:
                raise ValueError('Restart parent geometry mismatch or chained restart')
            names=[m.name.removeprefix('./') for m in tf.getmembers() if m.isfile() and m.name.removeprefix('./').startswith('charged') and m.name.endswith('.sav')]
            if len(names)<2:raise ValueError('Missing device/circuit save pair')
            copied={}
            for name in ['cell_msh.tdr']+names:
                if Path(name).name!=name:raise ValueError('Unsafe restart member')
                data=read(tf,name);(out/name).write_bytes(data);copied[name]=hashlib.sha256(data).hexdigest()
        (out/'restart-provenance.json').write_text(json.dumps({'parent_run':restart_run,'archive_sha256':manifest['results_sha256'],'time_s':.95e-9,'copied_sha256':copied},indent=2)+'\n')
        prefix=device.split('Solve {')[0].replace(' Set(sn=0)\n','')
        tail=device[device.index(' Transient(InitialTime=0.95e-9'):]
        device=prefix+'Solve {\n Load(FilePrefix="charged")\n Plot(FilePrefix="prestrike")\n'+tail
    (out/'geometry.scm').write_text(geometry,encoding='utf8')
    (out/'device.cmd').write_text(device,encoding='utf8')
    spec={'name':out.name,'steps':[
      {'tool':'sde','args':['-e','-l','geometry.scm'],'outputs':['cell_msh.tdr']},
      {'tool':'sdevice','args':['device.cmd'],'outputs':['circuit.plt','transient_des.log','final_access_des.tdr']} ]}
    if restart_run:spec['steps']=spec['steps'][1:]
    (out/'project.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf8')
    (out/'generator-sha256.txt').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()+'\n')
    return params

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--length',type=float,default=.25);p.add_argument('--charge-pc',type=float,default=0)
    p.add_argument('--angle',type=float,default=0);p.add_argument('--mesh',type=float,default=1)
    p.add_argument('--step',type=float,default=1);p.add_argument('--event');p.add_argument('--restart-run')
    a=p.parse_args();print(json.dumps(build(a.output,a.length,a.charge_pc,a.angle,a.mesh,a.step,a.event,a.restart_run),indent=2))
