"""Logged setup/probe operations; TCAD solving must use scripts/tcad.py."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tcad

def remote(label,script,timeout=120):
    folder=ROOT/'local_runtime/dram-see-v1/operations'/label
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'command.sh').write_text(script,encoding='utf8',newline='\n')
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'label':label,
            'script_sha256':hashlib.sha256(script.encode()).hexdigest(),'timeout_s':timeout}
    try:
        cfg,ssh,ip=tcad.connection()
        with (folder/'stdout.txt').open('wb') as out,(folder/'stderr.txt').open('wb') as err:
            result=subprocess.run(ssh+['bash -lc '+shlex.quote(script)],stdout=out,stderr=err,timeout=timeout)
        record['exit_code']=result.returncode
    except Exception as exc:
        record['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        record['finished_utc']=datetime.now(timezone.utc).isoformat()
        (folder/'operation.json').write_text(json.dumps(record,indent=2),encoding='utf8')
    return record,folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('script',type=Path);p.add_argument('--timeout',type=int,default=120)
    a=p.parse_args();record,folder=remote(a.label,a.script.read_text(encoding='utf8'),a.timeout)
    print(json.dumps(record,indent=2));print((folder/'stdout.txt').read_text(errors='replace')[-6000:]);print((folder/'stderr.txt').read_text(errors='replace')[-3000:])
    raise SystemExit(record['exit_code'])
