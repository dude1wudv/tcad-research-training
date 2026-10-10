"""Recompute v2 observables and contracts from the archived raw solver data."""
import argparse,csv,hashlib,json,math,re,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'dram-see-v1'))
from analyze import read,parse_plt,integral,at
sys.path.insert(0,str(HERE))
from event_audit import validate_bytes

def clean(rows,first=False):
    out=[]
    for r in rows:
        if out and r['time']<out[-1]['time']-1e-20:raise ValueError('Time went backwards')
        if out and r['time']==out[-1]['time']:
            # DC operating-point rows at t=0 precede the explicit transient
            # initialization. Preserve them in raw CSV; require continuity at
            # every positive-time boundary, including restart and precharge.
            if r['time']>0 and any(abs(r[k]-out[-1][k])>1e-6 for k in r if k.startswith('v(')):
                raise ValueError('Discontinuous node voltage at duplicate timestamp')
            if not first:out[-1]=r
        else:out.append(r)
    return out

def classification(m,epsilon=.005):
    if not math.isfinite(m) or not math.isfinite(epsilon) or epsilon<=0:raise ValueError('Nonfinite margin or invalid threshold')
    return 'correct' if m>epsilon else ('criterion_logic_flip' if m<-epsilon else 'uncertain')

def audit(rid,export=True):
    folder=ROOT/'local_runtime/runs'/rid
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['state']!='COLLECTED' or manifest['ssh_exit_code']!=0:raise ValueError('Unsuccessful archive '+rid)
    digest=hashlib.sha256((folder/'results.tar').read_bytes()).hexdigest()
    if digest!=manifest['results_sha256']:raise ValueError('Archive hash changed')
    with tarfile.open(folder/'inputs.tar') as tf:
        for n,h in manifest['input_sha256'].items():
            if hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Frozen input hash '+n)
    with tarfile.open(folder/'results.tar') as tf:
        for n,h in manifest['input_sha256'].items():
            if hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Results input differs from frozen input '+n)
        if read(tf,'exit-code.txt').strip()!=b'0' or b'ENGINEERING_RUN_COMPLETED' not in read(tf,'execution.log'):raise ValueError('No remote completion')
        log=read(tf,'transient_des.log').decode(errors='replace')
        if 'Sentaurus Device simulation finished' not in log:raise ValueError('No solver completion')
        p=json.loads(read(tf,'parameters.json'))
        if p['schema']!='dram-see-v2':raise ValueError('Wrong schema')
        if p.get('model_contract') and hashlib.sha256(json.dumps(p['model_contract'],sort_keys=True).encode()).hexdigest()!=p['model_contract_sha256']:
            raise ValueError('Model contract hash invalid')
        if p.get('model_contract'):
            if any(p[k]!=v for k,v in p['model_contract'].items() if k in p):raise ValueError('Model contract parameters differ')
            if hashlib.sha256(read(tf,'geometry.scm')).hexdigest()!=p['model_contract']['geometry_sha256']:
                raise ValueError('Geometry differs from model contract')
        cn,raw=parse_plt(read(tf,'circuit.plt').decode());cr=clean(raw)
        dn,dr=parse_plt(read(tf,'access_device.plt').decode());dr=clean(dr)
        if any(not math.isfinite(v) for rows in (raw,dr) for row in rows for v in row.values()):
            raise ValueError('Nonfinite raw solver output')
        if abs(cr[-1]['time']-4e-9)>1e-18:raise ValueError('Readout time not reached')
        hold=clean([r for r in raw if .95e-9-1e-20<=r['time']<=2.8e-9+1e-20],first=True)
        if abs(hold[0]['time']-.95e-9)>1e-18 or abs(hold[-1]['time']-2.8e-9)>1e-18:raise ValueError('Hold endpoints missing')
        pre=hold[0]['v(sn)'];endhold=hold[-1]['v(sn)']
        if abs(pre-p['target_voltage_V'])>.001:raise ValueError('Nonuniform initialization')
        if any(max(abs(r['v(bl)']),abs(r['v(wl)']))>1e-8 for r in hold[:-1]):raise ValueError('Wrong hold bias')
        before=[r for r in raw if abs(r['time']-3e-9)<1e-18]
        if not before or abs(before[0]['v(bl)']-.5)>p['precharge_tolerance_V'] or abs(before[0]['v(ref)']-.5)>1e-8:raise ValueError('Precharge missing')
        sharing=clean([r for r in raw if r['time']>=3e-9-1e-20])
        # Incoming step currents belong to the first row at the phase end;
        # a same-time switch reprint has new resistor current but stale BE
        # capacitor current. It is not a newly converged time step.
        precharging=clean([r for r in raw if 2.8e-9-1e-20<=r['time']<=3e-9+1e-20],first=True)
        if abs(cr[-1]['v(wl)']-1.8)>1e-8:raise ValueError('Read wordline not active')
        kcl={}
        for name,rows,keys in [('sn_hold',hold,('i(access,sn)','i(cstore,sn)','i(rsn,sn)')),
                              ('sn_read',sharing,('i(access,sn)','i(cstore,sn)','i(rsn,sn)')),
                              ('sn_precharge',precharging,('i(access,sn)','i(cstore,sn)','i(rsn,sn)')),
                              ('bl_precharge',precharging,('i(access,bl)','i(cbl,bl)','i(rbl,bl)','i(rpre,bl)')),
                              ('bl_read',sharing,('i(access,bl)','i(cbl,bl)','i(rbl,bl)','i(rpre,bl)')),
                              ('ref_read',sharing,('i(cref,ref)','i(rref,ref)'))]:
            solved=rows[1:]
            v=max(abs(sum(r[k] for k in keys)) for r in solved)
            # Use each converged step's current scale, not the phase peak.
            if any(abs(sum(r[k] for k in keys))>1e-12+.001*sum(abs(r[k]) for k in keys) for r in solved):
                raise ValueError('Local KCL mismatch '+name+': '+str(v))
            kcl[name]=v
        balances={}
        for name,rows,cap,vkey,ikeys in [('sn_hold',hold,1e-14,'v(sn)',('i(access,sn)','i(rsn,sn)')),
                                        ('sn_read',sharing,1e-14,'v(sn)',('i(access,sn)','i(rsn,sn)')),
                                        ('sn_precharge',precharging,1e-14,'v(sn)',('i(access,sn)','i(rsn,sn)')),
                                        ('bl_precharge',precharging,1e-13,'v(bl)',('i(access,bl)','i(rbl,bl)','i(rpre,bl)')),
                                        ('bl_read',sharing,1e-13,'v(bl)',('i(access,bl)','i(rbl,bl)','i(rpre,bl)'))]:
            delta=cap*(rows[0][vkey]-rows[-1][vkey])
            loss=-sum(integral(rows,'time',k,right=True) for k in ikeys)
            residual=abs(delta-loss)
            if residual>max(1e-18,.001*abs(delta)):raise ValueError('BE charge mismatch '+name+': '+str(residual))
            balances[name]={'capacitor_loss_C':delta,'terminal_loss_C':loss,'residual_C':residual}
        radiation={};event=None
        if not math.isfinite(p['charge_pc']) or p['charge_pc']<0:
            raise ValueError('Invalid injected charge')
        if p.get('source_event') or p['charge_pc'] or p.get('particle'):
            if set(p.get('source_evidence_sha256',{}))!={'source-event.json','source-steps.csv','source-events.csv'}:
                raise ValueError('Particle response requires complete frozen source evidence, including zero deposition')
        if p.get('source_evidence_sha256'):
            b={n:read(tf,n) for n in p['source_evidence_sha256']}
            for n,content in b.items():
                if hashlib.sha256(content).hexdigest()!=p['source_evidence_sha256'][n] or p['source_evidence_sha256'][n]!=manifest['input_sha256'][n]:raise ValueError('Event frozen hash '+n)
            event=validate_bytes(b['source-event.json'],{'steps.csv':b['source-steps.csv'],'events.csv':b['source-events.csv']},
                                 {k:p[k] for k in ('gate_length_um','particle','energy_MeV','seed','angle_deg')})
            if not math.isclose(event['converted'][0]['charge_pc'],p['charge_pc'],rel_tol=1e-12,abs_tol=1e-15):raise ValueError('Wrong Q')
        if p['charge_pc']:
            gen=[n for n in dn if 'HeavyIonGeneration' in n]
            if len(gen)!=1:raise ValueError('Missing source integral')
            generated=integral(dr,'time',gen[0])*1e-12*1.602176634e-19;target=p['charge_pc']*1e-12
            error=abs(generated-target)/target
            if error>.05:raise ValueError('Source integral >5%')
            radiation={'generated_fC':generated*1e15,'target_fC':target*1e15,'relative_error':error}
        if p['parent_run']:
            pm=json.loads((ROOT/'local_runtime/runs'/p['parent_run']/'manifest.json').read_text())
            lineage=json.loads(read(tf,'restart-provenance.json'))
            if pm['state']!='COLLECTED' or pm.get('ssh_exit_code')!=0:
                raise ValueError('Restart parent did not complete successfully')
            if lineage.get('parent_run')!=p['parent_run'] or lineage.get('time_s')!=p['prestrike_s']:
                raise ValueError('Restart identity/checkpoint mismatch')
            if set(lineage.get('copied_sha256',{}))!={'cell_msh.tdr','charged_access_des.sav','charged_circuit_des.sav'}:
                raise ValueError('Restart requires mesh and both saved states')
            if lineage['archive_sha256']!=pm['results_sha256']:raise ValueError('Parent changed')
            if hashlib.sha256((ROOT/'local_runtime/runs'/p['parent_run']/'results.tar').read_bytes()).hexdigest()!=pm['results_sha256']:
                raise ValueError('Parent archive hash invalid')
            with tarfile.open(ROOT/'local_runtime/runs'/p['parent_run']/'results.tar') as pt:
                parent=json.loads(read(pt,'parameters.json'))
                if parent['parent_run'] or parent['charge_pc'] or parent.get('source_event'):
                    raise ValueError('Restart parent must be a full no-particle control')
                for k in ('stored_bit','gate_length_um','mesh_scale','step_scale'):
                    if parent[k]!=p[k]:raise ValueError('Incompatible restart '+k)
                if parent.get('model_contract_sha256')!=p.get('model_contract_sha256') or not p.get('model_contract_sha256'):
                    raise ValueError('Full parent model contract differs')
                for n,h in lineage['copied_sha256'].items():
                    if hashlib.sha256(read(pt,n)).hexdigest()!=h or hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Copied parent mismatch')
        d=cr[-1]['v(bl)']-cr[-1]['v(ref)'];margin=(2*p['stored_bit']-1)*d
        completed=re.findall(r'Sentaurus Device simulation finished.*',log)
        wall=re.search(r'wallclock:\s*([\d.]+) s',log)
        s={'run_id':rid,'archive_sha256':digest,'parameters':p,'solver_completion':completed[-1],
           'wallclock_s':float(wall.group(1)) if wall else None,'final_time_s':cr[-1]['time'],
           'prestrike_V':pre,'initial_error_V':pre-p['target_voltage_V'],'prestrike_charge_fC':pre*p['capacitance_F']*1e15,
           'hold_end_V':endhold,'raw_hold_drop_V':pre-endhold,'raw_hold_loss_fC':(pre-endhold)*10,
           'read_precharge_SN_V':before[0]['v(sn)'],'final_SN_V':cr[-1]['v(sn)'],
           'final_BL_V':cr[-1]['v(bl)'],'final_REF_V':cr[-1]['v(ref)'],'differential_V':d,'signed_margin_V':margin,
           'classification':classification(margin,p['read_threshold_V']),
           'decoded_bit':1 if d>.005 else (0 if d<-.005 else None),
           'ideal_sharing_D_V':(1e-14/(1e-14+1e-13))*(before[0]['v(sn)']-.5),
           'max_kcl_A':kcl,'BE_charge_checks':balances,'radiation':radiation,
           'boundary_current_reprints':'same-time switched rows retained in raw CSV; incoming first endpoint for precharge BE; phase-start rows excluded from time-step KCL',
           'newton_retries':log.count("Newton didn't converge"),'scope':'criterion decision only; no physical latch/restore or calibration'}
    if export:
        dest=HERE/'data/tcad'/rid;dest.mkdir(parents=True,exist_ok=True)
        for name,names,rows in [('circuit.csv',cn,cr),('circuit-raw.csv',cn,raw),('device.csv',dn,dr)]:
            with (dest/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)
        (dest/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
    return s
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args();print(json.dumps(audit(a.run_id),indent=2))
