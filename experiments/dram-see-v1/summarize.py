"""Fit only the frozen training group and render actual archived measurements."""
import csv
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import ROOT,HERE,analyze
from event_contract import validate_event

def main():
    state=json.loads((ROOT/'local_runtime/dram-see-v1/batch-state.json').read_text())
    matrix=json.loads((HERE/'matrix.json').read_text())
    rows=[]
    for case in matrix['cases']:
        record=state['cases'].get(case['id'])
        if not record:continue
        summary=analyze(record['run_id']);baseline=analyze(record['baseline_run'])
        event=validate_event(ROOT/record['event'],{'label':case['id'],'gate_length_um':case['gate_length_um'],
            'particle':case['particle'],'energy_MeV':case['energy_MeV'],'angle_deg':case['angle_deg'],
            'seed':case['seed'],'event_count':case['events']})
        if not np.isclose(event['converted'][0]['charge_pc'],summary['parameters']['charge_pc'],rtol=1e-12,atol=0):
            raise ValueError('Summary and event charge mismatch')
        for archived,digest in summary['parameters'].get('source_evidence_sha256',{}).items():
            current=(ROOT/record['event']).parent/archived.removeprefix('source-')
            if hashlib.sha256(current.read_bytes()).hexdigest()!=digest:
                raise ValueError('Current event differs from archived evidence: '+archived)
        rows.append({**case,'run_id':record['run_id'],'baseline_run':record['baseline_run'],
            'charge_fC':event['converted'][0]['charge_pc']*1000,
            'raw_drop_V':summary['voltage_drop_V'],'baseline_drop_V':baseline['voltage_drop_V'],
            'corrected_drop_V':summary['voltage_drop_V']-baseline['voltage_drop_V'],
            'collected_fC':(summary['capacitor_loss_C']-baseline['capacitor_loss_C'])*1e15,
            'prestrike_V':summary['prestrike_voltage_V'],'final_V':summary['final_voltage_V'],
            'source_integral_error':summary['radiation']['source_integral_relative_error']})
    out=HERE/'data';fig=HERE/'figures';fig.mkdir(exist_ok=True)
    if not rows:raise ValueError('No verified measurements')
    with (out/'scalars.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'completed_cases':len(rows),'planned_cases':len(matrix['cases']),'complete':len(rows)==len(matrix['cases']),
            'scope':'Fixed-event EM-only planar 1T1C prototype; no device calibration or upset cross section','rows':rows}
    train=[r for r in rows if r['split']=='train']
    if len(train)==8:
        def features(r):
            q=r['charge_fC'];l=r['gate_length_um'];a=np.deg2rad(r['angle_deg'])
            return [1,q,q/l,q*np.sin(a)]
        x=np.array([features(r) for r in train]);y=np.array([r['corrected_drop_V'] for r in train])
        coef,res,rank,singular=np.linalg.lstsq(x,y,rcond=None)
        if rank!=x.shape[1]:raise ValueError('Frozen regression is rank deficient')
        frozen_path=out/'model-frozen.json'
        train_ids=[r['run_id'] for r in train]
        matrix_digest=hashlib.sha256((HERE/'matrix.json').read_bytes()).hexdigest()
        if frozen_path.exists():
            frozen=json.loads(frozen_path.read_text())
            if frozen['training_run_ids']!=train_ids or frozen['matrix_sha256']!=matrix_digest:
                raise ValueError('Frozen model training provenance changed')
            if not np.allclose(coef,frozen['coefficients'],rtol=1e-12,atol=1e-12):
                raise ValueError('Frozen coefficients changed; refuse silent refit')
        else:
            frozen={'frozen_utc':datetime.now(timezone.utc).isoformat(),'training_run_ids':train_ids,
                'matrix_sha256':matrix_digest,'coefficients':coef.tolist(),'features':matrix['regression_features'],
                'observed_case_ids_at_fit':[r['id'] for r in rows],
                'extrapolation_cases_observed_at_fit':sum(r['split']=='extrapolation_test' for r in rows),
                'scope':'Training points only; test responses never enter least squares.'}
            frozen_path.write_text(json.dumps(frozen,indent=2)+'\n',encoding='utf8')
        mean=float(y.mean())
        metrics={}
        for row in rows:
            row['predicted_drop_V']=float(np.dot(features(row),coef))
            row['error_V']=row['predicted_drop_V']-row['corrected_drop_V']
        for split in ('train','interpolation_test','extrapolation_test'):
            group=[r for r in rows if r['split']==split]
            if not group:continue
            error=np.array([r['error_V'] for r in group])
            reference=np.array([r['corrected_drop_V'] for r in group])
            metrics[split]={'n':len(group),'mae_V':float(np.mean(abs(error))),'max_abs_error_V':float(np.max(abs(error))),
                            'rmse_V':float(np.sqrt(np.mean(error**2))),
                            'training_mean_baseline_mae_V':float(np.mean(abs(reference-mean))),
                            'within_0_05_V_target':bool(np.max(abs(error))<=.05)}
        result['prediction']={'features':matrix['regression_features'],'coefficients':coef.tolist(),
            'rank':int(rank),'training_mean_V':mean,'metrics':metrics,'limitation':matrix['limitation']}
        prediction_fields=['id','split','gate_length_um','particle','angle_deg','corrected_drop_V','predicted_drop_V','error_V','run_id']
        with (out/'predictions.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=prediction_fields,extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
        figure,ax=plt.subplots(figsize=(6.5,5))
        for split,marker in [('train','o'),('interpolation_test','s'),('extrapolation_test','^')]:
            group=[r for r in rows if r['split']==split]
            ax.scatter([r['corrected_drop_V'] for r in group],[r['predicted_drop_V'] for r in group],label=split,marker=marker)
        lim=max([abs(r['corrected_drop_V']) for r in rows]+[abs(r['predicted_drop_V']) for r in rows])*1.1
        ax.plot([0,lim],[0,lim],'k--',lw=1);ax.set(xlabel='Independent TCAD voltage drop (V)',ylabel='Frozen surrogate prediction (V)',title='Prototype surrogate: held-out validation')
        ax.legend(fontsize=8);ax.grid(alpha=.25);figure.tight_layout();figure.savefig(fig/'prediction.png',dpi=180);plt.close(figure)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    figure,axes=plt.subplots(1,2,figsize=(11,4.2))
    for particle in ('alpha','proton'):
        for angle,style in [(0,'-o'),(30,'--s')]:
            group=sorted([r for r in rows if r['particle']==particle and r['angle_deg']==angle],key=lambda r:r['gate_length_um'])
            label=f'{particle}, {angle} deg'
            axes[0].plot([r['gate_length_um'] for r in group],[r['corrected_drop_V'] for r in group],style,label=label)
            axes[1].plot([r['gate_length_um'] for r in group],[r['collected_fC'] for r in group],style,label=label)
    axes[0].set(xlabel='Access gate length (um), not process node',ylabel='Baseline-corrected voltage drop (V)',title='Single-event response in the 3 ns window')
    axes[1].set(xlabel='Access gate length (um)',ylabel='Capacitor charge loss (fC)',title='Fixed 10 fF storage capacitor')
    for ax in axes:ax.grid(alpha=.25);ax.legend(fontsize=8)
    figure.tight_layout();figure.savefig(fig/'size-response.png',dpi=180);plt.close(figure)
    # Plot raw solver samples. Restarts deliberately begin at the saved 0.95 ns state.
    figure,axes=plt.subplots(1,2,figsize=(11,4.2))
    for r in [r for r in rows if r['gate_length_um']==.25]:
        file=HERE/'data/tcad'/r['run_id']/'circuit.csv'
        values=list(csv.DictReader(file.open()))
        values=[v for v in values if float(v['time'])>=.95e-9-1e-20]
        axes[0].plot([float(v['time'])*1e9 for v in values],[float(v['v(sn)']) for v in values],label=f"{r['particle']} {r['angle_deg']} deg")
        axes[1].plot([float(v['time'])*1e9 for v in values],[-float(v['i(access,sn)'])*1e6 for v in values],label=f"{r['particle']} {r['angle_deg']} deg")
    axes[0].set(xlabel='Time (ns)',ylabel='Storage node voltage (V)',title='Actual transient samples, L=0.25 um')
    axes[1].set(xlabel='Time (ns)',ylabel='Current leaving storage node (uA)',title='Actual terminal transient')
    for ax in axes:ax.grid(alpha=.25);ax.legend(fontsize=8)
    figure.tight_layout();figure.savefig(fig/'transients.png',dpi=180);plt.close(figure)
    pilot=analyze(state['parents']['0.25'])
    with (HERE/'data/tcad'/pilot['run_id']/'circuit.csv').open() as stream:
        values=list(csv.DictReader(stream))
    figure,ax=plt.subplots(figsize=(9,4))
    for key,label in [('v(wl)','Word line'),('v(bl)','Bit line'),('v(sn)','Storage node, full alpha pilot')]:
        ax.plot([float(v['time'])*1e9 for v in values],[float(v[key]) for v in values],label=label)
    control_id=state['runs']['control-l025']['run_id']
    with (HERE/'data/tcad'/control_id/'circuit.csv').open() as stream:
        control=list(csv.DictReader(stream))
    ax.plot([float(v['time'])*1e9 for v in control],[float(v['v(sn)']) for v in control],'--',label='No-ion storage node, restart from 0.95 ns')
    ax.axvline(1,color='gray',lw=.8,ls=':');ax.set(xlabel='Time (ns)',ylabel='Voltage (V)',title='Actual write, hold and particle sequence, L=0.25 um')
    ax.legend(fontsize=8);ax.grid(alpha=.25);figure.tight_layout();figure.savefig(fig/'write-hold-strike.png',dpi=180);plt.close(figure)
    print(json.dumps({'completed':len(rows),'prediction':result.get('prediction',{}).get('metrics',{})},indent=2))

if __name__=='__main__':main()
