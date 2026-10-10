"""Descriptive curve landmarks; no solver, acceptance changes, or bit classification."""
import csv,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def rows(path):
    with path.open(encoding='utf8',newline='') as f:return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
def main():
    ledger=json.loads((ROOT/'local_runtime/dram-readout-offset-d1/ledger.json').read_text())
    design=json.loads((HERE/'design-r4.json').read_text())
    active={c['tag']:ledger['runs'].get(c['tag'],{}) for c in design['cases']}
    if len(active)!=9 or any(r.get('state')!='VERIFIED' for r in active.values()):raise ValueError('Need nine completed verified active runs')
    cases={k:HERE/'data'/v['run_id'] for k,v in active.items()}
    cases['original-alpha101']=HERE.parent/'dram-see-v2/data/tcad/20261010T024342Z-v2-l025-alpha-s202610101-b1-43ecbaaa'
    sources={};metrics={};landmarks=[]
    for tag,folder in cases.items():
        cp=folder/'circuit.csv';sp=folder/'summary.json';c=rows(cp);s=json.loads(sp.read_text());r=[x for x in c if 3e-9<=x['time']<=4e-9+1e-20]
        for p in (cp,sp):sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        ds=[(x['v(bl)']-x['v(ref)'])*1e3 for x in r];late=[(x['v(bl)']-x['v(ref)'])*1e3 for x in r if x['time']>=3.5e-9]
        metrics[tag]={'run_id':folder.name,'D4_mV':ds[-1],'D_read_min_mV':min(ds),'D_read_max_mV':max(ds),'D_3p5_to_4_range_mV':max(late)-min(late)}
        for t in (3,3.05,3.08,3.10,3.20,3.25,3.5,4):
            x=min(r,key=lambda x:abs(x['time']-t*1e-9))
            landmarks.append({'tag':tag,'run_id':folder.name,'requested_time_ns':t,'actual_sample_time_ns':x['time']*1e9,'SN_V':x['v(sn)'],'BL_V':x['v(bl)'],'REF_V':x['v(ref)'],'WL_V':x['v(wl)'],'D_mV':(x['v(bl)']-x['v(ref)'])*1e3})
        if tag!='original-alpha101':
            p=folder/'device.csv';dr=[x for x in rows(p) if 3e-9<=x['time']<=4e-9+1e-20];sources[p.relative_to(ROOT).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
            metrics[tag].update(gate_peak_abs_uA=max(abs(x['gate TotalCurrent']) for x in dr)*1e6,gate_integral_fC=s['port_integrals_fC']['gate']['TotalCurrent'],gate_e_integral_fC=s['port_integrals_fC']['gate']['eCurrent'],gate_h_integral_fC=s['port_integrals_fC']['gate']['hCurrent'],body_integral_fC=s['port_integrals_fC']['body']['TotalCurrent'],offset_mV=s['offset_mV'],read_SN_V=s['read_SN_V'])
    standard=metrics['rodiag1-center050'];slow=metrics['rodiag1-wl-slow']
    result={'scope':'Post-run descriptive curve summaries under the frozen analysis; nearest stored sample, no interpolation or new decision rule. Original alpha is historical, not an extra D1 run.',
      'metrics':metrics,'slow_vs_standard':{'gate_peak_ratio':slow['gate_peak_abs_uA']/standard['gate_peak_abs_uA'],'gate_integral_ratio':slow['gate_integral_fC']/standard['gate_integral_fC'],'D_difference_mV':slow['D4_mV']-standard['D4_mV']},
      'alpha_match_D_difference_mV':metrics['rodiag1-alpha-match']['D4_mV']-metrics['original-alpha101']['D4_mV'],'sources_sha256':sources}
    (HERE/'data/diagnostic-metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    with (HERE/'data/readout-landmarks.csv').open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(landmarks[0]));w.writeheader();w.writerows(landmarks)
    print(json.dumps({'slow_vs_standard':result['slow_vs_standard'],'alpha_match_D_difference_mV':result['alpha_match_D_difference_mV']},indent=2))
if __name__=='__main__':main()
