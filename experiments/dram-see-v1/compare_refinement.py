"""Compare real, baseline-corrected coarse/fine results against frozen thresholds."""
import argparse
import json
from analyze import analyze,HERE


def compare(coarse_run,coarse_control,fine_run,fine_control):
    c,cb,f,fb=[analyze(r) for r in (coarse_run,coarse_control,fine_run,fine_control)]
    for actual,control in ((c,cb),(f,fb)):
        p=actual['parameters'];b=control['parameters']
        for name in ('gate_length_um','mesh_scale','step_scale','capacitance_F','temperature_K'):
            if p[name]!=b[name]:raise ValueError('Unmatched numerical control: '+name)
        if b['charge_pc']!=0:raise ValueError('Control contains a particle')
        if abs(actual['prestrike_voltage_V']-control['prestrike_voltage_V'])>1e-6:
            raise ValueError('Control initial state differs')
    for name in ('gate_length_um','angle_deg','source_event','capacitance_F','temperature_K','track_radius_um'):
        if c['parameters'][name]!=f['parameters'][name]:raise ValueError('Changed physical condition: '+name)
    if not (f['parameters']['mesh_scale']<c['parameters']['mesh_scale'] and f['parameters']['step_scale']<c['parameters']['step_scale']):
        raise ValueError('Not a simultaneous mesh/time refinement')
    vc=c['voltage_drop_V']-cb['voltage_drop_V'];vf=f['voltage_drop_V']-fb['voltage_drop_V']
    qc=(c['capacitor_loss_C']-cb['capacitor_loss_C'])*1e15
    qf=(f['capacitor_loss_C']-fb['capacitor_loss_C'])*1e15
    vt=max(.01,.05*abs(vc));qt=max(.1,.05*abs(qc))
    result={'runs':{'coarse':coarse_run,'coarse_control':coarse_control,'fine':fine_run,'fine_control':fine_control},
        'coarse_corrected_drop_V':vc,'fine_corrected_drop_V':vf,'difference_V':abs(vc-vf),'tolerance_V':vt,
        'coarse_corrected_loss_fC':qc,'fine_corrected_loss_fC':qf,'difference_fC':abs(qc-qf),'tolerance_fC':qt,
        'passed':abs(vc-vf)<=vt and abs(qc-qf)<=qt,
        'coarse_trapezoid_vs_BE_fC':abs(c['terminal_loss_trapezoid_C']-c['terminal_loss_C'])*1e15,
        'fine_trapezoid_vs_BE_fC':abs(f['terminal_loss_trapezoid_C']-f['terminal_loss_C'])*1e15,
        'coarse_source_relative_error':c['radiation']['source_integral_relative_error'],
        'fine_source_relative_error':f['radiation']['source_integral_relative_error'],
        'scope':'One representative point, simultaneous mesh/time refinement; not separate convergence orders or matrix-wide grid independence.'}
    (HERE/'data/numerical-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('coarse');p.add_argument('coarse_control');p.add_argument('fine');p.add_argument('fine_control');a=p.parse_args()
    result=compare(a.coarse,a.coarse_control,a.fine,a.fine_control)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
