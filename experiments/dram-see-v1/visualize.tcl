# Native GUI evidence. Run in the completed TCAD run's directory.
proc style_export {plot filename} {
  set_plot_prop -plot $plot -title_font_factor 2
  zoom_plot -plot $plot -reset
  set_legend_prop -plot $plot -position {0.66 0.68} -size {0.025 0.35} -label_font_factor 3 -title_font_factor 2 -nof_labels 6 -precision 2
  export_view $filename -plots $plot -resolution 1400x1000 -format PNG -overwrite
  zoom_plot -plot $plot -reset
  set_plot_prop -plot $plot -title_font_factor 1
  set_legend_prop -plot $plot -reset
}
set mesh [load_file cell_msh.tdr]
set structure [create_plot -dataset $mesh]
set_plot_prop -plot $structure -title "Access NMOS: net doping (cm^-3); coordinates in um"
foreach f [list_fields -plot $structure -show] {
  set_field_prop -plot $structure -geom $mesh $f -hide -hide_bands
}
set_field_prop -plot $structure -geom $mesh DopingConcentration -show -show_bands -scale asinh -levels 41
set struck [load_file strike_access_des.tdr]
set field [create_plot -dataset $struck]
set_plot_prop -plot $field -title "Real TCAD solution at particle time 1 ns: electric field (V/cm)"
foreach f [list_fields -plot $field -show] {
  set_field_prop -plot $field -geom $struck $f -hide -hide_bands
}
set_field_prop -plot $field -geom $struck Abs(ElectricField-V) -show -show_bands -scale log -levels 41
set density [create_plot -dataset $struck]
set_plot_prop -plot $density -title "Real particle-time solution: electron density (cm^-3)"
foreach f [list_fields -plot $density -show] {
  set_field_prop -plot $density -geom $struck $f -hide -hide_bands
}
set_field_prop -plot $density -geom $struck eDensity -show -show_bands -scale log -levels 41
set grid [create_plot -dataset $mesh]
set_plot_prop -plot $grid -title "Actual solver mesh: L=0.25 um; coordinates in um" -hide_legend
foreach f [list_fields -plot $grid -show] {
  set_field_prop -plot $grid -geom $mesh $f -hide -hide_bands
}
set_material_prop {Silicon Oxide} -plot $grid -geom $mesh -show_mesh
style_export $structure structure.png
style_export $field strike-field.png
style_export $density strike-electrons.png
style_export $grid mesh.png
set proof [open visual-proof.txt w]
puts $proof "run_directory=[pwd]"
puts $proof [list_fields -dataset $struck]
puts $proof "DRAM_V1_NATIVE_EXPORT_COMPLETED"
close $proof
# GUI remains open; exports are not substitutes for a desktop screenshot.
