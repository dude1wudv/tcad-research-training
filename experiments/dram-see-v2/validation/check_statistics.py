"""Pure helper tests. AST load avoids running summary/plot/runner side effects."""
import ast,hashlib,json,math
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
env={'math':math}
for filename,names in [('statistics.py',{'wilson','zero_upper','summarize_classes'}),('summarize.py',{'denominator'}),('audit.py',{'classification'})]:
    tree=ast.parse((BASE/filename).read_text())
    selected=ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names],type_ignores=[])
    exec(compile(selected,str(BASE/filename),'exec'),env)
checks=0
for n in range(1,7):
    for k in range(n+1):
        for u in range(n-k+1):
            classes=['criterion_logic_flip']*k+['uncertain']*u+['correct']*(n-k-u)
            s=env['denominator'](classes,n)
            assert s['complete_planned_stratum'] and s['n_independent_events']==n
            assert s['definite_flip']==k and s['uncertain']==u
            for count,key in [(k,'wilson_95_definite'),(k+u,'wilson_95_flip_or_uncertain')]:
                # Wilson endpoints independently solve score-test quadratic.
                z=1.959963984540054;a=n+z*z;b=-(2*count+z*z);c=count*count/n
                disc=b*b-4*a*c
                expected=[max(0,(-b-math.sqrt(max(0,disc)))/(2*a)),min(1,(-b+math.sqrt(max(0,disc)))/(2*a))]
                assert all(abs(x-y)<1e-14 for x,y in zip(expected,s[key]))
            assert (s['zero_definite_flip_exact_one_sided_95_upper'] is not None)==(k==0)
            if k==0:assert abs((1-s['zero_definite_flip_exact_one_sided_95_upper'])**n-.05)<1e-14
            checks+=1
for completed in range(6):
    s=env['denominator'](['correct']*completed,6)
    assert s['missing_or_failed_n']==6-completed and not s['complete_planned_stratum']
    assert all(s[k] is None for k in ('wilson_95_definite','wilson_95_flip_or_uncertain','zero_definite_flip_exact_one_sided_95_upper','zero_flip_or_uncertain_exact_one_sided_95_upper'))
    assert s['planned_definite_fraction_lower']==0 and s['planned_flip_uncertain_missing_fraction_upper']==(6-completed)/6
    checks+=1
for eps in (.0025,.005,.010):
    assert env['classification'](eps,eps)=='uncertain'
    assert env['classification'](-eps,eps)=='uncertain'
    assert env['classification'](eps+1e-9,eps)=='correct'
    assert env['classification'](-eps-1e-9,eps)=='criterion_logic_flip'
    checks+=4
out={'scope':'pure helper tests only; synthetic classes, no physical simulation or summaries generated',
 'checks':checks,'status':'passed','zero_of_six':env['denominator'](['correct']*6,6),
 'zero_completed_of_six':env['denominator']([],6),
 'hashes':{n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in ('summarize.py','statistics.py','plot_results.py','run_stage.py')}}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
