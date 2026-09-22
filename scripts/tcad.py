"""Standard-library CLI for a private, pinned-host Sentaurus workstation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'local_runtime/connection.json'


def execute(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def connection():
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    result = execute([cfg['vmrun'], 'getGuestIPAddress', cfg['vmx']],
                     capture_output=True, text=True, timeout=30)
    import ipaddress
    ip = ipaddress.IPv4Address(result.stdout.strip())
    if not ip.is_private or ip.is_loopback:
        raise ValueError('Expected a private VMware guest IPv4 address')
    ssh = ['ssh', '-i', cfg['identity'], '-o', 'IdentitiesOnly=yes',
           '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'HostKeyAlias=tcad-training-vm',
           '-o', 'UserKnownHostsFile=' + cfg['known_hosts'],
           '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15',
           '-o', 'ServerAliveCountMax=3', cfg['user'] + '@' + str(ip)]
    return cfg, ssh, str(ip)


def remote(ssh, script, **kwargs):
    return execute(ssh + ['bash -lc ' + shlex.quote(script)], **kwargs)


def doctor(cfg, ssh, ip):
    script = ('set -eu; export PATH=' + shlex.quote(cfg['tool_bin']) + ':"$PATH"; '
              'printf "SSH_OK\\n"; hostname; id -un; '
              'for tool in sde snmesh sdevice swb svisual; do command -v "$tool"; done; '
              'command -v flock; command -v taskset; command -v tar; '
              'getconf _NPROCESSORS_ONLN; df -h "$HOME"; sdevice -v')
    result = remote(ssh, script, capture_output=True, text=True, timeout=60)
    print(result.stdout)
    folder = ROOT / 'local_runtime/diagnostics'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (folder / (stamp + '.json')).write_text(json.dumps({
        'utc': stamp, 'ip': ip, 'stdout': result.stdout, 'stderr': result.stderr,
        'scope': 'SSH, executable discovery and version/license probe; not physics validation'
    }, indent=2), encoding='utf-8')


def run_project(cfg, ssh, project):
    project = project.resolve()
    if not project.is_dir():
        raise ValueError('Project directory does not exist')
    spec = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', spec['name']):
        raise ValueError('Use a lowercase engineering project name')
    steps = spec['steps']
    if not steps:
        raise ValueError('A project needs at least one real tool step')
    allowed = {'sde', 'snmesh', 'sdevice'}
    for step in steps:
        if step['tool'] not in allowed or not all(isinstance(a, str) for a in step['args']):
            raise ValueError('Only explicit sde/snmesh/sdevice argument arrays are supported')
        if step['tool'] == 'sdevice' and any('thread' in a.lower() for a in step['args']):
            raise ValueError('Thread count is managed by the runner')
        if not step.get('outputs'):
            raise ValueError('Every step must declare its expected output files')
        for output in step['outputs']:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', output):
                raise ValueError('Expected outputs must be simple filenames')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_id = stamp + '-' + spec['name'] + '-' + uuid.uuid4().hex[:8]
    local = ROOT / 'local_runtime/runs' / run_id
    local.mkdir(parents=True)
    remote_dir = cfg['remote_root'].rstrip('/') + '/runs/' + run_id
    commit = execute(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                     capture_output=True, text=True).stdout.strip()
    files = sorted(p for p in project.rglob('*') if p.is_file())
    if any(p.is_symlink() for p in project.rglob('*')):
        raise ValueError('Symlinks are not allowed in simulation inputs')
    inputs = {p.relative_to(project).as_posix(): file_hash(p) for p in files}
    evidence = {'run_id': run_id, 'commit': commit, 'input_sha256': inputs,
                'runner_sha256': file_hash(Path(__file__)),
                'steps': steps, 'remote_directory': remote_dir, 'state': 'PREPARED',
                'interpretation': 'Engineering execution only; scientific validity requires review'}
    manifest = local / 'manifest.json'
    def save():
        manifest.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    save()
    archive = local / 'inputs.tar'
    with tarfile.open(archive, 'w') as tf:
        for p in files:
            tf.add(p, arcname=p.relative_to(project).as_posix(), recursive=False)
    qdir = shlex.quote(remote_dir)
    qroot = shlex.quote(cfg['remote_root'])
    runner = ['#!/bin/bash', 'set -euo pipefail', 'umask 077',
              'cd ' + qdir,
              'trap \'rc=$?; printf "%s\\n" "$rc" > exit-code.txt\' EXIT',
              'exec > >(tee execution.log) 2>&1',
              'export PATH=' + shlex.quote(cfg['tool_bin']) + ':"$PATH"',
              'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1',
              'mkdir -p ' + qroot,
              'exec 9>' + qroot + '/.solver.lock',
              'flock -n 9 || { echo "Another project run holds the solver lock" >&2; exit 75; }',
              'cpu=$(awk \'/^Cpus_allowed_list:/{split($2,a,/[-,]/);print a[1]}\' /proc/self/status)',
              'date -u; hostname; sdevice -v; taskset -pc $$']
    for index, step in enumerate(steps, 1):
        args = [step['tool']]
        if step['tool'] == 'sdevice':
            args += ['--threads', '1', '--exit-on-failure']
        args += step['args']
        runner += ['echo ' + shlex.quote('STEP ' + str(index) + ': ' + shlex.join(args)),
                   'taskset -c "$cpu" ' + shlex.join(args)]
        runner += ['test -s ' + shlex.quote(out) for out in step['outputs']]
    runner += ['echo ENGINEERING_RUN_COMPLETED']
    script = '\n'.join(runner) + '\n'
    (local / 'run.sh').write_text(script, encoding='utf-8', newline='\n')
    try:
        remote(ssh, 'umask 077; mkdir -p ' + shlex.quote(cfg['remote_root'] + '/runs') +
               '; mkdir ' + qdir, timeout=30)
        with archive.open('rb') as stream:
            remote(ssh, 'tar -xf - -C ' + qdir, stdin=stream, timeout=120)
        remote(ssh, 'cat > ' + qdir + '/run.sh', input=script.encode(), timeout=30)
        evidence['state'] = 'RUNNING'
        save()
        with (local / 'console.log').open('wb') as console:
            result = subprocess.run(ssh + ['bash ' + qdir + '/run.sh'], stdout=console,
                                    stderr=subprocess.STDOUT)
        evidence['ssh_exit_code'] = result.returncode
        evidence['state'] = 'EXECUTED' if result.returncode == 0 else 'FAILED_OR_DISCONNECTED'
    except Exception as exc:
        evidence['state'] = 'TRANSFER_OR_CONNECTION_FAILED'
        evidence['error'] = str(exc)
        raise
    finally:
        save()
        print('Run evidence:', local)
    with (local / 'results.tar').open('wb') as stream:
        remote(ssh, 'tar -cf - -C ' + qdir + ' .', stdout=stream, timeout=300)
    evidence['results_sha256'] = file_hash(local / 'results.tar')
    evidence['state'] = 'COLLECTED' if result.returncode == 0 else 'FAILED_COLLECTED'
    save()
    if result.returncode:
        raise RuntimeError('Solver execution failed; inspect collected evidence, do not relabel as valid')
    print('Outputs collected. Review convergence, mesh and terminal conditions before scientific use.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    sub.add_parser('shell')
    run = sub.add_parser('run')
    run.add_argument('project', type=Path)
    args = parser.parse_args()
    cfg, ssh, ip = connection()
    if args.command == 'doctor':
        doctor(cfg, ssh, ip)
    elif args.command == 'shell':
        execute(ssh[:-1] + ['-t', ssh[-1]])
    else:
        run_project(cfg, ssh, args.project)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print('ERROR:', exc, file=sys.stderr)
        if getattr(exc, 'stderr', None):
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
