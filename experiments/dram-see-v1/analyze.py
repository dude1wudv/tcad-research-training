"""Audit archived raw solver output before exporting prototype measurements."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def parse_plt(text):
    info=re.search(r'datasets\s*=\s*\[(.*?)\]',text,re.S)
    data=re.search(r'\bData\s*\{(.*?)\}',text,re.S)
    if not info or not data:raise ValueError('Missing complete DF-ISE data')
    names=re.findall(r'"([^"]+)"',info.group(1))
    vals=[float(x) for x in data.group(1).split()]
    if not names or len(set(names))!=len(names) or not vals or len(vals)%len(names) or not all(map(math.isfinite,vals)):
        raise ValueError('Malformed, truncated or nonfinite DF-ISE values')
    return names,[dict(zip(names,vals[i:i+len(names)])) for i in range(0,len(vals),len(names))]

def read(tf,name):
    matches=[m for m in tf.getmembers() if m.isfile() and m.name.removeprefix('./')==name]
    if len(matches)!=1:raise ValueError('Missing or ambiguous archive member '+name)
    return tf.extractfile(matches[0]).read()

def clean_times(rows,key):
    clean=[]
    for row in rows:
        if clean and row[key]<clean[-1][key]-1e-20:raise ValueError('Time moved backwards')
        if clean and row[key]==clean[-1][key]:clean[-1]=row
        else:clean.append(row)
    return clean

def integral(rows,x,y,right=False):
    return sum((b[x]-a[x])*(b[y] if right else (a[y]+b[y])/2) for a,b in zip(rows,rows[1:]))

def at(rows,time_key,key,t):
    for a,b in zip(rows,rows[1:]):
        if a[time_key]<=t<=b[time_key]:
            f=(t-a[time_key])/(b[time_key]-a[time_key])
            return a[key]+f*(b[key]-a[key])
    raise ValueError('Time outside observed range')

def analyze(run_id,export=True):
    folder=ROOT/'local_runtime/runs'/run_id
    m=json.loads((folder/'manifest.json').read_text())
    if m.get('state')!='COLLECTED' or m.get('ssh_exit_code')!=0:raise ValueError('Run not collected successfully: '+run_id)
    digest=hashlib.sha256((folder/'results.tar').read_bytes()).hexdigest()
    if digest!=m['results_sha256']:raise ValueError('Archive hash mismatch')
    with tarfile.open(folder/'results.tar') as tf:
        if read(tf,'exit-code.txt').strip()!=b'0':raise ValueError('Remote failure')
        if b'ENGINEERING_RUN_COMPLETED' not in read(tf,'execution.log'):raise ValueError('No run completion')
        log=read(tf,'transient_des.log').decode(errors='replace')
        if 'Sentaurus Device simulation finished' not in log:raise ValueError('No solver completion')
        p=json.loads(read(tf,'parameters.json'))
        event_binding='not_applicable'
        if p['charge_pc']:
            from event_contract import validate_bytes,validate_event
            expected={'gate_length_um':p['gate_length_um'],'angle_deg':p['angle_deg']}
            if p.get('source_evidence_sha256'):
                evidence={name:read(tf,name) for name in p['source_evidence_sha256']}
                for name,content in evidence.items():
                    actual=hashlib.sha256(content).hexdigest()
                    if actual!=p['source_evidence_sha256'][name] or actual!=m['input_sha256'][name]:
                        raise ValueError('Frozen source evidence hash mismatch')
                event=validate_bytes(evidence['source-event.json'],
                    {'steps.csv':evidence['source-steps.csv'],'events.csv':evidence['source-events.csv']},expected)
                event_binding='archived_input_hashes'
            else:
                event=validate_event(ROOT/p['source_event'],expected)
                event_binding='legacy_external_event_crosscheck; metadata was not frozen in TCAD input'
            if not math.isclose(event['converted'][0]['charge_pc'],p['charge_pc'],rel_tol=1e-12):
                raise ValueError('Event charge differs from archived TCAD source')
        cn,cr=parse_plt(read(tf,'circuit.plt').decode());cr=clean_times(cr,'time')
        dn,dr=parse_plt(read(tf,'access_device.plt').decode());dr=clean_times(dr,'time')
        if not math.isclose(cr[-1]['time'],3e-9,abs_tol=1e-18):raise ValueError('Final time not reached')
        if max(abs(cr[-1][k]) for k in ('v(bl)','v(wl)'))>1e-8:raise ValueError('Not in hold state')
        pre=at(cr,'time','v(sn)',.95e-9)
        if not (.5<pre<1.2):raise ValueError('Stored-high baseline missing')
        if p.get('restart_run'):
            parent=analyze(p['restart_run'],export=False)
            provenance=json.loads(read(tf,'restart-provenance.json'))
            if provenance['archive_sha256']!=parent['archive_sha256']:raise ValueError('Restart lineage mismatch')
            if abs(pre-parent['prestrike_voltage_V'])>1e-6:raise ValueError('Restart initial voltage changed')
        elif at(cr,'time','v(sn)',.25e-9)<.8:raise ValueError('Write operation did not charge capacitor')
        hold=[r for r in cr if r['time']>=.95e-9-1e-20]
        if not math.isclose(hold[0]['time'],.95e-9,abs_tol=1e-18):raise ValueError('No exact prestrike sample')
        kcl=max(abs(sum(r[k] for k in ('i(access,sn)','i(cstore,sn)','i(rleak,sn)'))) for r in hold)
        peak=max(abs(r['i(access,sn)']) for r in hold)
        if kcl>max(1e-12,1e-3*peak):raise ValueError('Circuit KCL exceeded tolerance')
        delta_q=p['capacitance_F']*(pre-cr[-1]['v(sn)'])
        terminal_q=-integral(hold,'time','i(access,sn)',right=True)
        balance=abs(delta_q-terminal_q)
        if balance>max(1e-18,.001*abs(delta_q)):raise ValueError('Capacitor/terminal charge mismatch')
        radiation={}
        if p['charge_pc']:
            gen=[n for n in dn if 'HeavyIonGeneration' in n]
            if len(gen)!=1:raise ValueError('Missing unique radiation generation integral')
            # SDevice volume integral uses um^3; density cm^-3, time s.
            generated=integral(dr,'time',gen[0])*1e-12*1.602176634e-19
            target=p['charge_pc']*1e-12
            radiation={'generation_dataset':gen[0],
                       'generated_C':generated,'target_C':target,'source_integral_relative_error':abs(generated-target)/target,
                       'integration':'trapezoid of spatial generation integral over actual solver times'}
            if radiation['source_integral_relative_error']>.05:raise ValueError('Source integral outside 5% tolerance: '+str(radiation))
        tdrs={n:hashlib.sha256(read(tf,n)).hexdigest() for n in ('cell_msh.tdr','prestrike_access_des.tdr','strike_access_des.tdr','final_access_des.tdr')}
    summary={'run_id':run_id,'parameters':p,'archive_sha256':digest,'input_sha256':m['input_sha256'],
             'solver_finished':True,'final_time_s':cr[-1]['time'],'circuit_samples':len(cr),'device_samples':len(dr),
             'prestrike_voltage_V':pre,'final_voltage_V':cr[-1]['v(sn)'],
             'min_poststrike_voltage_V':min(r['v(sn)'] for r in hold),
             'voltage_drop_V':pre-cr[-1]['v(sn)'],'capacitor_loss_C':delta_q,'terminal_loss_C':terminal_q,
             'terminal_loss_trapezoid_C':-integral(hold,'time','i(access,sn)'),
             'charge_balance_residual_C':balance,'max_kcl_residual_A':kcl,'peak_hold_current_A':peak,
             'radiation':radiation,'tdr_sha256':tdrs,'scope':'Engineering and stated numerical contracts; uncalibrated 1T1C model'}
    summary['event_binding']=event_binding
    if export:
        out=HERE/'data/tcad'/run_id;out.mkdir(parents=True,exist_ok=True)
        for name,names,rows in [('circuit.csv',cn,cr),('device.csv',dn,dr)]:
            with (out/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args()
    print(json.dumps(analyze(a.run_id),indent=2))
