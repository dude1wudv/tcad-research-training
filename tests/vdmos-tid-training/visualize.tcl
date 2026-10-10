# Run in a completed run directory on the logged-in guest desktop.
# svisual -tcl -script visualize.tcl
# Same run mesh and final breakdown TDR; no fabricated device geometry.
set mesh [load_file vdmos_msh.tdr]
set structure [create_plot -dataset $mesh]
set_plot_prop -plot $structure -title "VDMOS half-cell: real mesh, dimensions in um"
foreach f [list_fields -plot $structure -show] {
  set_field_prop -plot $structure -geom $mesh $f -hide -hide_bands
}
set_field_prop -plot $structure -geom $mesh DopingConcentration -show -show_bands -scale asinh -levels 41
zoom_plot -plot $structure -reset
export_view structure.png -plots $structure -resolution 1600x900 -format PNG -overwrite
set surface [create_cutline -plot $structure -type y -at 0.01]
export_variables {X DopingConcentration} -dataset $surface -filename surface-doping.csv -overwrite
foreach x {0.15 0.9 2.5 4.5} {
  set cut [create_cutline -plot $structure -type x -at $x]
  export_variables {Y DopingConcentration} -dataset $cut -filename "depth-doping-$x.csv" -overwrite
}
set data [load_file breakdown_des.tdr]
set field [create_plot -dataset $data]
set_plot_prop -plot $field -title "VDMOS final off-state solution; consult same-run PLT for internal VDS"
foreach f [list_fields -plot $field -show] {
  set_field_prop -plot $field -geom $data $f -hide -hide_bands
}
set_field_prop -plot $field -geom $data Abs(ElectricField-V) -show -show_bands -levels 41
zoom_plot -plot $field -reset
export_view electric-field.png -plots $field -resolution 1600x900 -format PNG -overwrite
set interface [create_cutline -plot $field -type y -at 0]
export_variables {X eInterfaceTrappedCharge hInterfaceTrappedCharge TotalInterfaceTrapConcentration} -dataset $interface -filename interface-fields.csv -overwrite
set proof [open visual-proof.txt w]
puts $proof [list_fields -dataset $data]
puts $proof "native exports completed"
close $proof
# Keep actual GUI open. Exports and screenshots are different evidence.
