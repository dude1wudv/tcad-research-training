"""Run one immutable v3 event with the existing Geant4 binary and pinned SSH.

Only the main scheduler may call run(). Import and pure contract validation do
not connect to the VM. All operation logs and failure evidence stay under v3.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME = ROOT / 'local_runtime/dram-see-v3'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


event_audit = _load('_dram_see_v3_event_audit_transport', HERE / 'event_audit.py')
tcad = _load('_dram_see_v3_tcad_transport', ROOT / 'scripts/tcad.py')
BINARY_SHA = event_audit.BINARY_SHA
SOURCE_SHA = event_audit.SOURCE_SHA


def _json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def _check_unused(label, seed):
    """Fail closed on historical/partial event identities; never auto-resubmit."""
    for path in sorted((ROOT / 'experiments').glob('*/data/geant4/*/event.json')):
        previous = json.loads(path.read_bytes())
        if previous.get('seed') == seed or previous.get('label') == label:
            raise ValueError('Event label or random seed already exists: ' + path.relative_to(ROOT).as_posix())
    for path in sorted((RUNTIME / 'operations').glob('g4-*/request.json')):
        previous = json.loads(path.read_bytes())
        if previous.get('seed') == seed or previous.get('label') == label:
            raise ValueError('Event has a prior attempt; inspect remote state and collect, do not rerun: ' + str(path))
    if (HERE / 'data/geant4' / label).exists() or (RUNTIME / 'operations' / ('g4-' + label)).exists():
        raise ValueError('Immutable event or operation directory already exists')


def run(label, length, particle, seed, angle=0):
    event_audit.condition_seed(length, particle, angle, seed)
    if not isinstance(label, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', label):
        raise ValueError('Bad event label')
    source_path = HERE.parent / 'dram-see-v1/geant4_transport.cc'
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError('Local verified Geant4 source has changed')
    _check_unused(label, seed)
    geo = event_audit.geometry(length, angle)
    request = {'schema': 'dram-see-v3-transport-request', 'label': label,
               'gate_length_um': length, 'particle': particle, 'energy_MeV': 5.,
               'seed': seed, 'angle_deg': angle, 'event_count': 1,
               'source_sha256': SOURCE_SHA, 'binary_sha256': BINARY_SHA,
               'requested_utc': datetime.now(timezone.utc).isoformat()}
    # Atomic local reservations also protect against an accidental second caller.
    seed_dir = RUNTIME / 'operations/transport-seeds' / str(seed)
    seed_dir.mkdir(parents=True, exist_ok=False)
    _json(seed_dir / 'request.json', request)
    op = RUNTIME / 'operations' / ('g4-' + label)
    op.mkdir(parents=True, exist_ok=False)
    _json(op / 'request.json', request)
    record = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'label': 'g4-' + label, 'timeout_s': 120,
              'state': 'PREPARED', 'request_sha256': hashlib.sha256((op / 'request.json').read_bytes()).hexdigest()}
    _json(op / 'operation.json', record)
    try:
        cfg, ssh, _ = tcad.connection()
        old = cfg['remote_root'].rstrip('/') + '/dram-see-v1'
        base = cfg['remote_root'].rstrip('/') + '/dram-see-v3'
        directory = base + '/events/' + label
        command = ' '.join(map(shlex.quote, [old + '/build/transport', str(length), particle,
                                            '5', str(angle), str(seed), '1']))
        script = ('set -eu\nsource ' + shlex.quote(old + '/env.sh') + '\n'
                  'actual=$(sha256sum ' + shlex.quote(old + '/build/transport') + ' | cut -d " " -f1)\n'
                  'test "$actual" = ' + BINARY_SHA + '\n'
                  'source_actual=$(sha256sum ' + shlex.quote(old + '/build/geant4_transport.cc') + ' | cut -d " " -f1)\n'
                  'test "$source_actual" = ' + SOURCE_SHA + '\n'
                  'mkdir -p ' + shlex.quote(base + '/events/.seeds') + '\n'
                  'mkdir ' + shlex.quote(base + '/events/.seeds/' + str(seed)) + '\n'
                  'mkdir ' + shlex.quote(directory) + '\n'
                  'cd ' + shlex.quote(directory) + '\n'
                  "printf '%s\\n' " + shlex.quote(label) + ' > event-label.txt\n'
                  "printf '%s\\n' " + str(seed) + ' > seed.txt\n'
                  'trap \'code=$?; printf "%s\\n" "$code" > transport-exit-code.txt\' EXIT\n'
                  + command + '\n')
        (op / 'command.sh').write_text(script, encoding='utf-8', newline='\n')
        record.update(script_sha256=hashlib.sha256(script.encode()).hexdigest(),
                      remote_directory=directory, state='SUBMITTED')
        _json(op / 'operation.json', record)
        with (op / 'stdout.txt').open('wb') as out, (op / 'stderr.txt').open('wb') as err:
            result = subprocess.run(ssh + ['bash -lc ' + shlex.quote(script)], stdout=out, stderr=err, timeout=120)
        record['exit_code'] = result.returncode
        if result.returncode != 0 or 'TRANSPORT_COMPLETED events=1' not in (op / 'stdout.txt').read_text(errors='replace'):
            raise RuntimeError('Transport did not complete successfully; preserve evidence and inspect ' + str(op))
        collect_command = 'tar -cf - -C ' + shlex.quote(directory) + ' events.csv steps.csv transport-exit-code.txt'
        (op / 'collection-command.txt').write_text(collect_command + '\n', encoding='utf-8')
        with (op / 'events.tar').open('wb') as out, (op / 'collection-stderr.txt').open('wb') as err:
            collected = subprocess.run(ssh + [collect_command], stdout=out, stderr=err, timeout=60)
        record['collection_exit_code'] = collected.returncode
        record['archive_sha256'] = hashlib.sha256((op / 'events.tar').read_bytes()).hexdigest()
        if collected.returncode != 0:
            raise RuntimeError('Transport collection failed; do not resubmit event: ' + str(op))
        with tarfile.open(op / 'events.tar') as archive:
            members = archive.getmembers()
            required = {'steps.csv', 'events.csv', 'transport-exit-code.txt'}
            if len(members) != 3 or {m.name for m in members} != required or any(not m.isfile() for m in members):
                raise ValueError('Unexpected transport archive members')
            files = {name: archive.extractfile(name).read() for name in ('steps.csv', 'events.csv')}
            if archive.extractfile('transport-exit-code.txt').read().strip() != b'0':
                raise ValueError('Remote transport exit is not zero')
        rows = list(csv.DictReader(io.StringIO(files['events.csv'].decode('utf-8'))))
        if len(rows) != 1:
            raise ValueError('Wrong transport event count')
        energy = float(rows[0]['ionizing_MeV'])
        charge = energy * 1e6 / 3.6 * 1.602176634e-19 * 1e12
        track = geo.pop('track_length_um')
        metadata = {'schema': 'dram-see-v3', 'label': label, 'gate_length_um': length,
                    'particle': particle, 'energy_MeV': 5., 'angle_deg': angle, 'seed': seed,
                    'event_count': 1, **geo, 'conversion_eV_per_pair': 3.6,
                    'converted': [{'event': 0, 'ionizing_MeV': energy, 'charge_pc': charge,
                                   'track_length_um': track, 'let_pc_per_um': charge / track}],
                    'source_sha256': SOURCE_SHA, 'binary_sha256': BINARY_SHA,
                    'files_sha256': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                    'operation_exit_code': result.returncode, 'collection_exit_code': collected.returncode,
                    'operation_label': record['label'], 'operation_archive_sha256': record['archive_sha256'],
                    'command': command.replace(old, '${V1_INSTALLED_ROOT}'),
                    'scope': 'one predeclared independent silicon event; EM-only; uniform equivalent straight track; no oxide transport'}
        event_audit.validate_bytes(json.dumps(metadata).encode(), files)
        out = HERE / 'data/geant4' / label
        out.mkdir(parents=True, exist_ok=False)
        for name, content in files.items():
            (out / name).write_bytes(content)
        _json(out / 'event.json', metadata)
        record.update(state='VALIDATED', event_metadata_sha256=hashlib.sha256((out / 'event.json').read_bytes()).hexdigest())
        return metadata
    except Exception as exc:
        record['error'] = repr(exc)
        record['state'] = 'REQUIRES_READ_ONLY_RECONCILIATION'
        raise
    finally:
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        _json(op / 'operation.json', record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--length', type=float, required=True)
    parser.add_argument('--particle', choices=event_audit.PARTICLES, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--angle', type=int, choices=event_audit.ANGLES, default=0)
    args = parser.parse_args()
    print(json.dumps(run(args.label, args.length, args.particle, args.seed, args.angle), indent=2))
