"""Constrained Chinese request compiler, not a general-purpose LLM parser."""
import argparse
import itertools
import json
import re
from pathlib import Path

PATTERN=re.compile(r'栅长\s*([0-9., ]+)\s*um\s*[；;]\s*粒子\s*([a-z, ]+)\s*[；;]\s*能量\s*([0-9.]+)\s*MeV\s*[；;]\s*角度\s*([0-9, ]+)\s*deg\s*')
def compile_request(text,max_cases=16):
    m=PATTERN.fullmatch(text)
    if not m:raise ValueError('Ambiguous request; expected 栅长 ... um；粒子 ...；能量 ... MeV；角度 ... deg')
    lengths=[float(x.strip()) for x in m[1].split(',')]
    particles=[x.strip() for x in m[2].split(',')]
    energy=float(m[3]);angles=[int(x.strip()) for x in m[4].split(',')]
    if any(not .15<=x<=.5 for x in lengths) or any(x not in ('alpha','proton') for x in particles) or energy<1 or energy>10 or any(x not in (0,30) for x in angles):
        raise ValueError('Request outside frozen v1 bounds')
    if any(len(set(x))!=len(x) for x in (lengths,particles,angles)):raise ValueError('Duplicate parameter values')
    if len(lengths)*len(particles)*len(angles)>max_cases:raise ValueError('Case budget exceeded')
    cases=[{'id':f'l{round(l*100):03d}-{p}-e{energy:g}-a{a}', 'gate_length_um':l,'particle':p,'energy_MeV':energy,'angle_deg':a,'seed':20261009,'events':1}
            for l,p,a in itertools.product(lengths,particles,angles)]
    if len({c['id'] for c in cases})!=len(cases):
        raise ValueError('Distinct lengths collide under v1 case labels; use a more widely separated set')
    return cases

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('request');p.add_argument('output',type=Path);a=p.parse_args()
    result={'request':a.request,'parser_scope':'Constrained Chinese template compiled by deterministic rules; AI authored workflow, no autonomous external LLM API',
            'cases':compile_request(a.request)}
    if a.output.exists():raise ValueError('Refuse overwrite')
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'Compiled {len(result["cases"])} cases')
