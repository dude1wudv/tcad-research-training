"""Bind an actual Geant4 event to a TCAD condition and audit its conversion."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path


def validate_bytes(metadata, files, expected=None):
    event=json.loads(metadata)
    if event['operation_exit_code']!=0 or event['event_count']!=1:
        raise ValueError('TCAD v1 requires one successful event')
    if set(event['files_sha256'])!={'steps.csv','events.csv'}:
        raise ValueError('Unexpected event file set')
    for name,digest in event['files_sha256'].items():
        if hashlib.sha256(files[name]).hexdigest()!=digest:
            raise ValueError('Event CSV hash mismatch: '+name)
    if expected:
        for key,value in expected.items():
            if event.get(key)!=value:raise ValueError('Event condition mismatch: '+key)
    if event['particle'] not in ('alpha','proton') or event['angle_deg'] not in (0,30):
        raise ValueError('Unsupported event condition')
    rows=list(csv.DictReader(io.StringIO(files['events.csv'].decode())))
    steps=list(csv.DictReader(io.StringIO(files['steps.csv'].decode())))
    if len(rows)!=1 or rows[0]['event']!='0' or any(s['event']!='0' for s in steps):
        raise ValueError('Unexpected raw event identities')
    energy=float(rows[0]['ionizing_MeV'])
    values=[float(s['ionizing_MeV']) for s in steps]
    if not values or not all(math.isfinite(v) and v>=0 for v in values):
        raise ValueError('Invalid deposited energy')
    if not (0<energy<=event['energy_MeV']) or not math.isclose(sum(values),energy,rel_tol=1e-10):
        raise ValueError('Raw energy accounting failed')
    if event['conversion_eV_per_pair']!=3.6:raise ValueError('Unexpected conversion constant')
    q=energy*1e6/3.6*1.602176634e-19*1e12
    angle=math.radians(event['angle_deg'])
    track=min(1.2/math.cos(angle),(event['gate_length_um']+.45)/math.sin(angle) if angle else math.inf)
    if len(event['converted'])!=1:raise ValueError('Unexpected converted event count')
    converted=event['converted'][0]
    for key,value in {'ionizing_MeV':energy,'charge_pc':q,'track_length_um':track,'let_pc_per_um':q/track}.items():
        if not math.isclose(converted[key],value,rel_tol=1e-10):raise ValueError('Converted value mismatch: '+key)
    return event


def validate_event(path,expected=None):
    path=Path(path)
    files={name:(path.parent/name).read_bytes() for name in ('steps.csv','events.csv')}
    return validate_bytes(path.read_bytes(),files,expected)
