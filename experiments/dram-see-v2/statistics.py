"""Small-sample intervals: fixed strata, independent particle event denominator."""
import math
def wilson(k,n,z=1.959963984540054):
    if not isinstance(k,int) or not isinstance(n,int) or not 0<=k<=n or n<1:raise ValueError('Invalid binomial count')
    p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [0. if k==0 else max(0,center-half),1. if k==n else min(1,center+half)]
def zero_upper(n,alpha=.05):
    if n<1:raise ValueError('No samples')
    return 1-alpha**(1/n)
def summarize_classes(classes):
    allowed={'correct','criterion_logic_flip','uncertain'}
    if not classes or not set(classes)<=allowed:raise ValueError('Bad classifications')
    n=len(classes);k=classes.count('criterion_logic_flip');u=classes.count('uncertain')
    return {'n_independent_events':n,'correct':classes.count('correct'),'definite_flip':k,'uncertain':u,
            'definite_flip_fraction':k/n,'wilson_95_definite':wilson(k,n),
            'wilson_95_flip_or_uncertain':wilson(k+u,n),
            'zero_definite_flip_exact_one_sided_95_upper':zero_upper(n) if k==0 else None,
            'zero_flip_or_uncertain_exact_one_sided_95_upper':zero_upper(n) if k+u==0 else None}
