"""Register frozen-model forecasts after Geant4, before TCAD reference completion."""
from datetime import datetime,timezone
import hashlib
import json
import math
from analyze import ROOT,HERE
from event_contract import validate_event


def main():
    model_path=HERE/'data/model-frozen.json';model=json.loads(model_path.read_text())
    model_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
    state=json.loads((ROOT/'local_runtime/dram-see-v1/batch-state.json').read_text())
    path=HERE/'data/extrapolation-forecasts.json'
    records=json.loads(path.read_text()) if path.exists() else {}
    for case in json.loads((HERE/'matrix.json').read_text())['cases']:
        if case['split']!='extrapolation_test':continue
        key=case['id'];event_path=HERE/'data/geant4'/key/'event.json'
        if key in records:
            if records[key]['model_sha256']!=model_hash:raise ValueError('Forecast model changed')
            continue
        if not event_path.exists():continue
        if key in state['cases']:raise ValueError('Reference already completed; refuse backdated forecast')
        for manifest_path in (ROOT/'local_runtime/runs').glob('*-see-'+key+'-*/manifest.json'):
            if json.loads(manifest_path.read_text())['state']!='RUNNING':
                raise ValueError('Reference runner already ended')
            log=manifest_path.parent/'console.log'
            if log.exists() and 'Sentaurus Device simulation finished' in log.read_text(encoding='utf8',errors='replace'):
                raise ValueError('Reference solver already finished')
        event=validate_event(event_path,{'label':key,'gate_length_um':case['gate_length_um'],'particle':case['particle'],
            'energy_MeV':case['energy_MeV'],'angle_deg':case['angle_deg'],'seed':case['seed'],'event_count':case['events']})
        q=event['converted'][0]['charge_pc']*1000
        values={'1':1,'Qdep_fC':q,'Qdep_fC/L_um':q/case['gate_length_um'],'Qdep_fC*sin(angle)':q*math.sin(math.radians(case['angle_deg']))}
        prediction=sum(values[name]*coefficient for name,coefficient in zip(model['features'],model['coefficients'],strict=True))
        records[key]={'registered_utc':datetime.now(timezone.utc).isoformat(),'predicted_drop_V':prediction,
            'model_sha256':model_hash,'source_event_sha256':hashlib.sha256(event_path.read_bytes()).hexdigest(),
            'reference_completed_at_registration':False,'scope':'Two-stage forecast uses actual Geant4 Q; TCAD voltage/current values are not used.'}
        print(json.dumps({'registered':key,'predicted_drop_V':prediction}),flush=True)
    path.write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
