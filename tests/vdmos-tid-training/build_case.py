"""Generate a new immutable input project; run it with scripts/tcad.py, not this file."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def device_command(dose, mode, step_scale):
    not_density = 5e10 + 2.43e9 * dose
    nit_each = (1e10 + 2e9 * dose) / 2
    bv = mode == 'breakdown'
    resistor = ' Resistor=1e7' if bv else ''
    avalanche = ' Avalanche(ElectricField)' if bv else ''
    bv_math = 'AvalDerivatives\n  BreakCriteria { Current(Contact="drain" AbsVal=5e-6) }' if bv else ''
    if bv:
        sweep = f'''Quasistationary(
    InitialStep=1e-5 Increment=1.35 Decrement=2 MinStep=1e-10 MaxStep={0.005 * step_scale:.9g}
    Goal {{ Name="drain" Voltage=1000 }}
  ) {{ Coupled {{ Poisson Electron Hole }} }}'''
    else:
        sweep = f'''Quasistationary(
    InitialStep=0.02 Increment=1.4 MinStep=1e-7 MaxStep=0.2
    Goal {{ Name="drain" Voltage=0.1 }}
  ) {{ Coupled {{ Poisson Electron Hole }} }}
  NewCurrentPrefix="idvg_"
  Quasistationary(
    InitialStep=0.001 Increment=1.3 Decrement=2 MinStep=1e-8 MaxStep={0.01 * step_scale:.9g}
    Goal {{ Name="gate" Voltage=10 }}
  ) {{ Coupled {{ Poisson Electron Hole }} }}'''
    return f'''* Post-TID effective defect scenario: {dose:g} krad(SiO2); uncalibrated training.
File {{
  Grid="vdmos_msh.tdr"
  Current="{mode}"
  Plot="{mode}"
  Output="{mode}"
}}
Electrode {{
  {{ Name="source" Voltage=0 }}
  {{ Name="drain" Voltage=0{resistor} }}
  {{ Name="gate" Voltage=0 Barrier=-0.55 }}
}}
Physics {{
  AreaFactor=1
  Temperature=300
  Fermi
  EffectiveIntrinsicDensity(OldSlotboom)
  Mobility(DopingDep Enormal HighFieldSaturation)
  Recombination(SRH(DopingDep){avalanche})
}}
Physics(MaterialInterface="Silicon/Oxide") {{
  Traps(
    (FixedCharge Conc={not_density:.12g})
    (Donor Level fromMidBandGap EnergyMid=-0.25 Conc={nit_each:.12g} eXsection=1e-15 hXsection=1e-15)
    (Acceptor Level fromMidBandGap EnergyMid=0.25 Conc={nit_each:.12g} eXsection=1e-15 hXsection=1e-15)
  )
}}
Plot {{
  Doping DonorConcentration AcceptorConcentration
  Potential SpaceCharge ElectricField/Vector
  eDensity hDensity eCurrent/Vector hCurrent/Vector
  SRH eMobility hMobility
  eInterfaceTrappedCharge hInterfaceTrappedCharge
  TotalInterfaceTrapConcentration
  ImpactIonization
}}
CurrentPlot {{
  ElectricField(Maximum(Semiconductor Coordinates))
  ImpactIonization(Integrate(Semiconductor))
}}
Math {{
  Number_Of_Threads=1
  Extrapolate
  RelErrControl
  Digits=5
  Iterations=30
  ErrRef(Electron)=1e8
  ErrRef(Hole)=1e8
  {bv_math}
}}
Solve {{
  Coupled(Iterations=100) {{ Poisson }}
  Coupled(Iterations=100) {{ Poisson Electron Hole }}
  {sweep}
}}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--dose', type=float, required=True)
    parser.add_argument('--mesh-scale', type=float, default=1.0)
    parser.add_argument('--step-scale', type=float, default=1.0)
    args = parser.parse_args()
    if not 0 <= args.dose <= 60 or not 0 < args.mesh_scale <= 2 or not 0 < args.step_scale <= 2:
        parser.error('Dose must be 0..60 krad and numeric scales must be >0 and <=2')
    args.output.mkdir(parents=True, exist_ok=False)
    geometry = (HERE / 'model/geometry.scm').read_text(encoding='utf-8')
    geometry = geometry.replace('@MESH_SCALE@', format(args.mesh_scale, '.9g'))
    files = {'geometry.scm': geometry,
             'idvg.cmd': device_command(args.dose, 'transfer', args.step_scale),
             'breakdown.cmd': device_command(args.dose, 'breakdown', args.step_scale)}
    for name, text in files.items():
        (args.output / name).write_text(text, encoding='utf-8', newline='\n')
    parameters = {'dose_krad_SiO2': args.dose, 'not_cm2': 5e10 + 2.43e9 * args.dose,
                  'nit_total_cm2': 1e10 + 2e9 * args.dose,
                  'mesh_scale': args.mesh_scale, 'step_scale': args.step_scale,
                  'area_factor': 1, 'current_unit': 'A/um; 2D half-cell, unit depth',
                  'interpretation': 'Uncalibrated post-TID effective-defect training model',
                  'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    project = {'name': 'vdmos-tid-' + args.output.name.lower().replace('_', '-'),
               'purpose': parameters['interpretation'],
               'steps': [
                   {'tool': 'sde', 'args': ['-e', '-l', 'geometry.scm'], 'outputs': ['vdmos_msh.tdr']},
                   {'tool': 'sdevice', 'args': ['idvg.cmd'], 'outputs': ['idvg_transfer_des.plt', 'transfer_des.tdr', 'transfer_des.log']},
                   {'tool': 'sdevice', 'args': ['breakdown.cmd'], 'outputs': ['breakdown_des.plt', 'breakdown_des.tdr', 'breakdown_des.log']}]}
    for name, value in [('parameters.json', parameters), ('project.json', project)]:
        (args.output / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
