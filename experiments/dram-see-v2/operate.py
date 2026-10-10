"""Logged v2 environment/transport operations; solver only through scripts/tcad.py."""
from datetime import datetime, timezone
import hashlib, json, shlex, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import tcad

def remote(label,script,timeout=120):
    folder=ROOT/'local_runtime/dram-see-v2/operations'/label
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'command.sh').write_text(script,encoding='utf8',newline='\n')
    rec={'started_utc':datetime.now(timezone.utc).isoformat(),'label':label,
         'script_sha256':hashlib.sha256(script.encode()).hexdigest(),'timeout_s':timeout}
    try:
        cfg,ssh,_=tcad.connection()
        with (folder/'stdout.txt').open('wb') as out,(folder/'stderr.txt').open('wb') as err:
            r=subprocess.run(ssh+['bash -lc '+shlex.quote(script)],stdout=out,stderr=err,timeout=timeout)
        rec['exit_code']=r.returncode
    except Exception as exc:
        rec['error']=repr(exc)
        raise
    finally:
        rec['finished_utc']=datetime.now(timezone.utc).isoformat()
        (folder/'operation.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf8')
    return rec,folder
