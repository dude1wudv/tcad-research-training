"""Leakage-guarded v3 ridge/mean fitting and immutable pre-test prediction freeze."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys
import tarfile

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / 'local_runtime/dram-see-v3'
TARGETS = ('deltaQ_fC', 'deltaM_mV')
FEATURES = ('Qdep_fC', 'Qdep_fC/L_um', 'Qdep_fC*sin(theta)')
ALPHAS = (0., .01, .1, 1., 10.)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _module(name):
    path = HERE / (name + '.py')
    spec = importlib.util.spec_from_file_location('_v3_prediction_' + name, path)
    obj = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), obj.__dict__)
    return obj


def _configuration(design):
    p = design.get('prediction', {})
    expected = {'models': ['training_mean', 'ridge'], 'targets': list(TARGETS),
                'features': list(FEATURES), 'ridge_candidates': list(ALPHAS),
                'train_lengths_um': [.18, .35], 'holdout_lengths_um': [.25],
                'extrapolation_lengths_um': [.45], 'separate_model_per_bit_and_target': True,
                'selection_score': 'arithmetic mean of per-fold RMSE for each bit/target independently',
                'tie_break': 'lowest alpha among scores within 1e-12 target units of minimum',
                'standardization': 'training fold population mean/std only; zero std replaced with1; final fit uses all training data',
                'ridge_objective': 'sum_squared_error + alpha*sum(coef**2); intercept unpenalized; alpha0 via least-squares'}
    for key, value in expected.items():
        if p.get(key) != value:
            raise ValueError('Prediction configuration differs from frozen implementation: ' + key)
    events = design.get('events', [])
    if len(events) != 64 or len({event['label'] for event in events}) != 64:
        raise ValueError('Expected exactly 64 unique frozen events')
    for split, count, lengths in [('train', 32, (.18, .35)), ('holdout', 16, (.25,)), ('extrapolation', 16, (.45,))]:
        selected = [event for event in events if event['split'] == split]
        if len(selected) != count or any(event['gate_length_um'] not in lengths for event in selected):
            raise ValueError('Frozen split mismatch: ' + split)
    return p


def features(row):
    q, length, angle = row['Qdep_fC'], row['gate_length_um'], row['angle_deg']
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (q, length, angle)):
        raise ValueError('Nonfinite or invalid predictor')
    if q < 0 or length not in (.18, .25, .35, .45) or angle not in (0, 30):
        raise ValueError('Outside frozen feature conditions')
    return [q, q / length, q * math.sin(math.radians(angle))]


def _validated_rows(rows, design, training):
    _configuration(design)
    events = {e['label']: e for e in design['events'] if (e['split'] == 'train') == training}
    expected = {(label, bit) for label in events for bit in (0, 1)}
    indexed = {}
    for row in rows:
        key = (row['event_label'], row['stored_bit'])
        if key not in expected or key in indexed or type(row['stored_bit']) is not int:
            raise ValueError('Unknown, leaked or duplicate response in ' + ('training' if training else 'test inputs'))
        event = events[key[0]]
        for name in ('gate_length_um', 'particle', 'angle_deg', 'seed', 'condition_id', 'replicate', 'split'):
            if row.get(name) != event[name]:
                raise ValueError('Response/event identity mismatch: ' + name)
        features(row)
        if row.get('oxide_nm', 5) != 5 or row.get('step_scale', 1) != 1 or row.get('mesh_scale', 1) != 1:
            raise ValueError('Process/refinement responses do not enter length prediction')
        if training:
            if row.get('continuous_valid') is not True or row.get('continuous_numerical_status') in ('FAILED', 'MISSING', 'UNRESOLVED'):
                raise ValueError('Incomplete/failed continuous training target')
            if set(row.get('targets', {})) != set(TARGETS):
                raise ValueError('Both audited continuous targets required')
            if any(not math.isfinite(row['targets'][target]) for target in TARGETS):
                raise ValueError('Nonfinite training target')
        elif any(name in row for name in ('targets', 'deltaQ_fC', 'deltaM_mV', 'deltaM_V', 'response_run_id', 'signal_response')):
            raise ValueError('Held-out response leaked into predictor input')
        indexed[key] = row
    if set(indexed) != expected:
        raise ValueError('Need every frozen ' + ('64 training responses' if training else '64 test input/bit pairs'))
    ordered = [indexed[(event['label'], bit)] for event in design['events'] if event['label'] in events for bit in (0, 1)]
    # The deposited event is shared by its two bits, not measured independently.
    for label in events:
        if indexed[(label, 0)]['Qdep_fC'] != indexed[(label, 1)]['Qdep_fC']:
            raise ValueError('Paired bits must use exactly the same event deposition')
    return ordered


def _fit_ridge(x, y, alpha):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mean = np.mean(x, axis=0)
    raw_std = np.std(x, axis=0, ddof=0)
    scale = np.where(raw_std == 0, 1., raw_std)
    z = (x - mean) / scale
    intercept = float(np.mean(y))
    if alpha == 0:
        coefficient = np.linalg.lstsq(z, y - intercept, rcond=None)[0]
    else:
        coefficient = np.linalg.solve(z.T @ z + alpha * np.eye(x.shape[1]), z.T @ (y - intercept))
    if not np.all(np.isfinite(coefficient)):
        raise ValueError('Nonfinite fitted coefficient')
    return {'alpha': alpha, 'feature_mean': mean.tolist(), 'feature_population_std': raw_std.tolist(),
            'feature_scale': scale.tolist(), 'coefficient_standardized': coefficient.tolist(),
            'intercept': intercept, 'coefficient_original_units': (coefficient / scale).tolist(),
            'intercept_original_units': intercept - float(mean @ (coefficient / scale)),
            'training_n': len(y)}


def _predict_ridge(model, x):
    x = np.asarray(x, dtype=float)
    z = (x - np.asarray(model['feature_mean'])) / np.asarray(model['feature_scale'])
    return z @ np.asarray(model['coefficient_standardized']) + model['intercept']


def _rmse(prediction, actual):
    return float(np.sqrt(np.mean((np.asarray(prediction) - np.asarray(actual)) ** 2)))


def fit_models(training_rows, design):
    """Pure fit: all 64 declared, audited targets; never silently discard a row."""
    rows = _validated_rows(training_rows, design, True)
    groups = sorted({row['condition_id'] for row in rows})
    if len(groups) != 8 or any(sum(row['condition_id'] == group for row in rows) != 8 for group in groups):
        raise ValueError('Need eight complete training physical-condition groups')
    models = {}
    for bit in (0, 1):
        bit_rows = [row for row in rows if row['stored_bit'] == bit]
        x = np.asarray([features(row) for row in bit_rows])
        for target in TARGETS:
            y = np.asarray([row['targets'][target] for row in bit_rows])
            cv = []
            for group in groups:
                validation = np.asarray([row['condition_id'] == group for row in bit_rows])
                train = ~validation
                mean = float(np.mean(y[train]))
                ridge = []
                for alpha in ALPHAS:
                    fitted = _fit_ridge(x[train], y[train], alpha)
                    predictions = _predict_ridge(fitted, x[validation])
                    ridge.append({'alpha': alpha, 'rmse': _rmse(predictions, y[validation]),
                                  'fit': fitted, 'predictions': predictions.tolist()})
                cv.append({'held_condition_id': group,
                           'training_event_labels': [row['event_label'] for row, keep in zip(bit_rows, train) if keep],
                           'validation_event_labels': [row['event_label'] for row, keep in zip(bit_rows, validation) if keep],
                           'training_mean': {'value': mean, 'rmse': _rmse(np.full(sum(validation), mean), y[validation])},
                           'ridge_candidates': ridge})
            scores = [float(np.mean([fold['ridge_candidates'][i]['rmse'] for fold in cv])) for i in range(len(ALPHAS))]
            minimum = min(scores)
            selected = min(alpha for alpha, score in zip(ALPHAS, scores) if score <= minimum + 1e-12)
            final = _fit_ridge(x, y, selected)
            models[f'bit{bit}:{target}'] = {
                'stored_bit': bit, 'target': target, 'training_response_n': 32,
                'training_mean': {'value': float(np.mean(y)),
                                  'cv_mean_fold_rmse': float(np.mean([fold['training_mean']['rmse'] for fold in cv]))},
                'ridge': final, 'selected_alpha': selected,
                'cv_alpha_scores': [{'alpha': a, 'mean_fold_rmse': s} for a, s in zip(ALPHAS, scores)],
                'cv_folds': cv,
            }
    return {'schema': 'dram-see-v3-prediction-models', 'configuration': design['prediction'],
            'feature_names': list(FEATURES), 'train_independent_events': 32,
            'train_paired_responses': 64, 'models': models,
            'implementation': {'python': platform.python_version(), 'numpy': np.__version__,
                               'linear_algebra': 'numpy lstsq(rcond=None) for alpha0; solve otherwise'},
            'scope': design['prediction']['scope']}


def predict_inputs(models, test_rows, design):
    rows = _validated_rows(test_rows, design, False)
    if models.get('configuration') != design['prediction']:
        raise ValueError('Model configuration differs from frozen design')
    predictions = []
    for row in rows:
        values = features(row)
        targets = {}
        for target in TARGETS:
            fitted = models['models'][f"bit{row['stored_bit']}:{target}"]
            targets[target] = {'training_mean': fitted['training_mean']['value'],
                               'ridge': float(_predict_ridge(fitted['ridge'], [values])[0])}
        predictions.append({'event_label': row['event_label'], 'stored_bit': row['stored_bit'],
                            'condition_id': row['condition_id'], 'split': row['split'],
                            'feature_values': dict(zip(FEATURES, values)), 'predictions': targets})
    return {'schema': 'dram-see-v3-frozen-predictions', 'test_independent_events': 32,
            'test_paired_responses': 64, 'predictions': predictions}


def assert_no_test_submissions(design, ledger, manifests=()):
    """Inspect identities/input metadata only; do not open any test response."""
    test_labels = {event['label'] for event in design['events'] if event['split'] != 'train'}
    for tag, row in ledger.get('runs', {}).items():
        p = row.get('parameters', {})
        if any(('v3-' + label + '-b') in tag for label in test_labels) or (p.get('source_event') and p.get('gate_length_um') in (.25, .45)):
            raise ValueError('Test TCAD already submitted/recorded: ' + tag)
    if ledger.get('stages', {}).get('test'):
        raise ValueError('A test stage already exists')
    for record in manifests:
        identity = record.get('run_id', '')
        p = record.get('parameters', {})
        if any(('v3-' + label + '-b') in identity for label in test_labels) or (p.get('schema') == 'dram-see-v3' and p.get('source_event') and p.get('gate_length_um') in (.25, .45)):
            raise ValueError('Test TCAD archive/submission already exists: ' + identity)


def _verified(ledger, tag):
    row = ledger.get('runs', {}).get(tag.replace('.', 'p'))
    if not row or row.get('state') != 'VERIFIED' or not row.get('run_id'):
        raise ValueError('Required verified response missing: ' + tag)
    if row.get('continuous_numerical_status') in ('FAILED', 'MISSING', 'UNRESOLVED') or row.get('continuous_numeric_valid') is False:
        raise ValueError('Known unresolved continuous numerical target: ' + tag)
    return row


def _manifest_inputs():
    found = []
    for path in sorted((ROOT / 'local_runtime/runs').glob('*-v3-*/manifest.json')):
        m = json.loads(path.read_text(encoding='utf8'))
        record = {'run_id': m.get('run_id', path.parent.name), 'state': m.get('state'),
                  'manifest_sha256': sha(path)}
        inputs = path.parent / 'inputs.tar'
        if inputs.exists():
            with tarfile.open(inputs) as tf:
                members = [member for member in tf.getmembers() if member.isfile() and member.name.removeprefix('./') == 'parameters.json']
                if len(members) != 1:
                    raise ValueError('Ambiguous v3 submitted parameters: ' + record['run_id'])
                record['parameters'] = json.loads(tf.extractfile(members[0]).read())
        found.append(record)
    return found


def _event_record(design_event, validator, evidence):
    path = HERE / 'data/geant4' / design_event['label'] / 'event.json'
    expected = {key: design_event[key] for key in ('gate_length_um', 'particle', 'angle_deg', 'seed', 'energy_MeV')}
    ev = validator.validate_event(path, expected)
    for name in ('event.json', 'events.csv', 'steps.csv'):
        member = path.parent / name
        evidence[member.relative_to(ROOT).as_posix()] = sha(member)
    return ev


def _bind_bundle(bundle, evidence):
    run_id = bundle['summary']['run_id']
    for name in ('manifest.json', 'inputs.tar', 'results.tar'):
        path = ROOT / 'local_runtime/runs' / run_id / name
        evidence[path.relative_to(ROOT).as_posix()] = sha(path)


def collect_inputs(design, ledger):
    """Production adapter: raw audits, matched curves, and predeclared G4 only."""
    for stage in ('references', 'pilot', 'train'):
        if ledger.get('stages', {}).get(stage, {}).get('state') != 'VERIFIED':
            raise ValueError('Prediction gate incomplete: ' + stage)
    assert_no_test_submissions(design, ledger, _manifest_inputs())
    metrics, event_audit = _module('metrics'), _module('event_audit')
    evidence, training, test, cache = {}, [], [], {}
    def bundle(run_id):
        if run_id not in cache:
            cache[run_id] = metrics.audit_module.load_curves(run_id)
            _bind_bundle(cache[run_id], evidence)
        return cache[run_id]
    # Recheck physical reference/source-isolation evidence instead of trusting
    # the stage label alone. Old controls and neutral curves are re-audited.
    for length in (.18, .25, .35, .45):
        neutral_run = _verified(ledger, f'v3-neutral-l{round(length*100):03d}-ox5-s1-m1')['run_id']
        for bit in (0, 1):
            control_run = _verified(ledger, f'v3-control-l{round(length*100):03d}-b{bit}-ox5-s1-m1')['run_id']
            physical_run = _verified(ledger, f'v3-physical-l{round(length*100):03d}-b{bit}')['run_id']
            result = metrics.compare_physical_curves(bundle(physical_run), bundle(control_run), bundle(neutral_run))
            if not result['passed']:
                raise ValueError('Reference gate no longer passes')
    for particle, angle, bit in (('alpha', 30, 1), ('proton', 0, 0)):
        event = next(e for e in design['events'] if e['pilot'] and e['particle'] == particle and e['angle_deg'] == angle)
        physical = _verified(ledger, f'v3-isolation-{particle}-a{angle}-b{bit}')['run_id']
        signal = _verified(ledger, 'v3-' + event['label'] + f'-b{bit}')['run_id']
        neutral = _verified(ledger, 'v3-neutral-l018-ox5-s1-m1')['run_id']
        if not metrics.compare_physical_curves(bundle(physical), bundle(signal), bundle(neutral))['passed']:
            raise ValueError('Source isolation gate no longer passes')
    for event in design['events']:
        transport = _event_record(event, event_audit, evidence)
        length = event['gate_length_um']
        neutral_run = _verified(ledger, f'v3-neutral-l{round(length*100):03d}-ox5-s1-m1')['run_id']
        for bit in (0, 1):
            row = {key: event[key] for key in ('gate_length_um', 'particle', 'angle_deg', 'seed', 'condition_id', 'replicate', 'split')}
            row.update(event_label=event['label'], stored_bit=bit,
                       Qdep_fC=transport['converted'][0]['charge_pc'] * 1000,
                       source_event_sha256=evidence[(HERE / 'data/geant4' / event['label'] / 'event.json').relative_to(ROOT).as_posix()])
            control_run = _verified(ledger, f'v3-control-l{round(length*100):03d}-b{bit}-ox5-s1-m1')['run_id']
            control, neutral = bundle(control_run), bundle(neutral_run)
            if event['split'] == 'train':
                item = _verified(ledger, 'v3-' + event['label'] + f'-b{bit}')
                signal = bundle(item['run_id'])
                p = signal['parameters']
                for key in ('gate_length_um', 'particle', 'angle_deg', 'seed', 'stored_bit'):
                    if p.get(key) != row[key]:
                        raise ValueError('Training archive identity differs from frozen event')
                if p.get('charge_pc') != transport['converted'][0]['charge_pc']:
                    raise ValueError('Training archived particle charge differs from G4')
                result = metrics.compute_curves(signal, control, neutral)
                row.update(targets={'deltaQ_fC': result['deltaQ_fC'], 'deltaM_mV': result['deltaM_V'] * 1000},
                           continuous_valid=True, continuous_numerical_status='RAW_AUDIT_PASSED',
                           classification=result['classification'],
                           classification_numerical_status=item.get('classification_numerical_status', 'boundary/refinement status must remain separately reported'),
                           numerical_evidence=item.get('numerical_evidence'), sources=result['sources'],
                           metric_validity=result['validity'])
                training.append(row)
            else:
                # Comparing a control against itself validates the full neutral
                # matching key/mesh; no held-out particle response is opened.
                baseline = metrics.compute_curves(control, control, neutral)
                row.update(known_control={'M4_mV': baseline['control_M4_V'] * 1000,
                                          'hold_SN_V': metrics.sample(control['circuit'], 'v(sn)', 2.8e-9)},
                           sources={'control': baseline['sources']['control'], 'neutral': baseline['sources']['neutral']})
                test.append(row)
    _validated_rows(training, design, True)
    _validated_rows(test, design, False)
    return training, test, evidence


def _write_json(path, value):
    with path.open('x', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def _write_bundle(out, training, test, design, ledger, provenance, evidence):
    out = Path(out)
    if out.exists():
        raise ValueError('Prediction output is immutable and already exists')
    models = fit_models(training, design)
    predictions = predict_inputs(models, test, design)
    artifacts = {'models.json': models, 'training-data.json': training, 'test-inputs.json': test,
                 'predictions.json': predictions, 'ledger-snapshot.json': ledger, 'provenance.json': provenance}
    out.mkdir(parents=True)
    for name, value in artifacts.items():
        _write_json(out / name, value)
        evidence[(out / name).relative_to(ROOT).as_posix()] = sha(out / name)
    frozen = {'schema': 'dram-see-v3-prediction-freeze',
              'frozen_utc': datetime.now(timezone.utc).isoformat(),
              'design_sha256': provenance['design_sha256'],
              'training_independent_events': 32, 'training_responses': 64,
              'test_independent_events': 32, 'test_paired_predictions': 64,
              'models_per_bit_target': 4, 'test_responses_seen': 0,
              'files_sha256': evidence, 'scope': design['prediction']['scope']}
    _write_json(out / 'freeze.json', frozen)
    # The self-hash lives outside JSON, avoiding a circular digest.
    with (out / 'freeze.sha256').open('x', encoding='ascii') as stream:
        stream.write(sha(out / 'freeze.json') + '\n')
    return frozen


def freeze():
    """Main dispatcher calls this only after all gates; no solve/transport here."""
    out = HERE / 'data/predictions'
    if out.exists():
        raise ValueError('Prediction output exists; never replace a pre-test freeze')
    design_path, ledger_path = HERE / 'stats-design.json', LOCAL / 'ledger.json'
    digest = sha(design_path)
    if digest != (LOCAL / 'stats-design.sha256').read_text().strip():
        raise ValueError('Design hash differs from the frozen design')
    design = json.loads(design_path.read_text(encoding='utf8'))
    _configuration(design)
    ledger_bytes = ledger_path.read_bytes()
    ledger = json.loads(ledger_bytes)
    training, test, evidence = collect_inputs(design, ledger)
    sources = [HERE / (name + '.py') for name in ('prediction', 'statistics', 'metrics', 'audit', 'event_audit', 'build_case', 'design')]
    sources += [design_path, HERE.parent / 'dram-see-v1/analyze.py', HERE.parent / 'dram-see-v2/audit.py',
                HERE.parent / 'dram-readout-offset-d1/audit.py']
    for path in sources:
        evidence[path.relative_to(ROOT).as_posix()] = sha(path)
    if ledger_path.read_bytes() != ledger_bytes:
        raise ValueError('Ledger changed during model preparation; freeze requires a stable controller boundary')
    assert_no_test_submissions(design, ledger, _manifest_inputs())
    provenance = {'design_sha256': digest, 'ledger_snapshot_sha256': hashlib.sha256(ledger_bytes).hexdigest(),
                  'gates': ledger['stages'], 'test_submission_check': 'no test ledger entries or submitted input manifests',
                  'target_status': 'critical classes retained as audited continuous values; failures/missing/known continuous numerical failures block',
                  'source_sha256': {path.relative_to(ROOT).as_posix(): sha(path) for path in sources},
                  'python': sys.version, 'numpy': np.__version__,
                  'raw_evidence_files': len(evidence)}
    return _write_bundle(out, training, test, design, ledger, provenance, evidence)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze'])
    parser.parse_args()
    result = freeze()
    print(json.dumps({'frozen_utc': result['frozen_utc'], 'test_paired_predictions': result['test_paired_predictions'],
                      'freeze': str(HERE / 'data/predictions/freeze.json')}, indent=2))
