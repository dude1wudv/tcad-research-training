set data [load_file {/home/tcad/research-training/runs/20261010T082741Z-rodiag1-matched-ref-r3-99f3de31/final_access_des.tdr}]
set plot [create_plot -dataset $data]
set_plot_prop -plot $plot -title {D1 4 ns signal E-field map (not a readout curve) | 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31 | V/cm, coordinates um}
foreach f [list_fields -plot $plot -show] {set_field_prop -plot $plot -geom $data $f -hide -hide_bands}
set_field_prop -plot $plot -geom $data Abs(ElectricField-V) -show -show_bands -scale log -levels 41
zoom_plot -plot $plot -reset
export_view {/home/tcad/research-training/dram-readout-offset-d1/gui/20261010T082741Z-rodiag1-matched-ref-r3-99f3de31/final-field-native.png} -plots $plot -resolution 1400x1000 -format PNG -overwrite
set proof [open {/home/tcad/research-training/dram-readout-offset-d1/gui/20261010T082741Z-rodiag1-matched-ref-r3-99f3de31/native-proof.txt} w]
puts $proof [list_fields -dataset $data]
puts $proof {D1_NATIVE_FIELD_EXPORT_COMPLETED 20261010T082741Z-rodiag1-matched-ref-r3-99f3de31}
close $proof
