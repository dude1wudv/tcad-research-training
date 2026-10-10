"""Collect the existing interrupted-controller run; never submit or restart a solver."""
import hashlib,json,msvcrt,shlex,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];LOCAL=ROOT/'local_runtime/dram-readout-offset-d1'
RID='20261010T082741Z-rodiag1-matched-ref-r3-99f3de31';TAG='rodiag1-matched-ref-r3'
sys.path.insert(0,str(ROOT/'scripts'));import tcad
from audit import audit
from analyze import read
from run import load,save,sha,check_preservation
def main():
    lock=(LOCAL/'controller.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        folder=ROOT/'local_runtime/runs'/RID;mp=folder/'manifest.json';m=json.loads(mp.read_text());l=load()
        if m['state']!='RUNNING' or l['runs'][TAG]['state']!='RUNNING':raise ValueError('Not the interrupted running record')
        if (folder/'results.tar').exists():raise ValueError('Existing archive; inspect without overwrite')
        check_preservation();cfg,ssh,_=tcad.connection();remote=m['remote_directory'];q=shlex.quote(remote)
        command="set -eu\ncd "+q+"\ntest -f exit-code.txt\ntest \"$(cat exit-code.txt)\" = 0\ngrep -q 'Sentaurus Device simulation finished' transient_des.log\n"
        for step in m['steps']:
            for n in step['outputs']:command+='test -s '+shlex.quote(n)+'\n'
        command+="ps -eo pid,comm,args | awk '$2 ~ /^(sdevice|sde|snmesh|transport)$/ {print; active=1} END {exit active}'\n"
        command+='sha256sum '+ ' '.join(shlex.quote(n) for n in m['input_sha256'])+'\n'
        r=tcad.remote(ssh,command,capture_output=True,text=True,timeout=45)
        expected={n:h for n,h in m['input_sha256'].items()};actual={line.split(None,1)[1].strip():line.split()[0] for line in r.stdout.splitlines()}
        if actual!=expected:raise ValueError('Remote inputs differ or solver active')
        recovery=folder/'collection-recovery';recovery.mkdir(exist_ok=False)
        (recovery/'manifest-before.json').write_bytes(mp.read_bytes());(recovery/'ledger-before.json').write_bytes((LOCAL/'ledger.json').read_bytes())
        (recovery/'preflight.sh').write_text(command,encoding='utf8');(recovery/'preflight-stdout.txt').write_text(r.stdout);(recovery/'preflight-stderr.txt').write_text(r.stderr)
        temporary=folder/'recovered-results.tar.partial'
        with temporary.open('xb') as stream:collected=tcad.remote(ssh,'tar -cf - -C '+q+' .',stdout=stream,stderr=__import__('subprocess').PIPE,timeout=300)
        with tarfile.open(temporary) as tf:
            if read(tf,'exit-code.txt').strip()!=b'0' or b'Sentaurus Device simulation finished' not in read(tf,'transient_des.log'):raise ValueError('Remote completion absent in collected archive')
            if read(tf,'run.sh')!=(folder/'run.sh').read_bytes():raise ValueError('Original runner script changed')
            for n,h in expected.items():
                if hashlib.sha256(read(tf,n)).hexdigest()!=h:raise ValueError('Collected input differs')
        temporary.rename(folder/'results.tar')
        m.update(state='COLLECTED',results_sha256=sha(folder/'results.tar'),original_execution_ssh_exit_code=None,
                 remote_runner_exit_code=0,ssh_exit_code=collected.returncode,ssh_exit_code_scope='recovery_collection_only',
                 recovery_note='Local controller was interrupted; original execution SSH exit is unknown. Same remote run completed, no resubmission.',
                 recovered_utc=datetime.now(timezone.utc).isoformat())
        mp.write_text(json.dumps(m,indent=2)+'\n');s=audit(RID)
        item=l['runs'][TAG];item.update(state='VERIFIED',run_id=RID,solver_s=s['solver_s'],runner_exit_code=None,
            recovery_collection_ssh_exit_code=collected.returncode,remote_runner_exit_code=0,
            finished_utc=datetime.now(timezone.utc).isoformat(),recovery_note=m['recovery_note'])
        save(l)
        proof={'run_id':RID,'collector_sha256':sha(Path(__file__)),'missing_execution_stream_marker_preserved':True,'no_resubmission':True,'original_execution_ssh_exit_code':None,'remote_runner_exit_code':0,
               'collection_ssh_exit_code':collected.returncode,'archive_sha256':m['results_sha256'],'D_mV':s['D_mV'],'solver_s':s['solver_s']}
        (recovery/'recovery.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
