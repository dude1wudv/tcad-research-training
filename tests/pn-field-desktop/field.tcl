# Run in the completed run directory: svisual -tcl -script field.tcl
# Data are the final converged -2 V solution, not a synthetic rendering.
set data [load_file diode_des.tdr]
set plot [create_plot -dataset $data]
set_plot_prop -plot $plot -title "PN junction: NA=5e16 cm^-3, ND=1e16 cm^-3, Va=-2 V"
set_field_prop -plot $plot -geom $data Abs(ElectricField-V) -show_bands -levels 41
export_view electric-field.png -plots $plot -resolution 1600x1000 -format PNG -overwrite
# Keep the GUI open for actual desktop screenshot and human inspection.
