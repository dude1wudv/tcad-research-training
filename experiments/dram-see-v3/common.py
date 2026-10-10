"""Shared evidence helpers; TCAD execution remains exclusively scripts/tcad.py."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / 'local_runtime/dram-see-v3'
sys.path.insert(0, str(ROOT / 'scripts'))
import tcad

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open('x', encoding='utf8', newline='\n') as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write('\n')
    else:
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
        os.replace(temp, path)

@contextmanager
def controller_lock():
    import msvcrt
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / 'controller.lock').open('a+b') as f:
        f.seek(0)
        if not f.read(1):
            f.write(b'0'); f.flush()
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

def preflight(label):
    """Read-only VM and host/manifest checks, preserved before each dispatch."""
    unresolved = []
    manifests = []
    for p in sorted((ROOT / 'local_runtime/runs').glob('*/manifest.json')):
        m = json.loads(p.read_text(encoding='utf8'))
        row = {'run_id': p.parent.name, 'state': m.get('state'), 'ssh_exit_code': m.get('ssh_exit_code')}
        manifests.append(row)
        if m.get('state') not in ('COLLECTED', 'FAILED_COLLECTED'):
            unresolved.append(row)
    # List only solver-controller executables, never keys or unrelated arguments.
    ps = r"Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|ssh)\.exe$' } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Compress"
    host = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
    raw = json.loads(host.stdout) if host.stdout.strip() else []
    if isinstance(raw, dict): raw = [raw]
    controllers = []
    for p in raw:
        cmd = p.get('CommandLine') or ''
        if p['ProcessId'] == os.getpid(): continue
        if p['Name'].lower() == 'ssh.exe' or any(token in cmd for token in ('tcad.py run', 'run_stage.py', 'finish_batch.py', 'dram-see-v3/run.py', 'dram-see-v3\\run.py', 'dram-readout-offset-d1/run.py')):
            controllers.append({'pid': p['ProcessId'], 'ppid': p['ParentProcessId'], 'name': p['Name'], 'created': p['CreationDate'], 'command': cmd if 'ssh' not in p['Name'].lower() else '[existing SSH; inspect owner before dispatch]'})
    _, ssh, _ = tcad.connection()
    command = "ps -eo pid,ppid,stat,etime,comm,args | awk '$5 ~ /^(sdevice|sde|snmesh|transport|flock)$/ {print}'; true"
    result = tcad.remote(ssh, command, capture_output=True, text=True, timeout=45)
    record = {'utc': now(), 'owner': 'current root chat; sole solver dispatcher', 'label': label,
              'host_controllers': controllers, 'manifests': manifests, 'unresolved': unresolved,
              'remote_command': command, 'remote_exit_code': result.returncode,
              'remote_stdout': result.stdout, 'remote_stderr': result.stderr}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_json(LOCAL / 'preflight' / (stamp + '-' + label + '.json'), record, exclusive=True)
    if unresolved or controllers or result.returncode or result.stdout.strip():
        raise RuntimeError('Active or ambiguous controller/solver/archive; inspect preserved preflight, do not resubmit')
    return record

def preservation_paths():
    paths = set()
    for name in ('dram-see-v1', 'dram-see-v2', 'dram-readout-offset-d1'):
        for base in (ROOT / 'experiments' / name, ROOT / 'local_runtime' / name):
            paths.update(p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'controller.lock')
    # All historical archive files are cheap enough to preserve, not only reused successes.
    paths.update(p for p in (ROOT / 'local_runtime/runs').rglob('*') if p.is_file() and '-v3-' not in p.as_posix())
    return sorted(paths)

def preserve():
    path = LOCAL / 'preservation-before.json'
    if path.exists():
        raise ValueError('Preservation snapshot already exists; verify instead of overwriting')
    files = {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in preservation_paths()}
    user_paths = ('README.txt', 'README.md', 'design-notes/README.md', 'design-notes/agent-workflow.md')
    user = {n: {'exists': (ROOT/n).exists(), 'sha256': sha(ROOT/n) if (ROOT/n).exists() else None} for n in user_paths}
    git = subprocess.run(['git','status','--short'],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    write_json(path, {'utc': now(), 'files': files, 'user_changes': user, 'git_status': git}, exclusive=True)
    return {'files': len(files), 'snapshot_sha256': sha(path), 'user_changes': user}

def check_preservation():
    before = json.loads((LOCAL/'preservation-before.json').read_text(encoding='utf8'))
    accepted = {}
    amendments = LOCAL/'preservation-user-updates.json'
    if amendments.exists():
        for row in json.loads(amendments.read_text(encoding='utf8'))['updates']:
            n=row['path']
            if before['files'][n]['sha256'] != row['before_sha256'] or sha(ROOT/row['backup']) != row['before_sha256']:
                raise ValueError('External document update has no exact preserved original')
            # Narrow exception: only the observed README link replacement in this index.
            if n!='experiments/dram-see-v1/data/artifact-index.json':raise ValueError('Unreviewed preservation amendment')
            prior=json.loads((ROOT/row['backup']).read_bytes());current=json.loads((ROOT/n).read_bytes())
            prior['files'].pop('README.txt'); entry=current['files'].pop('README.md')
            if prior!=current or entry['sha256']!=before['user_changes']['README.md']['sha256']:
                raise ValueError('External update exceeds reviewed README reference change')
            accepted[n]=row['after_sha256']
    bad = [n for n,v in before['files'].items() if not (ROOT/n).is_file() or sha(ROOT/n) != accepted.get(n,v['sha256'])]
    if bad:
        raise ValueError('Historical evidence changed: ' + repr(bad))
    return {'utc': now(), 'files_checked': len(before['files']), 'unexpected_changes': [], 'reviewed_external_document_updates': list(accepted), 'passed': True}

if __name__ == '__main__':
    action = sys.argv[1]
    result = preflight('takeover') if action == 'preflight' else {'preserve': preserve, 'check': check_preservation}[action]()
    if action == 'preflight':
        result = {'passed': True, 'manifests': len(result['manifests']), 'remote_exit_code': result['remote_exit_code'], 'active_controllers': len(result['host_controllers'])}
    print(json.dumps(result, ensure_ascii=False))
