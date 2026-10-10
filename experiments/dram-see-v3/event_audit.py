"""Audit one frozen v3 silicon transport event without running any external tool."""
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

BINARY_SHA = '830cd8480bc11a27b243f6662d0e64a71d5b382a45bfd1e80f8e199bfdfdb67f'
SOURCE_SHA = '8f3ec870dad0905be7516bf657ed033d8cf5c5ade7cef938a941622b2f483ce2'
LENGTHS = (.18, .25, .35, .45)
PARTICLES = ('alpha', 'proton')
ANGLES = (0, 30)
EVENT_FIELDS = ('event', 'ionizing_MeV', 'niel_MeV', 'primary_path_um')
STEP_FIELDS = ('event', 'track', 'parent', 'x_um', 'y_um', 'z_um', 't_ns',
               'step_um', 'edep_MeV', 'niel_MeV', 'ionizing_MeV')


def geometry(length, angle=0):
    """Geometry of the equivalent straight track, not the scattered primary path."""
    if isinstance(length, bool) or length not in LENGTHS or isinstance(angle, bool) or angle not in ANGLES:
        raise ValueError('Outside frozen v3 geometry')
    a = math.radians(angle)
    sine, cosine = math.sin(a), math.cos(a)
    impact = length + .45
    bottom = 1.2 / cosine
    side = impact / sine if angle else math.inf
    track = min(bottom, side)
    return {'surface_impact_um': [impact, 0., 0.],
            'launch_position_um': [impact + .001 * math.tan(a), -.001, 0.],
            'direction': [-sine, cosine, 0.],
            'track_length_um': track,
            'exit_position_um': [impact - track * sine, track * cosine, 0.],
            'exit_boundary': 'left' if side < bottom else 'bottom'}


def condition_seed(length, particle, angle, seed):
    """Return the predeclared replicate r (1..4), rejecting condition/seed drift."""
    geometry(length, angle)
    if particle not in PARTICLES or type(seed) is not int:
        raise ValueError('Bad particle or integer random seed')
    c = 4 * LENGTHS.index(length) + 2 * PARTICLES.index(particle) + ANGLES.index(angle)
    replicate = seed - (202610300 + 10 * c)
    if replicate not in (1, 2, 3, 4):
        raise ValueError('Seed is not registered for this v3 condition')
    return replicate


def _close(actual, expected, name, rel_tol=1e-10, abs_tol=1e-15):
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
        raise ValueError('Nonfinite or nonnumeric ' + name)
    if not math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
        raise ValueError('Mismatch ' + name)


def _vector(actual, expected, name):
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError('Bad vector ' + name)
    for i, (value, target) in enumerate(zip(actual, expected)):
        _close(value, target, name + '[' + str(i) + ']')


def _rows(content, fields, name):
    reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    if tuple(reader.fieldnames or ()) != fields:
        raise ValueError('Unexpected CSV fields: ' + name)
    rows = list(reader)
    for row in rows:
        if set(row) != set(fields) or any(v is None or v == '' for v in row.values()):
            raise ValueError('Malformed CSV row: ' + name)
        try:
            if any(not math.isfinite(float(value)) for value in row.values()):
                raise ValueError('Nonfinite transport output')
        except (TypeError, ValueError) as exc:
            raise ValueError('Nonnumeric or nonfinite CSV row: ' + name) from exc
    return rows


def validate_bytes(metadata, files, expected=None):
    """v2-compatible call shape; metadata and CSV bytes must describe a v3 event.

    A legal zero-deposition event can have an empty steps CSV. Geant4 only writes
    steps with positive total deposited energy, so primary_path_um is not forced
    equal to the sum of recorded step lengths or to the equivalent straight track.
    """
    ev = json.loads(metadata)
    if ev.get('schema') != 'dram-see-v3':
        raise ValueError('Need v3 event metadata')
    if not isinstance(ev.get('label'), str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', ev['label']):
        raise ValueError('Bad event label')
    if ev.get('binary_sha256') != BINARY_SHA or ev.get('source_sha256') != SOURCE_SHA:
        raise ValueError('Transport binary/source differs from the existing verified build')
    condition_seed(ev['gate_length_um'], ev['particle'], ev['angle_deg'], ev['seed'])
    if ev.get('energy_MeV') != 5 or ev.get('conversion_eV_per_pair') != 3.6:
        raise ValueError('Energy or conversion differs from frozen v3 transport')
    if type(ev.get('operation_exit_code')) is not int or ev['operation_exit_code'] != 0 or type(ev.get('event_count')) is not int or ev['event_count'] != 1:
        raise ValueError('Need one complete transport event')
    if type(ev.get('collection_exit_code')) is not int or ev['collection_exit_code'] != 0:
        raise ValueError('Need successful transport collection')
    if ev.get('operation_label') != 'g4-' + ev['label']:
        raise ValueError('Operation identity differs from event label')
    for key, value in (expected or {}).items():
        if ev.get(key) != value:
            raise ValueError('Source condition mismatch ' + key)
    if set(files) != {'steps.csv', 'events.csv'} or set(ev.get('files_sha256', {})) != set(files):
        raise ValueError('Unexpected event file set')
    for name, content in files.items():
        if hashlib.sha256(content).hexdigest() != ev['files_sha256'][name]:
            raise ValueError('Source file hash mismatch: ' + name)
    geo = geometry(ev['gate_length_um'], ev['angle_deg'])
    for key in ('surface_impact_um', 'launch_position_um', 'direction', 'exit_position_um'):
        _vector(ev.get(key), geo[key], key)
    if ev.get('exit_boundary') != geo['exit_boundary']:
        raise ValueError('Wrong equivalent-track exit boundary')
    rows = _rows(files['events.csv'], EVENT_FIELDS, 'events.csv')
    steps = _rows(files['steps.csv'], STEP_FIELDS, 'steps.csv')
    if len(rows) != 1 or rows[0]['event'] != '0' or any(row['event'] != '0' for row in steps):
        raise ValueError('Wrong raw event identity')
    e, niel, path = (float(rows[0][key]) for key in EVENT_FIELDS[1:])
    if e < 0 or niel < 0 or e + niel > 5 + 1e-12 or path < 0:
        raise ValueError('Invalid event energy or primary path')
    width = ev['gate_length_um'] + .6
    for row in steps:
        for key in ('track', 'parent'):
            value = float(row[key])
            if value != int(value) or value < (1 if key == 'track' else 0):
                raise ValueError('Invalid track/parent identity')
        if float(row['parent']) >= float(row['track']):
            raise ValueError('Impossible track ancestry')
        if any(float(row[key]) < 0 for key in ('t_ns', 'step_um', 'edep_MeV', 'niel_MeV', 'ionizing_MeV')):
            raise ValueError('Negative transport observable')
        if float(row['edep_MeV']) <= 0 or float(row['niel_MeV']) > float(row['edep_MeV']) + 1e-15:
            raise ValueError('Invalid recorded deposition')
        _close(float(row['ionizing_MeV']), max(0., float(row['edep_MeV']) - float(row['niel_MeV'])), 'step energy partition')
        for key, lo, hi in [('x_um', 0., width), ('y_um', 0., 1.2), ('z_um', -.5, .5)]:
            if not lo - 1e-8 <= float(row[key]) <= hi + 1e-8:
                raise ValueError('Recorded step is outside the silicon slab: ' + key)
    _close(math.fsum(float(row['ionizing_MeV']) for row in steps), e, 'ionizing energy accounting')
    _close(math.fsum(float(row['niel_MeV']) for row in steps), niel, 'nonionizing energy accounting')
    primary_recorded = math.fsum(float(row['step_um']) for row in steps if row['parent'] == '0')
    if primary_recorded > path + max(1e-12, path * 1e-10):
        raise ValueError('Recorded primary steps exceed complete primary path')
    if not isinstance(ev.get('converted'), list) or len(ev['converted']) != 1:
        raise ValueError('Wrong converted event count')
    converted = ev['converted'][0]
    if converted.get('event') != 0:
        raise ValueError('Converted event identity differs')
    charge = e * 1e6 / 3.6 * 1.602176634e-19 * 1e12
    for key, value in {'ionizing_MeV': e, 'charge_pc': charge,
                       'track_length_um': geo['track_length_um'],
                       'let_pc_per_um': charge / geo['track_length_um']}.items():
        _close(converted.get(key), value, 'conversion ' + key)
    return ev


def validate_event(path, expected=None):
    path = Path(path)
    return validate_bytes(path.read_bytes(),
                          {name: (path.parent / name).read_bytes() for name in ('steps.csv', 'events.csv')},
                          expected)
