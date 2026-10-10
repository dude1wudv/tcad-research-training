"""Read-only archive checks and charge-accounting exports for offset diagnosis."""
import csv,hashlib,importlib.util,json,math,re,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'dram-see-v1'))
from analyze import read,parse_plt,integral
spec=importlib.util.spec_from_file_location('original_v2_audit',HERE.parent/'dram-see-v2/audit.py');v2=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2)
clean=v2.clean
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvout(path,rows):
    with path.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def segment(rows,a,b,first=False):
    r=clean([x for x in rows if a-1e-20<=x['time']<=b+1e-20],first=first)
    if not r or abs(r[0]['time']-a)>1e-18 or abs(r[-1]['time']-b)>1e-18:raise ValueError('Missing phase endpoints')
    return r
def qint(rows,key):return integral(rows,'time',key,right=True)*1e15
def audit(rid,export=True):
    folder=ROOT/'local_runtime/runs'/rid;m=json.loads((folder/'manifest.json').read_text())
    if m['state']!='COLLECTED' or m.get('ssh_exit_code')!=0 or sha(folder/'results.tar')!=m['results_sha256']:raise ValueError('Incomplete/bad archive')
    design=json.loads((HERE/'design.json').read_text())
    candidates=[c for c in design['cases'] if '-'+c['tag']+'-' in rid]
    if len(candidates)!=1 or m['input_sha256']!=candidates[0]['input_sha256']:raise ValueError('Run outside frozen inputs')
    with tarfile.open(folder/'inputs.tar') as tf:
        for n,h in m['input_sha256'].items():
            if hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Input hash '+n)
    with tarfile.open(folder/'results.tar') as tf:
        for n,h in m['input_sha256'].items():
            if hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Output input hash '+n)
        p=json.loads(read(tf,'parameters.json'));log=read(tf,'transient_des.log').decode(errors='replace')
        if p['schema']!='dram-readout-offset-d1' or read(tf,'exit-code.txt').strip()!=b'0' or b'ENGINEERING_RUN_COMPLETED' not in read(tf,'execution.log') or 'Sentaurus Device simulation finished' not in log:raise ValueError('Completion/provenance')
        if hashlib.sha256(read(tf,'cell_msh.tdr')).hexdigest()!=p['frozen_mesh_sha256']:raise ValueError('Mesh mismatch')
        if p['base_run_id']!=design['original_baseline']:raise ValueError('Wrong base identity')
        basefolder=ROOT/'local_runtime/runs'/p['base_run_id']
        if sha(basefolder/'results.tar')!=p['base_results_sha256']:raise ValueError('Base archive mismatch')
        with tarfile.open(basefolder/'results.tar') as base:
            if p['inherited_v2_parameters']!=json.loads(read(base,'parameters.json')):raise ValueError('Base parameters differ')
            for n in ('geometry.scm','cell_msh.tdr'):
                if read(tf,n)!=read(base,n):raise ValueError('Base mesh/geometry differs')
        if hashlib.sha256(read(tf,'geometry.scm')).hexdigest()!=p['frozen_geometry_sha256']:raise ValueError('Geometry hash')
        if any(p['case'][k]!=candidates[0][k] for k in ('tag','variant','sn_target_V','order')):raise ValueError('Case differs')
        if p['variant'] not in ('standard','wl_off','wl_slow','matched_ref'):raise ValueError('Unknown variant')
        _,raw=parse_plt(read(tf,'circuit.plt').decode());cr=clean(raw)
        _,device=parse_plt(read(tf,'access_device.plt').decode());dr=clean(device)
        ref=None
        if p['variant']=='matched_ref':_,ref=parse_plt(read(tf,'reference_device.plt').decode());ref=clean(ref)
        for rows in (cr,dr,ref or dr):
            if abs(rows[-1]['time']-4e-9)>1e-18:raise ValueError('Incomplete endpoint')
        hold=segment(raw,.95e-9,2.8e-9,True)
        if abs(hold[0]['v(sn)']-p['sn_target_V'])>.001:raise ValueError('Initial target')
        if any(abs(x['v(wl)'])>1e-8 or abs(x['v(bl)'])>1e-8 for x in hold[:-1]):raise ValueError('Hold bias')
        phases={'hold':hold,'precharge':segment(raw,2.8e-9,3e-9,True),'read':segment(raw,3e-9,4e-9)}
        start=phases['read'][0];end=cr[-1]
        if abs(start['v(sn)']-p['sn_target_V'])>.001:raise ValueError('Read-before SN differs from target')
        if ref and (abs(hold[0]['v(snr)']-.5)>.001 or abs(start['v(snr)']-.5)>.001):raise ValueError('Nonneutral reference cell')
        for row in cr:
            expected_wl=0 if p['variant']=='wl_off' else 1.8*min(1,max(0,(row['time']-3.05e-9)/((3.25e-9 if p['variant']=='wl_slow' else 3.10e-9)-3.05e-9)))
            if abs(row['v(wl)']-expected_wl)>1e-7:raise ValueError('WL waveform differs')
        if ref and any(abs(x['v(ref)'])>1e-8 for x in hold[:-1]):raise ValueError('Reference hold precharge differs')
        if abs(start['v(bl)']-.5)>1e-5 or abs(start['v(ref)']-.5)>1e-5:raise ValueError('Precharge')
        expected=0 if p['variant']=='wl_off' else 1.8
        if abs(end['v(wl)']-expected)>1e-8:raise ValueError('WL endpoint')
        balances={};maxkcl={}
        nodes=[('sn',1e-14,['i(access,sn)','i(rsn,sn)'],'i(cstore,sn)'),
               ('bl',1e-13,['i(access,bl)','i(rbl,bl)','i(rpre,bl)'],'i(cbl,bl)')]
        if ref:nodes += [('snr',1e-14,['i(reference,snr)','i(rsnr,snr)'],'i(cstoreref,snr)'),('ref',1e-13,['i(reference,ref)','i(rref,ref)','i(rpreref,ref)'],'i(cref,ref)')]
        else:nodes += [('ref',1e-13,['i(rref,ref)'],'i(cref,ref)')]
        for phase,rows in phases.items():
            for node,cap,terms,capkey in nodes:
                if (phase=='hold' and node!='sn' and node!='snr') or (phase=='precharge' and node=='ref' and ref is None):continue
                for row in rows[1:]:
                    currents=[row[k] for k in terms+[capkey]]
                    if abs(sum(currents))>1e-12+.001*sum(map(abs,currents)):raise ValueError('KCL '+phase+node)
                maxkcl[phase+'_'+node]=max(abs(sum(row[k] for k in terms+[capkey])) for row in rows[1:])
                gain=cap*(rows[-1]['v('+node+')']-rows[0]['v('+node+')'])*1e15
                q=sum(qint(rows,k) for k in terms);error=abs(gain-q)
                if error>max(.001,.001*abs(gain)):raise ValueError('BE balance '+phase+node)
                balances[phase+'_'+node]={'capacitor_gain_fC':gain,'circuit_inflow_fC':q,'residual_fC':error}
        drows=segment(device,3e-9,4e-9);crows=phases['read']
        if len(drows)!=len(crows) or any(abs(a['time']-b['time'])>1e-20 for a,b in zip(drows,crows)):raise ValueError('Device/circuit time mismatch')
        for a,b in zip(drows[1:],crows[1:]):
            for port,node in [('source','bl'),('drain','sn')]:
                if abs(a[port+' TotalCurrent']+b['i(access,'+node+')'])>1e-12+.001*abs(a[port+' TotalCurrent']):raise ValueError('Port sign mismatch')
        portq={port:{comp:qint(drows,port+' '+comp) for comp in ('TotalCurrent','eCurrent','hCurrent','DisplacementCurrent')} for port in ('source','drain','gate','body')}
        refq=None
        if ref:
            rr=segment(ref,3e-9,4e-9)
            if len(rr)!=len(crows) or any(abs(a['time']-b['time'])>1e-20 for a,b in zip(rr,crows)):raise ValueError('Reference time mismatch')
            for a,b in zip(rr[1:],crows[1:]):
                vals=[a[k+' TotalCurrent'] for k in portq]
                if abs(sum(vals))>1e-12+.001*sum(map(abs,vals)):raise ValueError('Reference terminal KCL')
                for port,node in [('source','ref'),('drain','snr')]:
                    if abs(a[port+' TotalCurrent']+b['i(reference,'+node+')'])>1e-12+.001*abs(a[port+' TotalCurrent']):raise ValueError('Reference port sign')
            refq={port:{comp:qint(rr,port+' '+comp) for comp in ('TotalCurrent','eCurrent','hCurrent','DisplacementCurrent')} for port in portq}
        for row in drows[1:]:
            vals=[row[port+' TotalCurrent'] for port in portq]
            if abs(sum(vals))>1e-12+.001*sum(map(abs,vals)):raise ValueError('Four-terminal KCL')
            for port in portq:
                if abs(row[port+' TotalCurrent']-sum(row[port+' '+c] for c in ('eCurrent','hCurrent','DisplacementCurrent')))>1e-12+.001*abs(row[port+' TotalCurrent']):raise ValueError('Current components')
        gain=sum(balances['read_'+node]['capacitor_gain_fC'] for node in ('sn','bl'))
        via_sd=-sum(portq[k]['TotalCurrent'] for k in ('source','drain'))
        gatebody=sum(portq[k]['TotalCurrent'] for k in ('gate','body'))
        if max(abs(gain-via_sd),abs(gatebody-via_sd))>max(.002,.001*abs(gain)):raise ValueError('External net charge closure')
        ideal=(1e-14*start['v(sn)']+1e-13*start['v(bl)'])/1.1e-13-start['v(ref)']
        D=end['v(bl)']-end['v(ref)'];offset=D-ideal
        predicted=gain*1e-15/1.1e-13+(end['v(bl)']-end['v(sn)'])/11-(end['v(ref)']-start['v(ref)'])
        if abs(predicted-offset)>.00001:raise ValueError('Offset charge identity')
        wall=float(re.search(r'wallclock:\s*([\d.]+) s',log).group(1))
        result={'run_id':rid,'parameters':p,'archive_sha256':m['results_sha256'],'final_time_s':end['time'],
          'initial_SN_V':hold[0]['v(sn)'],'read_SN_V':start['v(sn)'],'read_BL_V':start['v(bl)'],'final_SN_V':end['v(sn)'],'final_BL_V':end['v(bl)'],'final_REF_V':end['v(ref)'],
          'D_mV':D*1e3,'two_capacitor_D_mV':ideal*1e3,'offset_mV':offset*1e3,'charge_predicted_offset_mV':predicted*1e3,
          'SN_BL_gain_fC':gain,'source_drain_outflow_fC':via_sd,'gate_body_inflow_fC':gatebody,
          'port_integrals_fC':portq,'reference_port_integrals_fC':refq,'capacitor_balances':balances,'max_kcl_A':maxkcl,'reference_drift_mV':(end['v(ref)']-start['v(ref)'])*1e3,
          'SN_BL_endpoint_separation_mV':(end['v(sn)']-end['v(bl)'])*1e3,'newton_retries':log.count("Newton didn't converge"),'solver_s':wall,
          'interpretation':'Four-port charge balance; gate displacement establishes coupling contribution, not unique nonlinear mechanism decomposition; no bit classification.'}
    if export:
        out=HERE/'data'/rid;out.mkdir(parents=True,exist_ok=True)
        csvout(out/'circuit.csv',cr);csvout(out/'circuit-raw.csv',raw);csvout(out/'device.csv',dr)
        if ref:csvout(out/'reference-device.csv',ref)
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
