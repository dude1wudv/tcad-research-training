"""Load audited real TDR in a new SVisual session, export and capture own window."""
import argparse,hashlib,json,re,shlex,subprocess,time
from pathlib import Path
from operate import remote,ROOT,tcad
from audit import audit
HERE=Path(__file__).resolve().parent
def main(rid,resume=False):
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-z0-9-]+',rid):raise ValueError('Invalid run id')
    summary=audit(rid,export=False);cfg,ssh,_=tcad.connection()
    source=cfg['remote_root']+'/runs/'+rid
    with __import__('tarfile').open(ROOT/'local_runtime/runs'/rid/'results.tar') as tf:
        from analyze import read
        tdrhash=hashlib.sha256(read(tf,'final_access_des.tdr')).hexdigest()
    sourcecheck=subprocess.run(ssh+['sha256sum '+shlex.quote(source+'/final_access_des.tdr')],capture_output=True,check=True,timeout=30)
    if sourcecheck.stdout.decode().split()[0]!=tdrhash:raise ValueError('Remote native TDR differs from the audited archive')
    target=cfg['remote_root']+'/dram-see-v2/gui/'+rid
    label='gui-'+rid
    tcl='''set data [load_file {SOURCE/final_access_des.tdr}]
set plot [create_plot -dataset $data]
set_plot_prop -plot $plot -title {Actual 4 ns readout | RID | Electric field (V/cm), coordinates (um)}
foreach f [list_fields -plot $plot -show] {set_field_prop -plot $plot -geom $data $f -hide -hide_bands}
set_field_prop -plot $plot -geom $data Abs(ElectricField-V) -show -show_bands -scale log -levels 41
zoom_plot -plot $plot -reset
export_view {TARGET/final-field-native.png} -plots $plot -resolution 1400x1000 -format PNG -overwrite
set proof [open {TARGET/native-proof.txt} w]
puts $proof [list_fields -dataset $data]
puts $proof {V2_NATIVE_TDR_EXPORT_COMPLETED RID}
close $proof
'''.replace('SOURCE',source).replace('TARGET',target).replace('RID',rid)
    local=HERE/'figures/native'/rid
    if not resume:
        local.mkdir(parents=True,exist_ok=False)
        (local/'view.tcl').write_text(tcl)
        subprocess.run(ssh+['umask 077; mkdir -p '+shlex.quote(target)+'; cat > '+shlex.quote(target+'/view.tcl')],input=tcl.encode(),check=True,timeout=30)
    elif not local.exists() or (local/'view.tcl').read_text()!=tcl:raise ValueError('No matching owned GUI session to resume')
    caplabel=label+'-capture'+('-r2' if resume else '')
    helpername='capture-r2.py' if resume else 'capture.py'
    helper=(HERE/'capture_guest_window.py').read_bytes()
    subprocess.run(ssh+['cat > '+shlex.quote(target+'/'+helpername)],input=helper,check=True,timeout=30)
    script='set -eu\nexport DISPLAY=:0\nexport XAUTHORITY="$HOME/.Xauthority"\ncd '+shlex.quote(target)+'\nnohup /usr/synopsys/sentaurus/W-2024.09/bin/svisual -tcl -script view.tcl > visual.log 2>&1 < /dev/null &\necho $! > own-pid.txt\n'
    if not resume:record,op=remote(label+'-launch',script,30)
    else:record=json.loads((ROOT/'local_runtime/dram-see-v2/operations'/(label+'-launch')/'operation.json').read_text())
    if record['exit_code']:raise RuntimeError('GUI launch failed')
    for i in range(12):
        r=subprocess.run(ssh+['test -f '+shlex.quote(target+'/native-proof.txt')],capture_output=True,timeout=20)
        if r.returncode==0:break
        time.sleep(2)
    else:raise RuntimeError('GUI export did not complete; retain own launch logs')
    cap='set -eu\nexport DISPLAY=:0\nexport XAUTHORITY="$HOME/.Xauthority"\ncd '+shlex.quote(target)+'\n/usr/bin/python '+helpername+' "$(cat own-pid.txt)" own-window.png\n'
    caprecord,capop=remote(caplabel,cap,30)
    if caprecord['exit_code']:raise RuntimeError('Owned window capture failed')
    for name in ('final-field-native.png','own-window.png','native-proof.txt','visual.log','own-pid.txt'):
        data=subprocess.run(ssh+['cat '+shlex.quote(target+'/'+name)],capture_output=True,check=True,timeout=30).stdout
        (local/name).write_bytes(data)
    proof={'run_id':rid,'archive_sha256':summary['archive_sha256'],'tdr_sha256':tdrhash,
           'remote_source_sha256_before_load_or_resume':sourcecheck.stdout.decode().split()[0],
           'native_loaded_file':source+'/final_access_des.tdr','condition':summary['parameters'],
           'launch_operation':record,'capture_operation':caprecord,
           'capture_stdout':(capop/'stdout.txt').read_text(),
           'screenshot_kind':'real owned SVisual X11 window pixels; unmodified',
           'export_kind':'native SVisual export from actual solver TDR; distinct from window screenshot',
           'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in local.iterdir() if p.is_file()}}
    (local/'evidence.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(local)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('--resume',action='store_true');a=p.parse_args();main(a.run_id,a.resume)
