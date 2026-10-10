"""Create a non-secret index of this experiment's local evidence; never edit runs."""
from datetime import datetime,timezone
import hashlib
import json
import re
import tarfile
from analyze import ROOT,HERE,read


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runs=[]
    for folder in sorted((ROOT/'local_runtime/runs').iterdir()):
        inputs=folder/'inputs.tar'
        if not inputs.exists():continue
        with tarfile.open(inputs) as tf:
            try:p=json.loads(read(tf,'parameters.json'))
            except ValueError:continue
        if 'Uncalibrated planar 1T1C' not in p.get('interpretation',''):continue
        manifest=json.loads((folder/'manifest.json').read_text())
        record={k:manifest.get(k) for k in ('run_id','state','ssh_exit_code','results_sha256','input_sha256','runner_sha256','commit','steps')}
        record['parameters']=p
        record['local_evidence_directory']=folder.relative_to(ROOT).as_posix()
        record['files']={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in folder.iterdir() if f.is_file()}
        log=(folder/'console.log').read_text(encoding='utf8',errors='replace') if (folder/'console.log').exists() else ''
        times=re.findall(r'wallclock:\s*([0-9.]+)\s*s',log)
        record['completed_solver_wallclock_s']=float(times[-1]) if times else None
        record['solver_completion_in_console']='Sentaurus Device simulation finished' in log
        result=HERE/'data/tcad'/folder.name/'summary.json'
        if result.exists():record['analysis_summary_sha256']=sha(result)
        runs.append(record)
    operations=[]
    for file in sorted((ROOT/'local_runtime/dram-see-v1/operations').glob('*/operation.json')):
        data=json.loads(file.read_text())
        item={k:data.get(k) for k in ('label','started_utc','finished_utc','script_sha256','timeout_s','exit_code')}
        item['local_evidence_directory']=file.parent.relative_to(ROOT).as_posix()
        item['files']={f.name:{'bytes':f.stat().st_size,'sha256':sha(f)} for f in file.parent.iterdir() if f.is_file()}
        operations.append(item)
    stamp=datetime.now(timezone.utc).isoformat()
    result={'generated_utc':stamp,'scope':'Actual local evidence; COLLECTED and numerical acceptance do not establish physical calibration.',
        'runs':runs,'run_count':len(runs),'state_counts':{s:sum(r['state']==s for r in runs) for s in sorted({r['state'] for r in runs})},
        'completed_solver_wallclock_s_sum':sum(r['completed_solver_wallclock_s'] or 0 for r in runs),
        'duration_scope':'Only completion lines; aborted solve and setup time excluded.'}
    (HERE/'run-index.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    (HERE/'data/operations-index.json').write_text(json.dumps({'generated_utc':stamp,'operations':operations},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'runs':len(runs),'operations':len(operations),'states':result['state_counts']}))


if __name__=='__main__':main()
