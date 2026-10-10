Device Cell {
 File { Grid="cell_msh.tdr" Current="device.plt" Plot="device.tdr" }
 Electrode {
  {Name="source" Voltage=0} {Name="drain" Voltage=0}
  {Name="gate" Voltage=1.8 WorkFunction=4.6} {Name="body" Voltage=0}
 }
 Physics {
  AreaFactor=1 Temperature=300 Fermi
  EffectiveIntrinsicDensity(OldSlotboom)
  Mobility(DopingDep HighFieldSaturation Enormal)
  Recombination(SRH(DopingDep) Auger)
  HeavyIon (
      StartPoint=(0.7,0) Direction=(-0.0,1.0)
      Time=1e-9 Length=1.2 Wt_hi=0.03 LET_f=0.006382836329271379
      Gaussian PicoCoulomb
    )
 }
}
File { Output="transient" }
Plot { eDensity hDensity Potential ElectricField/Vector Doping
 TotalCurrent/Vector eCurrent/Vector hCurrent/Vector
 HeavyIonChargeDensity HeavyIonGeneration }
CurrentPlot { HeavyIonGeneration(Integrate(Semiconductor)) }
Math {
 RelErrControl Digits=5 ErrRef(electron)=1e7 ErrRef(hole)=1e7
 Iterations=30 Notdamped=100 Transient=BE Method=Blocked SubMethod=ParDiSo
 ExitOnFailure
}
System {
 Cell access ("source"=bl "drain"=sn "gate"=wl "body"=0)
 Vsource_pset vbl (bl 0) { pwl=(0 1 0.4e-9 1 0.45e-9 0 3e-9 0) }
 Vsource_pset vwl (wl 0) { pwl=(0 1.8 0.3e-9 1.8 0.35e-9 0 3e-9 0) }
 Capacitor_pset cstore (sn 0) {capacitance=1e-14}
 Resistor_pset rleak (sn 0) {resistance=1e20}
 Set(sn=0)
 Plot "circuit.plt" (time() v(bl) v(wl) v(sn) i(access,sn) i(cstore,sn) i(rleak,sn))
}
Solve {
 Coupled(Iterations=100) { Poisson }
 Coupled(Iterations=100) { Poisson Electron Hole Contact Circuit }
 Unset(sn)
 Transient(InitialTime=0 FinalTime=0.95e-9 InitialStep=1e-14 MinStep=1e-18 MaxStep=1e-11 Increment=1.4) {
  Coupled { Poisson Electron Hole Contact Circuit }
  Plot(FilePrefix="prestrike" Time=(0.95e-9))
  Save(FilePrefix="charged" Time=(0.95e-9))
 }
 Transient(InitialTime=0.95e-9 FinalTime=1.05e-9 InitialStep=2e-13 MinStep=1e-18 MaxStep=1e-12 Increment=1.3) {
  Coupled { Poisson Electron Hole Contact Circuit }
  Plot(FilePrefix="strike" Time=(1e-9))
 }
 Transient(InitialTime=1.05e-9 FinalTime=3e-9 InitialStep=1e-12 MinStep=1e-18 MaxStep=1e-11 Increment=1.4) {
  Coupled { Poisson Electron Hole Contact Circuit }
  Plot(FilePrefix="final" Time=(3e-9))
 }
}
