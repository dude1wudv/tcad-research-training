"""Rebuild transparent pilot tables from immutable run archives and frozen design."""
import argparse,csv,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from audit import audit,classification
from statistics import summarize_classes
from event_audit import validate_bytes

def write_csv(path,rows,fields=None):
    if fields is None:fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def denominator(classes,planned):
    """Missing outcomes are disclosed; CIs only for a complete planned stratum."""
    n=len(classes);k=classes.count('criterion_logic_flip');u=classes.count('uncertain');missing=planned-n
    if not 0<=n<=planned or planned<1:raise ValueError('Invalid planned denominator')
    s={'planned_n':planned,'completed_n':n,'missing_or_failed_n':missing,
       'correct':classes.count('correct'),'definite_flip':k,'uncertain':u,
       'planned_definite_fraction_lower':k/planned,
       'planned_flip_uncertain_missing_fraction_upper':(k+u+missing)/planned,
       'complete_planned_stratum':missing==0,'wilson_95_definite':None,
       'wilson_95_flip_or_uncertain':None,'zero_definite_flip_exact_one_sided_95_upper':None,
       'zero_flip_or_uncertain_exact_one_sided_95_upper':None}
    if missing==0:s.update(summarize_classes(classes))
    return s

def rebuild():
    ledgerpath=ROOT/'local_runtime/dram-see-v2/ledger.json'
    ledger=json.loads(ledgerpath.read_text()) if ledgerpath.exists() else {'runs':{}}
    designpath=HERE/'stats-design.json'
    design=json.loads(designpath.read_text()) if designpath.exists() else None
    numerical_path=HERE/'data/summary/numerical-checks.json'
    numerical=json.loads(numerical_path.read_text()) if numerical_path.exists() else {'checks':{}}
    refined=numerical['checks'].get('half_step',{})
    out=HERE/'data/summary';out.mkdir(parents=True,exist_ok=True)
    summaries={};index=[]
    for folder in sorted((ROOT/'local_runtime/runs').glob('*-v2-*')):
        m=json.loads((folder/'manifest.json').read_text())
        row={'run_id':folder.name,'runner_state':m['state'],'ssh_exit_code':m.get('ssh_exit_code'),
             'results_sha256':m.get('results_sha256'),'audit_state':'not_complete'}
        if m['state']=='COLLECTED' and m.get('ssh_exit_code')==0:
            try:
                s=audit(folder.name);summaries[folder.name]=s
                row.update(audit_state='verified',L_um=s['parameters']['gate_length_um'],bit=s['parameters']['stored_bit'],
                           seed=s['parameters'].get('seed'),solver_wallclock_s=s['wallclock_s'],solver_completion=s['solver_completion'])
            except Exception as exc:row.update(audit_state='failed_audit',error=repr(exc))
        index.append(row)
    write_csv(out/'all-run-attempts.csv',index)
    bases={};baseline_rows=[];responses=[]
    for tag,item in ledger['runs'].items():
        s=summaries.get(item.get('run_id'))
        if not s:continue
        p=s['parameters']
        if tag.startswith('v2-base-'):
            key=(p['gate_length_um'],p['stored_bit'])
            if key in bases:raise ValueError('Duplicate official baseline')
            bases[key]=s
            baseline_rows.append({'run_id':s['run_id'],'L_um':key[0],'bit':key[1],
                'target_SN_V':p['target_voltage_V'],'prestrike_SN_V':s['prestrike_V'],
                'initial_error_mV':s['initial_error_V']*1e3,'initial_charge_fC':s['prestrike_charge_fC'],
                'hold_end_SN_V':s['hold_end_V'],'read_precharge_SN_V':s['read_precharge_SN_V'],
                'D_mV':s['differential_V']*1e3,'M_mV':s['signed_margin_V']*1e3,
                'class_5mV':s['classification'],'newton_retries':s['newton_retries'],
                'solver_wallclock_s':s['wallclock_s'],'archive_sha256':s['archive_sha256']})
    write_csv(out/'baselines.csv',sorted(baseline_rows,key=lambda x:(x['L_um'],x['bit'])))
    stats=[];events=[]
    if design:
        ids=[(e['particle'],e['seed']) for e in design['events']]
        if len(set(ids))!=len(ids) or len({e['seed'] for e in design['events']})!=len(ids):raise ValueError('Duplicate independent seed')
        if design['independent_event_count']!=len(ids) or design['tcad_paired_response_count']!=2*len(ids):
            raise ValueError('Design count differs from frozen list')
        for particle in ('alpha','proton'):
            if sum(e['particle']==particle for e in design['events'])!=design['n_per_particle']:
                raise ValueError('Design stratum count differs')
        for ev in design['events']:
            label=ev['label'];eventpath=HERE/'data/geant4'/label/'event.json'
            row=dict(label=label,particle=ev['particle'],seed=ev['seed'],L_um=ev['gate_length_um'],energy_MeV=ev['energy_MeV'],
                     angle_deg=ev['angle_deg'],surface_impact_um=json.dumps(ev['surface_impact_um']),direction=json.dumps(ev['direction']),
                     event_id=0,source_state='not_completed',bit0_state='not_completed',bit1_state='not_completed')
            meta=None
            if eventpath.exists():
                meta=validate_bytes(eventpath.read_bytes(),{n:(eventpath.parent/n).read_bytes() for n in ('steps.csv','events.csv')},
                                    {k:ev[k] for k in ('particle','seed','gate_length_um','energy_MeV','angle_deg')})
                row.update(source_state='verified',ionizing_MeV=meta['converted'][0]['ionizing_MeV'],
                           injected_Q_fC=meta['converted'][0]['charge_pc']*1e3,
                           zero_deposition=meta['converted'][0]['charge_pc']==0,
                           source_sha256=hashlib.sha256(eventpath.read_bytes()).hexdigest(),
                           binary_sha256=meta['binary_sha256'])
            pair=[]
            for bit in (0,1):
                tag=f'v2-{label}-b{bit}';item=ledger['runs'].get(tag,{})
                row[f'bit{bit}_state']=item.get('state','not_started')
                row[f'bit{bit}_run_id']=item.get('run_id','')
                row[f'bit{bit}_failure_reason']=item.get('audit_error','')
                s=summaries.get(item.get('run_id'))
                if not s:continue
                if not meta:raise ValueError('TCAD response missing validated source')
                p=s['parameters'];base=bases[(ev['gate_length_um'],bit)]
                if p['source_evidence_sha256']['source-event.json']!=hashlib.sha256(eventpath.read_bytes()).hexdigest():
                    raise ValueError('Current source metadata differs from the archived response source')
                with tarfile.open(ROOT/'local_runtime/runs'/s['run_id']/'inputs.tar') as tf:
                    from analyze import read
                    if read(tf,'generator-sha256.txt').decode().strip()!=design['generator_sha256']:
                        raise ValueError('Response generator differs from frozen design')
                if base['run_id'] not in design['baseline_run_ids']:raise ValueError('Baseline outside frozen design')
                if any(base['signed_margin_V']<=eps*1e-3 for eps in design['epsilon_mV']):raise ValueError('Unreadable matched baseline')
                if (p['seed'],p['particle'],p['stored_bit'],p['parent_run'])!=(ev['seed'],ev['particle'],bit,base['run_id']):
                    raise ValueError('Response condition/parent mismatch')
                result={'label':label,'particle':ev['particle'],'seed':ev['seed'],'event_id':0,'replicate':ev['replicate'],'L_um':ev['gate_length_um'],
                    'energy_MeV':ev['energy_MeV'],'angle_deg':ev['angle_deg'],'bit':bit,'run_id':s['run_id'],'control_run_id':base['run_id'],
                    'prestrike_SN_V':s['prestrike_V'],'initial_charge_fC':s['prestrike_charge_fC'],
                    'injected_Q_fC':p['charge_pc']*1e3,'generated_Q_fC':s['radiation'].get('generated_fC',0),
                    'source_integral_relative_error':s['radiation'].get('relative_error',0),
                    'hold_end_SN_V':s['hold_end_V'],'raw_hold_drop_V':s['raw_hold_drop_V'],
                    'control_corrected_hold_drop_V':s['raw_hold_drop_V']-base['raw_hold_drop_V'],
                    'control_corrected_hold_loss_fC':s['raw_hold_loss_fC']-base['raw_hold_loss_fC'],
                    'read_precharge_SN_V':s['read_precharge_SN_V'],'D_mV':s['differential_V']*1e3,'M_mV':s['signed_margin_V']*1e3,
                    'control_D_mV':base['differential_V']*1e3,'margin_degradation_mV':(base['signed_margin_V']-s['signed_margin_V'])*1e3,
                    'newton_retries':s['newton_retries'],'solver_wallclock_s':s['wallclock_s'],'archive_sha256':s['archive_sha256']}
                for eps in design['epsilon_mV']:
                    c=classification(s['signed_margin_V'],eps*1e-3)
                    category='critical_margin' if c=='uncertain' else c
                    result[f'raw_class_{eps:g}mV']=c
                    if s['run_id']==refined.get('coarse_run_id'):
                        check=refined.get('threshold_classifications',{}).get(f'{eps:g}mV',{})
                        if check.get('numerically_uncertain'):
                            c='uncertain'
                            category='numerically_uncertain'
                            result[f'numerical_uncertainty_{eps:g}mV']='coarse/fine classifications differ; both raw values retained'
                    result[f'class_{eps:g}mV']=c;row[f'bit{bit}_class_{eps:g}mV']=c
                    result[f'outcome_{eps:g}mV']=category;row[f'bit{bit}_outcome_{eps:g}mV']=category
                responses.append(result);pair.append(result)
            row['complete_pair']=len(pair)==2
            if len(pair)==2:
                for eps in design['epsilon_mV']:
                    cs=[r[f'class_{eps:g}mV'] for r in pair]
                    row[f'any_bit_class_{eps:g}mV']='criterion_logic_flip' if 'criterion_logic_flip' in cs else ('uncertain' if 'uncertain' in cs else 'correct')
                    categories=[r[f'outcome_{eps:g}mV'] for r in pair]
                    row[f'any_bit_outcome_{eps:g}mV']=next((c for c in ('criterion_logic_flip','numerically_uncertain','critical_margin') if c in categories),'correct')
            events.append(row)
        for particle in ('alpha','proton'):
            group=[e for e in events if e['particle']==particle]
            for eps in design['epsilon_mV']:
                for bit in (0,1,'paired_any'):
                    key=f'any_bit_class_{eps:g}mV' if bit=='paired_any' else f'bit{bit}_class_{eps:g}mV'
                    classes=[e[key] for e in group if key in e]
                    reasonkey=f'any_bit_outcome_{eps:g}mV' if bit=='paired_any' else f'bit{bit}_outcome_{eps:g}mV'
                    reasons=[e[reasonkey] for e in group if reasonkey in e]
                    stats.append(dict(particle=particle,bit=bit,epsilon_mV=eps,
                                      critical_margin_n=reasons.count('critical_margin'),numerically_uncertain_n=reasons.count('numerically_uncertain'),
                                      **denominator(classes,len(group))))
    write_csv(out/'event-index.csv',events)
    write_csv(out/'responses.csv',responses)
    flat=[{k:(json.dumps(v) if isinstance(v,list) else v) for k,v in r.items()} for r in stats]
    write_csv(out/'statistics.csv',flat)
    record={'generated_utc':datetime.now(timezone.utc).isoformat(),'scope':'uncalibrated fixed-condition independent-event pilot',
            'design_sha256':hashlib.sha256(designpath.read_bytes()).hexdigest() if design else None,
            'independent_events_are_not_paired_TCAD_response_count':True,'statistics':stats,
            'official_baselines':len(baseline_rows),'completed_responses':len(responses),
            'source_event_count':sum(e['source_state']=='verified' for e in events),
            'all_raw_attempts':len(index),'verified_raw_attempts':sum(e['audit_state']=='verified' for e in index),
            'missing_intervals':'No probability interval for an incomplete planned stratum; disclose deterministic outcome bounds using all planned events',
            'raw_archives':{rid:s['archive_sha256'] for rid,s in summaries.items()}}
    (out/'statistics.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    (out/'source-hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'audit.py',HERE/'summarize.py',HERE/'statistics.py',ledgerpath] if p.exists()},indent=2)+'\n')
    print(json.dumps({k:record[k] for k in ('official_baselines','completed_responses','source_event_count','all_raw_attempts','verified_raw_attempts')}))
    return record
if __name__=='__main__':rebuild()
