File {
  Grid = "diode_msh.tdr"
  Current = "diode"
  Plot = "diode"
  Output = "diode"
}
Electrode {
  { Name = "anode" Voltage = 0.0 }
  { Name = "cathode" Voltage = 0.0 }
}
Physics {
  Fermi
  Mobility(DopingDep)
  Recombination(SRH)
}
Plot {
  Potential SpaceCharge ElectricField/Vector
  eDensity hDensity Doping
  eCurrent/Vector hCurrent/Vector
}
Math {
  Number_Of_Threads = 1
  Extrapolate
  RelErrControl
  Digits = 5
  Iterations = 30
}
Solve {
  Coupled(Iterations=100) { Poisson }
  Coupled { Poisson Electron Hole }
  Quasistationary(
    InitialStep=0.01 Increment=1.4 MinStep=1e-6 MaxStep=0.1
    Goal { Name="anode" Voltage=0.5 }
  ) { Coupled { Poisson Electron Hole } }
}
