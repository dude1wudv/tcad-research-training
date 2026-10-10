"""Independent full/restart equality and matched half-step response verification."""
import argparse,json
from pathlib import Path
from run_stage import load,record_run
from audit import audit,classification
HERE=Path(__file__).resolve().parent;OUT=HERE/'data/summary/numerical-checks.json'

def saved():return json.loads(OUT.read_text()) if OUT.exists() else {'checks':{},'scope':'numerical engineering checks; no physical calibration'}
def save(record):
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(record,indent=2)+'\n')

def compare_readout(coarse,fine,base,finebase,thresholds):
    delta=abs(fine['differential_V']-coarse['differential_V'])
    basedelta=abs(finebase['differential_V']-base['differential_V'])
    corrected=abs((fine['differential_V']-finebase['differential_V'])-(coarse['differential_V']-base['differential_V']))
    classes={}
    for eps in thresholds:
        c=classification(coarse['signed_margin_V'],eps*1e-3)
        f=classification(fine['signed_margin_V'],eps*1e-3)
        bc=classification(base['signed_margin_V'],eps*1e-3)
        bf=classification(finebase['signed_margin_V'],eps*1e-3)
        classes[f'{eps:g}mV']={'coarse':c,'fine':f,'control_coarse':bc,'control_fine':bf,
                             'same_class':c==f,'numerically_uncertain':c!=f}
    stable=all(x['same_class'] and x['control_coarse']==x['control_fine']=='correct' for x in classes.values())
    return {'D_difference_mV':delta*1e3,'control_D_difference_mV':basedelta*1e3,
            'control_corrected_D_difference_mV':corrected*1e3,'D_tolerance_mV':.5,
            'threshold_classifications':classes,'all_threshold_classes_stable':stable,
            'passed':max(delta,basedelta,corrected)<=.0005 and stable}

def equivalence():
    design=json.loads((HERE/'stats-design.json').read_text());ev=next(e for e in design['events'] if e['particle']=='alpha' and e['replicate']==0)
    tag='v2-'+ev['label']+'-b1';item=load()['runs'][tag]
    if item['state']!='VERIFIED':raise ValueError('Need first frozen alpha bit1 response')
    restart=audit(item['run_id'],export=False);event=restart['parameters']['source_event']
    full=record_run('v2-validate-full-'+ev['label']+'-b1',.25,1,event=event)
    delta=abs(full['differential_V']-restart['differential_V'])
    pre=abs(full['prestrike_V']-restart['prestrike_V'])
    record=saved();record['checks']['full_restart']={'full_run_id':full['run_id'],'restart_run_id':restart['run_id'],
       'D_difference_mV':delta*1e3,'prestrike_difference_mV':pre*1e3,'D_tolerance_mV':.1,'initial_tolerance_mV':.001,
       'passed':delta<=.0001 and pre<=.000001,'same_source_event':ev['label'],'bit':1}
    save(record)
    if not record['checks']['full_restart']['passed']:raise ValueError('Full/restart numerical equivalence failed')
    print(json.dumps(record['checks']['full_restart']))

def refine():
    design=json.loads((HERE/'stats-design.json').read_text());ledger=load();candidates=[]
    for ev in design['events']:
        for bit in (0,1):
            item=ledger['runs'].get('v2-'+ev['label']+f'-b{bit}',{})
            if item.get('state')!='VERIFIED':raise ValueError('Refine only after the entire frozen pilot is complete')
            s=audit(item['run_id'],export=False)
            candidates.append((min(abs(abs(s['signed_margin_V'])-eps*1e-3) for eps in design['epsilon_mV']),ev['label'],bit,s))
    _,label,bit,coarse=min(candidates,key=lambda x:x[:3])
    baseitem=ledger['runs'][f'v2-base-l025-b{bit}'];base=audit(baseitem['run_id'],export=False)
    finebase=record_run(f'v2-validate-halfstep-control-b{bit}',.25,bit,step=.5)
    fine=record_run(f'v2-validate-halfstep-{label}-b{bit}',.25,bit,event=coarse['parameters']['source_event'],parent=finebase['run_id'],step=.5)
    comparison=compare_readout(coarse,fine,base,finebase,design['epsilon_mV'])
    record=saved();record['checks']['half_step']={'selection':'closest absolute signed margin to any predeclared 2.5/5/10 mV boundary among all frozen completed responses; validation selection only, no change to event cohort',
       'coarse_run_id':coarse['run_id'],'fine_run_id':fine['run_id'],'coarse_control_run_id':base['run_id'],
       'fine_control_run_id':finebase['run_id'],'coarse_D_mV':coarse['differential_V']*1e3,'fine_D_mV':fine['differential_V']*1e3,
       **comparison,
       'coarse_class':coarse['classification'],'fine_class':fine['classification'],
       'same_class':coarse['classification']==fine['classification'],
       'only_temporal_refinement':True,'mesh_refinement_unverified':True,'bit':bit,'event':label}
    save(record)
    if not record['checks']['half_step']['passed']:raise ValueError('Half-step readout tolerance failed')
    print(json.dumps(record['checks']['half_step']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('check',choices=['equivalence','refine']);a=p.parse_args()
    equivalence() if a.check=='equivalence' else refine()
