"""Build a local navigation index without altering scientific results or raw runs.

Usage (from the repository root, after all controllers have stopped writing):
    python -B experiments/dram-see-v2/deliverable_index.py

Writes only experiments/dram-see-v2/data/summary/delivery-index.json, atomically.
No SSH, solver, archive extraction, copying, packaging, or scientific reanalysis.
RUNNING / PREPARED / EXECUTED observations refuse publication. The caller must
also check Windows/VM processes: a filesystem snapshot is not a scheduler lock.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path('experiments/dram-see-v2')
OUTPUT = EXPERIMENT / 'data/summary/delivery-index.json'
LEDGER = Path('local_runtime/dram-see-v2/ledger.json')
RUNS = Path('local_runtime/runs')
DESIGN = EXPERIMENT / 'stats-design.json'
ATTEMPTS = EXPERIMENT / 'data/summary/all-run-attempts.csv'
RAW_NAMES = ('inputs.tar', 'results.tar', 'manifest.json', 'console.log')
ACTIVE_STATES = {'RUNNING', 'PREPARED', 'EXECUTED'}
RUN_NAME = re.compile(r'^\d{8}T\d{6}Z-(v2-[a-z0-9_-]+)-[0-9a-f]{8}$')
ALLOWED_EXTENSIONS = {'.md', '.txt', '.log', '.py', '.json', '.csv', '.png', '.svg', '.tcl', '.scm', '.cmd'}
SENSITIVE_NAMES = {'connection.json', 'known_hosts', 'id_rsa', 'id_ed25519'}


class IndexRefused(RuntimeError):
    """Inputs are active, unsafe, or changed while being inspected."""


def linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def sensitive_name(name):
    lowered = name.lower()
    return (lowered in SENSITIVE_NAMES or lowered.startswith('.env') or
            any(token in lowered for token in ('credential', 'license', 'private-key', 'secret')))


def safe_path(root, relative):
    """Resolve only explicit local relative paths; never follow a link/junction."""
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise IndexRefused('Non-local inventory path: ' + str(relative))
    path = root
    for part in relative.parts:
        path = path / part
        if linked(path):
            raise IndexRefused('Linked inventory path: ' + relative.as_posix())
    if not path.resolve().is_relative_to(root.resolve()):
        raise IndexRefused('Inventory path escapes repository')
    return path


def identity(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


class Inventory:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.observed = {}
        self.records = {}

    def add(self, relative, contents=False):
        key = Path(relative).as_posix()
        path = safe_path(self.root, relative)
        if not path.exists():
            self.observed[key] = None
            return ({'path': key, 'present': False, 'size_bytes': None, 'sha256': None}, None)
        if not path.is_file():
            raise IndexRefused('Expected a regular file: ' + key)
        before = identity(path)
        digest = hashlib.sha256()
        chunks = [] if contents else None
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
                if contents:
                    chunks.append(chunk)
        if identity(path) != before:
            raise IndexRefused('File changed while hashing: ' + key)
        if key in self.observed and self.observed[key] != before:
            raise IndexRefused('File changed between reads: ' + key)
        self.observed[key] = before
        record = {'path': key, 'present': True, 'size_bytes': before[0], 'sha256': digest.hexdigest()}
        self.records[key] = record
        return record, b''.join(chunks) if contents else None

    def json(self, relative, default=None):
        record, raw = self.add(relative, contents=True)
        return json.loads(raw.decode('utf-8-sig')) if record['present'] else default

    def unchanged(self):
        for relative, previous in self.observed.items():
            path = safe_path(self.root, relative)
            current = identity(path) if path.exists() else None
            if current != previous:
                raise IndexRefused('Input changed before publication: ' + relative)


def run_directories(root):
    folder = safe_path(root, RUNS)
    if not folder.exists():
        return []
    result = []
    for path in sorted(folder.iterdir()):
        if RUN_NAME.fullmatch(path.name):
            safe_path(root, RUNS / path.name)
            if path.is_dir():
                result.append(path.name)
    return result


def experiment_files(root):
    """Only approved artifact types inside v2; omit secrets and self-reference."""
    base = safe_path(root, EXPERIMENT)
    included, excluded = [], []
    if not base.is_dir():
        raise IndexRefused('Missing v2 experiment directory')
    for directory, folders, files in os.walk(base, followlinks=False):
        parent = Path(directory)
        keep = []
        for name in sorted(folders):
            path = parent / name
            if name == '__pycache__' or name.startswith('.') or sensitive_name(name) or linked(path):
                excluded.append({'path': path.relative_to(root).as_posix(), 'reason': 'excluded directory or link'})
            else:
                keep.append(name)
        folders[:] = keep
        for name in sorted(files):
            path = parent / name
            relative = path.relative_to(root)
            if relative == OUTPUT or name == 'delivery-index.json.tmp':
                continue
            if sensitive_name(name) or linked(path) or path.suffix.lower() not in ALLOWED_EXTENSIONS:
                excluded.append({'path': relative.as_posix(), 'reason': 'sensitive name, link, or unapproved type'})
            else:
                included.append(relative)
    return sorted(included), sorted(excluded, key=lambda row: row['path'])


def assert_inactive(ledger, manifests):
    active = ['ledger:' + tag for tag, row in ledger.get('runs', {}).items()
              if str(row.get('state', '')).upper() in ACTIVE_STATES]
    active += [rid for rid, row in manifests.items()
               if str(row.get('state', '')).upper() in ACTIVE_STATES]
    if active:
        raise IndexRefused('Active/unsettled runs; no final index written: ' + ', '.join(active))


def failure_reasons(manifest, audit_row, ledger_rows):
    reasons = []
    sources = [('manifest', manifest), ('all-run-attempts.csv', audit_row)]
    sources.extend(('ledger:' + row['tag'], row) for row in ledger_rows)
    for source, row in sources:
        for key in ('audit_error', 'error', 'failure_reason', 'reason'):
            if row.get(key):
                reasons.append({'source': source, 'field': key, 'value': row[key]})
        for key in ('ssh_exit_code', 'runner_exit_code'):
            value = row.get(key)
            if value not in (None, '', 0, '0'):
                reasons.append({'source': source, 'field': key, 'value': value})
    if not reasons and ('FAIL' in manifest.get('state', '') or audit_row.get('audit_state') == 'failed_audit'):
        reasons.append({'source': 'manifest/console.log', 'field': 'status_only',
                        'value': 'Failure recorded; detailed cause requires the linked original log; not inferred.'})
    return reasons


def build_index(root=ROOT):
    """Prepare a deterministic index in memory; this function writes nothing."""
    root = Path(root).resolve()
    inventory = Inventory(root)
    ledger = inventory.json(LEDGER, {'runs': {}})
    run_ids = run_directories(root)
    manifests = {rid: inventory.json(RUNS / rid / 'manifest.json', {}) for rid in run_ids}
    assert_inactive(ledger, manifests)  # Refuse before hashing large archives.
    design = inventory.json(DESIGN)
    _, raw_attempts = inventory.add(ATTEMPTS, contents=True)
    attempts = list(csv.DictReader(io.StringIO(raw_attempts.decode('utf-8-sig')))) if raw_attempts else []
    audit_by_run = {}
    for row in attempts:
        rid = row.get('run_id')
        if rid in audit_by_run:
            raise IndexRefused('Duplicate attempt rows: ' + str(rid))
        audit_by_run[rid] = row
    planned_tags = {}
    for event in (design or {}).get('events', []):
        for bit in event.get('paired_bits', []):
            planned_tags[f'v2-{event["label"]}-b{bit}'] = {'event_label': event['label'], 'bit': bit}
    baseline_ids = set((design or {}).get('baseline_run_ids', []))
    rows = []
    for rid in run_ids:
        tag = RUN_NAME.fullmatch(rid).group(1)
        entries = [dict(item, tag=key) for key, item in ledger.get('runs', {}).items()
                   if item.get('run_id') == rid or (not item.get('run_id') and key == tag)]
        if rid in baseline_ids or (tag.startswith('v2-base-') and any(e['tag'] == tag for e in entries)):
            role, basis = 'official_baseline', 'frozen baseline_run_ids or explicit baseline ledger tag'
        elif tag in planned_tags:
            role, basis = 'independent_event_response', 'exact frozen event label and paired bit tag'
        elif tag.startswith('v2-validate-'):
            role, basis = 'numerical_validation', 'validation run tag; does not add an independent event'
        else:
            role, basis = 'historical_debug', 'v2 archive outside official baseline/event/validation tags'
        files = {name: inventory.add(RUNS / rid / name)[0] for name in RAW_NAMES}
        manifest = manifests[rid]
        audit_row = audit_by_run.get(rid, {})
        archive_hash = files['results.tar']['sha256']
        declared_hash = manifest.get('results_sha256')
        rows.append({'run_id': rid, 'tag': tag, 'role': role, 'role_basis': basis,
                     'frozen_event_pair': planned_tags.get(tag), 'manifest_state': manifest.get('state', 'MISSING'),
                     'ssh_exit_code': manifest.get('ssh_exit_code'), 'files': files,
                     'manifest_results_sha256': declared_hash,
                     'results_hash_matches_manifest': archive_hash == declared_hash if archive_hash and declared_hash else None,
                     'archive_collection_success': manifest.get('state') == 'COLLECTED' and manifest.get('ssh_exit_code') == 0,
                     'audit_observation': audit_row or None, 'ledger_observations': entries,
                     'failure_reasons': failure_reasons(manifest, audit_row, entries),
                     'audit_runner_state_matches_manifest': audit_row.get('runner_state') == manifest.get('state') if audit_row else None})
    artifact_paths, excluded = experiment_files(root)
    artifacts = [inventory.add(path)[0] for path in artifact_paths]
    inventory.unchanged()
    if run_directories(root) != run_ids or experiment_files(root) != (artifact_paths, excluded):
        raise IndexRefused('Inventory membership changed before publication')
    payload = {'schema': 'dram-see-v2-delivery-index-v1',
               'scope': 'Local navigation and actual byte hashes only; not a scientific reclassification or completion certificate.',
               'path_base': 'repository root; all indexed paths are relative',
               'publication_precondition': 'No active local controller/VM solve; caller confirms processes independently. Filesystem activity guards are not a scheduler lock.',
               'scan_allowlist': [EXPERIMENT.as_posix(), RUNS.as_posix() + '/<timestamp>-v2-<tag>-<8hex>/' + '{inputs.tar,results.tar,manifest.json,console.log}', LEDGER.as_posix()],
               'excluded_sensitive_scope': 'No connection configuration, keys, licenses, unrelated runs, archive extraction, or external path traversal.',
               'frozen_design': {'file': inventory.records.get(DESIGN.as_posix()), 'content': design},
               'ledger_file': inventory.records.get(LEDGER.as_posix()),
               'runs': rows, 'experiment_artifacts': artifacts, 'excluded_experiment_paths': excluded,
               'ledger_items_without_archive': [dict(item, tag=tag) for tag, item in ledger.get('runs', {}).items()
                   if not any(item.get('run_id') == rid or (not item.get('run_id') and tag == RUN_NAME.fullmatch(rid).group(1)) for rid in run_ids)],
               'statistics_policy': 'Frozen design, classifications, counts and intervals are preserved in their existing files. Paired bit responses and validation runs do not create new independent events.'}
    return payload, inventory


def publish(root=ROOT):
    payload, inventory = build_index(root)
    destination = safe_path(inventory.root, OUTPUT)
    temporary = safe_path(inventory.root, OUTPUT.with_name('delivery-index.json.tmp'))
    if temporary.exists():
        raise IndexRefused('Existing temporary index; inspect it before rerunning')
    if not destination.parent.is_dir():
        raise IndexRefused('Missing summary directory; generate final summaries first')
    data = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    inventory.unchanged()
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(data)
        inventory.unchanged()
        if run_directories(inventory.root) != [row['run_id'] for row in payload['runs']]:
            raise IndexRefused('Run appeared before publication')
        if experiment_files(inventory.root)[0] != [Path(row['path']) for row in payload['experiment_artifacts']]:
            raise IndexRefused('Artifact appeared before publication')
        os.replace(temporary, destination)
    finally:
        if created and temporary.exists():
            temporary.unlink()  # Only this function's exclusive newly-created temp file.
    return destination


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(publish())
    except (IndexRefused, OSError, ValueError) as exc:
        print('DELIVERY_INDEX_REFUSED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
