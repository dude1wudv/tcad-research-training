"""Scientific figures from audited CSV, never synthetic response traces."""
import csv,hashlib,json,sys,textwrap
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
FIG=HERE/'figures';FIG.mkdir(exist_ok=True)
S=HERE/'data/summary'

def table(name):
    with (S/name).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))
def curve(rid):
    with (HERE/'data/tcad'/rid/'circuit.csv').open(newline='') as f:
        rs=list(csv.DictReader(f))
    return {k:np.array([float(r[k]) for r in rs]) for k in rs[0]}

proof=[]
def save(fig,name,rows,caption):
    ids=list(dict.fromkeys(r['run_id'] for r in rows))
    lengths='/'.join(f'{x:g}' for x in sorted({float(r['L_um']) for r in rows}))
    condition=f'L={lengths} um; 300 K; Cstore=10 fF; CBL=CREF=100 fF. '
    condition+=('Particle curves: 5 MeV, vertical, surface x=L+0.45 um, z=0; matched controls shown where indicated. ' if any('particle' in r for r in rows) else 'No particle. ')
    foot='DATA PLOT (Matplotlib), extracted from solver data. '+condition+caption
    foot+='\nRun IDs: '+'; '.join(ids)
    footer='\n'.join('\n'.join(textwrap.wrap(line,175)) for line in foot.splitlines())
    fig.set_figheight(max(fig.get_figheight(),6.7))
    fig.text(.02,.012,footer,fontsize=6.8,color='#333333',va='bottom')
    bottom=max(.15,.027*len(footer.splitlines()))
    fig.tight_layout(rect=(0,bottom,1,.93))
    fig.savefig(FIG/(name+'.png'),dpi=170)
    fig.savefig(FIG/(name+'.svg'))
    proof.append({'figure':name,'generated_utc':datetime.now(timezone.utc).isoformat(),
                  'caption':caption,'run_ids':ids,'source':'audited raw circuit.plt -> circuit.csv; no fitted or predicted traces',
                  'archive_sha256':{r['run_id']:r.get('archive_sha256') for r in rows},
                  'png_sha256':hashlib.sha256((FIG/(name+'.png')).read_bytes()).hexdigest()})
    plt.close(fig)

def baselines(rows):
    if not rows:return
    fig,axs=plt.subplots(1,3,figsize=(15,5.2))
    colors={.18:'#5f63b8',.25:'#287d5e',.35:'#c58625',.45:'#aa4d71'}
    for r in rows:
        c=curve(r['run_id']);m=(c['time']>=.6e-9)&(c['time']<=.95e-9)
        l=float(r['L_um']);b=int(r['bit']);label=f'L={l:g} um, bit {b}'
        axs[0].plot(c['time'][m]*1e9,c['v(sn)'][m],color=colors[l],ls='-' if b else '--',label=label)
        axs[1].plot(c['time'][m]*1e9,(c['v(sn)'][m]-float(r['target_SN_V']))*1e6,color=colors[l],ls='-' if b else '--')
        axs[2].scatter(l,float(r['initial_charge_fC']),color=colors[l],marker='o' if b else 's',s=50)
    axs[0].set(xlabel='Time (ns)',ylabel='Storage node SN (V)',ylim=(.05,.95))
    axs[0].legend(fontsize=8,loc='center right');axs[0].set_title('Controlled 0/1 states after clamp release')
    axs[1].set(xlabel='Time (ns)',ylabel='SN minus target (uV)');axs[1].set_title('Initialization error; tolerance +/-1000 uV')
    axs[1].ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    axs[2].axhline(1,color='#777777',lw=.7);axs[2].axhline(9,color='#777777',lw=.7)
    axs[2].set(xlabel='Gate length L (um)',ylabel='Cstore x SN at 0.95 ns (fC)',ylim=(0,10))
    axs[2].set_title('10 fF capacitor: 1 / 9 fC targets')
    fig.suptitle('Actual no-particle baselines | 300 K, 2D 1T1C, Cstore=10 fF, CBL=CREF=100 fF')
    for ax in axs:ax.grid(alpha=.18)
    save(fig,'01-uniform-initialization',rows,'Ideal SN clamp released at 0.6 ns; this is controlled initialization, not a calibrated write.')

def control_readout(rows):
    if not rows:return
    fig,axs=plt.subplots(1,2,figsize=(14,6.7))
    for bit,ax in enumerate(axs):
        for r in rows:
            if int(r['bit'])!=bit:continue
            c=curve(r['run_id']);t=c['time']*1e9;m=t>=2.8
            ax.plot(t[m],(c['v(bl)'][m]-c['v(ref)'][m])*1e3,label=f'L={float(r["L_um"]):g} um')
        ax.axhspan(-5,5,color='grey',alpha=.12)
        for eps in (2.5,5,10):
            for sign in (-1,1):ax.axhline(sign*eps,color='grey',ls='--',lw=.6)
        ax.axvline(3.05,color='grey',ls=':');ax.axvline(3.10,color='grey',ls=':')
        ax.set(xlabel='Time (ns)',ylabel='BL - REF (mV)',title=f'No particle, stored bit {bit}',xlim=(3,4),ylim=(-45,65))
        ax.legend();ax.grid(alpha=.15)
    fig.suptitle('Actual four-size control readout | 300 K, Cstore=10 fF, CBL=CREF=100 fF')
    save(fig,'06-control-readout',rows,'Half-supply REF=0.5 V; BL/REF release at 3 ns; WL rises 3.05-3.10 ns; decision at 4 ns; thresholds +/-2.5/5/10 mV.')

def read_timing(bases,rs):
    selected=[r for r in bases if float(r['L_um'])==.25 and int(r['bit'])==1]
    if not selected:return
    particles=sorted([r for r in rs if r['particle']=='alpha' and int(r['bit'])==1],key=lambda r:int(r['seed']))
    if particles:selected+=particles[:1]
    fig,axs=plt.subplots(2,1,figsize=(14,8),sharex=True)
    for j,r in enumerate(selected):
        c=curve(r['run_id']);t=c['time']*1e9;m=t>=2.7
        label='Matched no-particle control' if j==0 else f'alpha seed {r["seed"]}'
        axs[0].plot(t[m],c['v(sn)'][m],label=label+' SN')
        axs[1].plot(t[m],(c['v(bl)'][m]-c['v(ref)'][m])*1e3,label=label)
        if j==0:
            for key,name in [('v(bl)','BL'),('v(ref)','REF'),('v(wl)','WL')]:axs[0].plot(t[m],c[key][m],ls='--',label=name+' (control)')
    for ax in axs:
        ax.axvspan(2.8,3,color='#d7ad58',alpha=.14,label='Precharge')
        ax.axvspan(3.05,3.10,color='#7a83c5',alpha=.14,label='WL ramp')
        ax.axvline(4,color='black',ls=':',label='4 ns sample');ax.grid(alpha=.15)
    for eps in (2.5,5,10):
        for sign in (-1,1):axs[1].axhline(sign*eps,color='grey',ls='--',lw=.65)
    axs[1].axhspan(-5,5,color='grey',alpha=.12)
    axs[0].set(ylabel='Node voltage (V)');axs[0].legend(fontsize=8,ncol=3)
    axs[1].set(xlabel='Time (ns)',ylabel='BL - REF (mV)',title='Decision-scale zoom; precharge differential extends to -500 mV',xlim=(2.7,4.03),ylim=(-55,65));axs[1].legend(fontsize=8,ncol=2)
    fig.suptitle('Actual read sequence and threshold bands | L=0.25 um, bit 1, 300 K')
    save(fig,'07-read-window-and-thresholds',selected,'Fixed 4 ns decision; precharge to 0.5 V before WL; no sense latch/restore. Alpha, when present: 5 MeV, vertical, first predeclared seed; not selected by outcome.')

def transients(bases,rs):
    if not rs:return
    colors={'alpha':'#c6503a','proton':'#2b8aaa'}
    selected=[r for r in bases if float(r['L_um'])==.25]
    allrows=selected+rs
    for mode in ('hold','read'):
        fig,axs=plt.subplots(1,2,figsize=(14,5.4))
        for bit,ax in enumerate(axs):
            bb=[r for r in selected if int(r['bit'])==bit]
            for r in bb:
                c=curve(r['run_id']);t=c['time']*1e9
                m=(t>=.95)&(t<=2.8) if mode=='hold' else (t>=3)&(t<=4)
                y=c['v(sn)'] if mode=='hold' else (c['v(bl)']-c['v(ref)'])*1e3
                ax.plot(t[m],y[m],color='#222222',lw=2.2,label='Matched control')
            for particle in ('alpha','proton'):
                group=[r for r in rs if int(r['bit'])==bit and r['particle']==particle]
                for j,r in enumerate(group):
                    c=curve(r['run_id']);t=c['time']*1e9
                    m=(t>=.95)&(t<=2.8) if mode=='hold' else (t>=3)&(t<=4)
                    y=c['v(sn)'] if mode=='hold' else (c['v(bl)']-c['v(ref)'])*1e3
                    ax.plot(t[m],y[m],color=colors[particle],alpha=.8 if j==0 else .3,lw=1.7 if j==0 else 1,
                            label=f'{particle}, {len(group)} independent events' if j==0 else None)
            if mode=='read':
                ax.axhspan(-5,5,color='#777777',alpha=.13,label='Critical band at +/-5 mV')
                for y in (-10,-5,0,5,10):ax.axhline(y,color='#777777',ls='--',lw=.6)
                ax.axvline(3.05,color='#999999',ls=':',lw=.8);ax.axvline(3.10,color='#999999',ls=':',lw=.8)
                ax.set(xlabel='Time (ns)',ylabel='BL - REF (mV)',xlim=(3,4))
            else:
                ax.axvline(1,color='#999999',ls=':',lw=.8)
                ax.set(xlabel='Time (ns)',ylabel='Storage node SN (V)',xlim=(.95,2.8))
            ax.set_title(f'Stored bit {bit}');ax.grid(alpha=.18);ax.legend(fontsize=9)
        fig.suptitle(f'Actual {mode} response | L=0.25 um, 5 MeV vertical, strike=1 ns, fixed impact position')
        cap='All completed frozen events shown; 0/1 share each event seed. '
        cap+=('D sampled at 4 ns, WL ramps 0 to 1.8 V at 3.05-3.10 ns; no sense latch or restore.' if mode=='read' else 'Radiation perturbation is distinct from readout classification; no fit or predicted curves.')
        save(fig,'02-hold-transients' if mode=='hold' else '03-readout-differential',allrows,cap)

def statistics(rs):
    p=S/'statistics.json'
    if not rs or not p.exists():return
    stats=json.loads(p.read_text())['statistics'];main=[s for s in stats if s['epsilon_mV']==5]
    fig,axs=plt.subplots(1,3,figsize=(14,5.3),sharey=True)
    for ax,bit in zip(axs,(0,1,'paired_any')):
        for x,particle in enumerate(('alpha','proton')):
            rows=[s for s in main if s['bit']==bit and s['particle']==particle]
            if not rows:continue
            s=rows[0];n=s['planned_n'];k=s['definite_flip'];u=s['uncertain']
            if s['complete_planned_stratum']:
                for shift,count,key,color,marker in [(-.1,k,'wilson_95_definite','#333333','o'),(.1,k+u,'wilson_95_flip_or_uncertain','#c6503a','s')]:
                    lo,hi=s[key];v=count/n
                    ax.errorbar(x+shift,v,yerr=[[v-lo],[hi-v]],fmt=marker,color=color,capsize=5)
                ax.text(x,.98,f'n={n}\nmisread={k}, unresolved={u}',ha='center',va='top',fontsize=9)
                upper=s['zero_flip_or_uncertain_exact_one_sided_95_upper']
                if upper is not None:ax.text(x,.67,f'0/{n}: exact 95%\nupper {upper:.1%}',ha='center',fontsize=9)
            else:
                ax.text(x,.6,f'{s["completed_n"]}/{n} completed\n{s["missing_or_failed_n"]} missing\nNo probability interval',ha='center',fontsize=9)
        ax.set_xticks([0,1],['alpha','proton']);ax.set_xlim(-.6,1.6);ax.set_ylim(-.03,1.1)
        ax.set_title(f'Bit {bit}' if bit!='paired_any' else 'Either bit in an event pair');ax.grid(axis='y',alpha=.18)
    axs[0].set_ylabel('Criterion error fraction; 95% Wilson interval')
    fig.suptitle('Fixed-condition exploratory pilot | circles: definite misread; squares: misread or unresolved | +/-5 mV')
    save(fig,'04-event-statistics',rs,'Independent events are the denominator; paired bit states are not pooled. Incomplete strata receive no probability interval; no cross section or calibrated rate.')
    fig,axs=plt.subplots(1,2,figsize=(13,5.2),sharey=True)
    for bit,ax in enumerate(axs):
        for particle,color in [('alpha','#c6503a'),('proton','#2b8aaa')]:
            group=sorted([r for r in rs if int(r['bit'])==bit and r['particle']==particle],key=lambda x:int(x['seed']))
            ax.scatter(np.array([int(r['replicate']) for r in group])+(0 if particle=='alpha' else .16),[float(r['M_mV']) for r in group],
                       color=color,marker='o' if particle=='alpha' else 's',s=55,label=particle)
        ax.axhspan(-5,5,color='#777777',alpha=.13)
        for eps in (2.5,5,10):
            for sign in (-1,1):ax.axhline(sign*eps,color='#999999',lw=.7,ls='--')
        ax.set(xlabel='Predeclared independent event index',ylabel='Signed margin M = (2b-1)(BL-REF) (mV)',title=f'Stored bit {bit}')
        ax.legend();ax.grid(alpha=.18)
    fig.suptitle('Threshold sensitivity on the same raw samples | +/-2.5, +/-5 and +/-10 mV')
    save(fig,'05-threshold-sensitivity',rs,'Negative margin beyond a threshold is a criterion misread; the central band is critical. Numerical uncertainty, if present, is tabulated separately. Thresholds were declared before particle-response sampling.')

if __name__=='__main__':
    bs=table('baselines.csv');rs=table('responses.csv')
    baselines(bs);control_readout(bs);read_timing(bs,rs);transients(bs,rs);statistics(rs)
    (FIG/'figure-evidence.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'figures':[x['figure'] for x in proof],'response_count':len(rs)}))
