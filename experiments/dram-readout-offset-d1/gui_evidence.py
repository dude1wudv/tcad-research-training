"""D1-only native 4 ns electric-field export and actual owned-window capture.

Adapted from dram-see-v2/gui_evidence.py. This is a final TDR field image,
NOT a transient readout curve. Run only after the matched-ref-r3 audit passes:
  python -B experiments/dram-readout-offset-d1/gui_evidence.py <run-id>

An existing output directory is refused. No resume, solver execution, window
closing, or v2 writes. The reused capture helper raises only its owned window,
which may temporarily cover another window. The owned GUI remains open.
"""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # Imported legacy helpers must not create v1/v2 caches.
from audit import audit
from analyze import read

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / 'local_runtime/dram-readout-offset-d1'
CAPTURE = HERE.parent / 'dram-see-v2/capture_guest_window.py'
REFERENCE = HERE.parent / 'dram-see-v2/gui_evidence.py'
sys.path.insert(0, str(ROOT / 'scripts'))
import tcad


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def remote(ssh, operation_root, label, script, payload=None, timeout=30):
    """Use the existing SSH connection; keep all operation evidence in D1."""
    folder = operation_root / label
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'command.sh').write_text(script, encoding='utf-8', newline='\n')
    record = {'label': label, 'started_utc': now(), 'timeout_s': timeout,
              'script_sha256': hashlib.sha256(script.encode('utf-8')).hexdigest(),
              'stdin_sha256': hashlib.sha256(payload).hexdigest() if payload is not None else None}
    try:
        result = subprocess.run(ssh + ['bash -lc ' + shlex.quote(script)], input=payload,
                                capture_output=True, timeout=timeout)
        (folder / 'stdout.bin').write_bytes(result.stdout)
        (folder / 'stderr.txt').write_bytes(result.stderr)
        record['exit_code'] = result.returncode
        return result, record
    except subprocess.TimeoutExpired as exc:
        (folder / 'stdout.bin').write_bytes(exc.stdout or b'')
        (folder / 'stderr.txt').write_bytes(exc.stderr or b'')
        record['error'] = 'TimeoutExpired; inspect actual remote state, do not relaunch automatically'
        raise
    except Exception as exc:
        record['error'] = repr(exc)
        raise
    finally:
        record['finished_utc'] = now()
        (folder / 'operation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


def main(rid):
    if not re.fullmatch(r'\d{8}T\d{6}Z-rodiag1-matched-ref-r3-[0-9a-f]{8}', rid):
        raise ValueError('Expected the actual D1 matched-ref-r3 run ID')
    local = HERE / 'figures/native' / rid
    if local.exists():
        raise ValueError('Native output already exists; inspect it instead of launching another GUI')
    ledger = json.loads((LOCAL / 'ledger.json').read_text(encoding='utf-8'))
    if any(row.get('state') == 'RUNNING' for row in ledger.get('runs', {}).values()):
        raise ValueError('D1 controller still has a RUNNING case; wait before GUI capture')
    item = ledger['runs'].get('rodiag1-matched-ref-r3', {})
    if item.get('state') != 'VERIFIED' or item.get('run_id') != rid:
        raise ValueError('Need the VERIFIED matched-ref-r3 ledger identity')
    summary = audit(rid, export=False)
    if summary['parameters']['variant'] != 'matched_ref':
        raise ValueError('Not a physical matched-reference case')
    with tarfile.open(ROOT / 'local_runtime/runs' / rid / 'results.tar') as archive:
        tdr_hash = hashlib.sha256(read(archive, 'final_access_des.tdr')).hexdigest()
    dependencies = [Path(__file__), HERE / 'audit.py', REFERENCE, CAPTURE,
                    HERE.parent / 'dram-see-v2/audit.py', HERE.parent / 'dram-see-v2/event_audit.py',
                    HERE.parent / 'dram-see-v1/analyze.py',
                    ROOT / 'scripts/tcad.py']
    dependency_hashes = {path.relative_to(ROOT).as_posix(): sha(path) for path in dependencies}
    local.mkdir(parents=True, exist_ok=False)
    operation_root = LOCAL / 'gui-operations' / rid
    if operation_root.exists():
        raise ValueError('Existing D1 GUI operation evidence; inspect before retrying')
    cfg, ssh, _ = tcad.connection()
    source = cfg['remote_root'] + '/runs/' + rid
    target_parent = cfg['remote_root'] + '/dram-readout-offset-d1/gui'
    target = target_parent + '/' + rid
    if any(character in source + target for character in '{}\r\n'):
        raise ValueError('Remote paths cannot be represented by the existing literal Tcl template')

    def checked(label, script, payload=None):
        result, record = remote(ssh, operation_root, label, script, payload)
        if result.returncode:
            raise RuntimeError(label + ' failed; preserve D1 logs and inspect, no automatic relaunch')
        return result, record

    source_check, _ = checked('source-hash', 'sha256sum ' + shlex.quote(source + '/final_access_des.tdr'))
    remote_tdr_hash = source_check.stdout.decode().split()[0]
    if remote_tdr_hash != tdr_hash:
        raise ValueError('Remote final TDR differs from the audited archived TDR')
    marker = 'D1_NATIVE_FIELD_EXPORT_COMPLETED ' + rid
    tcl = '''set data [load_file {SOURCE/final_access_des.tdr}]
set plot [create_plot -dataset $data]
set_plot_prop -plot $plot -title {D1 4 ns signal E-field map (not a readout curve) | RID | V/cm, coordinates um}
foreach f [list_fields -plot $plot -show] {set_field_prop -plot $plot -geom $data $f -hide -hide_bands}
set_field_prop -plot $plot -geom $data Abs(ElectricField-V) -show -show_bands -scale log -levels 41
zoom_plot -plot $plot -reset
export_view {TARGET/final-field-native.png} -plots $plot -resolution 1400x1000 -format PNG -overwrite
set proof [open {TARGET/native-proof.txt} w]
puts $proof [list_fields -dataset $data]
puts $proof {MARKER}
close $proof
'''.replace('SOURCE', source).replace('TARGET', target).replace('RID', rid).replace('MARKER', marker)
    (local / 'view.tcl').write_text(tcl, encoding='utf-8')
    checked('upload-view', 'set -eu\numask 077\nmkdir -p ' + shlex.quote(target_parent) +
            '\nmkdir ' + shlex.quote(target) + '\ncat > ' + shlex.quote(target + '/view.tcl') + '\n',
            tcl.encode('utf-8'))
    helper = CAPTURE.read_bytes()
    if hashlib.sha256(helper).hexdigest() != dependency_hashes[CAPTURE.relative_to(ROOT).as_posix()]:
        raise ValueError('Capture helper changed after dependency hashing')
    checked('upload-capture-helper', 'cat > ' + shlex.quote(target + '/capture.py'), helper)
    launch = ('set -eu\nexport DISPLAY=:0\nexport XAUTHORITY="$HOME/.Xauthority"\ncd ' + shlex.quote(target) +
              '\nnohup /usr/synopsys/sentaurus/W-2024.09/bin/svisual -tcl -script view.tcl > visual.log 2>&1 < /dev/null &\n'
              'echo $! > own-pid.txt\n')
    _, launch_record = checked('launch', launch)
    pid_result, _ = checked('owned-pid', 'cat ' + shlex.quote(target + '/own-pid.txt'))
    if not pid_result.stdout.decode().strip().isdigit():
        raise ValueError('No numeric owned launch PID; inspect existing GUI, do not relaunch')
    (local / 'own-pid.txt').write_bytes(pid_result.stdout)
    for index in range(12):
        ready, _ = remote(ssh, operation_root, f'ready-{index:02d}',
                          'test -f ' + shlex.quote(target + '/native-proof.txt'), timeout=20)
        if ready.returncode == 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError('Native export did not complete; keep owned PID and D1 launch logs')
    capture = ('set -eu\nexport DISPLAY=:0\nexport XAUTHORITY="$HOME/.Xauthority"\ncd ' + shlex.quote(target) +
               '\n/usr/bin/python capture.py "$(cat own-pid.txt)" own-window.png\n')
    capture_result, capture_record = checked('capture', capture)
    capture_stdout = capture_result.stdout.decode(errors='replace')
    if 'OWNED_WINDOW_CAPTURE pid=' not in capture_stdout:
        raise ValueError('Missing owned-window capture confirmation')
    for name in ('final-field-native.png', 'own-window.png', 'native-proof.txt', 'visual.log'):
        result, _ = checked('fetch-' + name, 'cat ' + shlex.quote(target + '/' + name))
        (local / name).write_bytes(result.stdout)
    if marker not in (local / 'native-proof.txt').read_text(encoding='utf-8'):
        raise ValueError('Native proof marker does not identify the selected run')
    evidence = {'run_id': rid, 'archive_sha256': summary['archive_sha256'], 'tdr_sha256': tdr_hash,
                'remote_source_sha256_before_load': remote_tdr_hash,
                'native_loaded_file': source + '/final_access_des.tdr', 'condition': summary['parameters'],
                'depended_source_files_sha256': dependency_hashes,
                'launch_operation': launch_record, 'capture_operation': capture_record,
                'operation_directory': operation_root.relative_to(ROOT).as_posix(),
                'owned_launch_pid': int(pid_result.stdout.decode().strip()), 'capture_stdout': capture_stdout,
                'screenshot_kind': 'real owned SVisual X11 window pixels; unmodified',
                'export_kind': 'native SVisual export of actual final signal-branch TDR',
                'scope': '4 ns electric-field map in V/cm, coordinates um; NOT a transient readout curve; no solver executed',
                'window_behavior': 'Only the newly owned window was raised for capture; existing windows were not closed. Owned GUI remains open.',
                'files_sha256': {path.name: sha(path) for path in sorted(local.iterdir()) if path.is_file()}}
    (local / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(local)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    main(parser.parse_args().run_id)
