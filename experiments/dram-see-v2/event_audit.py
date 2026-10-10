"""Single independent v2 event, including legitimate zero deposition."""
import csv,hashlib,io,json,math
BINARY_SHA='830cd8480bc11a27b243f6662d0e64a71d5b382a45bfd1e80f8e199bfdfdb67f'
SOURCE_SHA='8f3ec870dad0905be7516bf657ed033d8cf5c5ade7cef938a941622b2f483ce2'
def validate_bytes(metadata,files,expected=None):
    ev=json.loads(metadata)
    if ev.get('binary_sha256')!=BINARY_SHA or ev.get('source_sha256')!=SOURCE_SHA:
        raise ValueError('Transport binary/source differs from the declared existing build')
    if ev.get('conversion_eV_per_pair')!=3.6 or ev.get('launch_position_um')!=[ev['gate_length_um']+.45,-.001,0]:
        raise ValueError('Conversion or primary launch differs')
    if ev['operation_exit_code']!=0 or ev['event_count']!=1:raise ValueError('Need one complete event')
    if set(ev['files_sha256'])!={'steps.csv','events.csv'}:raise ValueError('Wrong file set')
    for n,h in ev['files_sha256'].items():
        if hashlib.sha256(files[n]).hexdigest()!=h:raise ValueError('Source file hash mismatch')
    for k,v in (expected or {}).items():
        if ev[k]!=v:raise ValueError('Source condition mismatch '+k)
    if ev['particle'] not in ('alpha','proton') or ev['angle_deg']!=0 or ev['energy_MeV']!=5:
        raise ValueError('Outside frozen v2 transport')
    if not (0<ev['seed']<2147483647):raise ValueError('Bad random seed')
    eventreader=csv.DictReader(io.StringIO(files['events.csv'].decode()))
    stepreader=csv.DictReader(io.StringIO(files['steps.csv'].decode()))
    if not {'event','ionizing_MeV','niel_MeV','primary_path_um'}<=set(eventreader.fieldnames or []):raise ValueError('Missing event fields')
    if not {'event','track','parent','x_um','y_um','z_um','t_ns','step_um','edep_MeV','niel_MeV','ionizing_MeV'}<=set(stepreader.fieldnames or []):
        raise ValueError('Missing step fields')
    rows=list(eventreader);steps=list(stepreader)
    if len(rows)!=1 or rows[0]['event']!='0' or any(x['event']!='0' for x in steps):raise ValueError('Bad event identity')
    if any(not math.isfinite(float(v)) for row in rows+steps for v in row.values()):raise ValueError('Nonfinite transport output')
    e=float(rows[0]['ionizing_MeV']);values=[float(x['ionizing_MeV']) for x in steps]
    if not math.isfinite(e) or not 0<=e<=5 or not all(math.isfinite(v) and v>=0 for v in values):raise ValueError('Bad energy')
    if not math.isclose(sum(values),e,rel_tol=1e-10,abs_tol=1e-15):raise ValueError('Energy accounting')
    niel=float(rows[0]['niel_MeV'])
    if niel<0 or not math.isclose(sum(float(x['niel_MeV']) for x in steps),niel,rel_tol=1e-10,abs_tol=1e-15):
        raise ValueError('Nonionizing energy accounting')
    if any(float(x[k])<0 for x in steps for k in ('t_ns','step_um','edep_MeV','niel_MeV')):raise ValueError('Negative transport observable')
    q=e*1e6/3.6*1.602176634e-19*1e12
    if len(ev['converted'])!=1:raise ValueError('Wrong converted count')
    c=ev['converted'][0]
    if c['event']!=0:raise ValueError('Converted event identity differs')
    for k,v in {'ionizing_MeV':e,'charge_pc':q,'track_length_um':1.2,'let_pc_per_um':q/1.2}.items():
        if not math.isclose(c[k],v,rel_tol=1e-10,abs_tol=1e-15):raise ValueError('Conversion mismatch '+k)
    if ev['surface_impact_um']!=[ev['gate_length_um']+.45,0,0] or ev['direction']!=[0,1,0]:raise ValueError('Position/direction mismatch')
    return ev
