set data [load_file {/home/tcad/research-training/runs/20261010T014743Z-v2-base-l025-b1-143253c7/final_access_des.tdr}]
set plot [create_plot -dataset $data]
set_plot_prop -plot $plot -title {Actual 4 ns readout | 20261010T014743Z-v2-base-l025-b1-143253c7 | Electric field (V/cm), coordinates (um)}
foreach f [list_fields -plot $plot -show] {set_field_prop -plot $plot -geom $data $f -hide -hide_bands}
set_field_prop -plot $plot -geom $data Abs(ElectricField-V) -show -show_bands -scale log -levels 41
zoom_plot -plot $plot -reset
export_view {/home/tcad/research-training/dram-see-v2/gui/20261010T014743Z-v2-base-l025-b1-143253c7/final-field-native.png} -plots $plot -resolution 1400x1000 -format PNG -overwrite
set proof [open {/home/tcad/research-training/dram-see-v2/gui/20261010T014743Z-v2-base-l025-b1-143253c7/native-proof.txt} w]
puts $proof [list_fields -dataset $data]
puts $proof {V2_NATIVE_TDR_EXPORT_COMPLETED 20261010T014743Z-v2-base-l025-b1-143253c7}
close $proof
