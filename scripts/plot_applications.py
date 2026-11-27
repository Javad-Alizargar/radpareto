"""Generate reusable workflow/application plots from retained numerical outputs.

Outputs are generated locally on demand; no source article or manuscript text is
embedded. This script reads results and records all input/output hashes. It does
not invent measurements or execute a new hardware experiment.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
from matplotlib.colors import ListedColormap
import numpy as np

INK='#253444'; BLUE='#0072B2'; TEAL='#00866A'; ORANGE='#D77B13'; RED='#B64646'; GRAY='#718096'
SOURCES={}
LABELS={'DF-TMR-DFF-1.28':'DF1.28','DF-TMR-DFF-2.56':'DF2.56',
        'DF-TMR-DFF-5.12':'DF5.12','DCLR-TMR-DFF':'DCLR'}


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    SOURCES[path.relative_to(ROOT).as_posix()]=digest(path)
    if path.suffix=='.csv':
        with path.open(encoding='utf-8',newline='') as stream: return list(csv.DictReader(stream))
    return json.loads(path.read_text(encoding='utf-8'))


def save(fig,name):
    for ext in ['pdf','svg','png']:
        meta={'Creator':'RadPareto reproducible analysis','CreationDate':None,'ModDate':None} if ext=='pdf' else {'Creator':'RadPareto reproducible analysis','Date':None} if ext=='svg' else None
        fig.savefig(OUT/(name+'.'+ext),bbox_inches='tight',pad_inches=.08,dpi=320,metadata=meta)
    plt.close(fig)


def title(ax,letter,text): ax.set_title(letter+'  '+text,loc='left',fontweight='bold',pad=12)


def workflow():
    fig,ax=plt.subplots(figsize=(7.4,3.4)); ax.set(xlim=(0,10),ylim=(0,4.7)); ax.axis('off')
    def box(x,y,w,h,heading,body,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08,rounding_size=0.09',
            edgecolor=color,facecolor='#F7FAFC',linewidth=1.1))
        ax.text(x+.12,y+h-.2,heading,fontsize=8.5,fontweight='bold',va='top',color=color)
        ax.text(x+.12,y+h-.57,body,fontsize=7.7,va='top',linespacing=1.45)
    def arrow(a,b,color=GRAY):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=10,lw=1.1,color=color))
    box(.15,2.55,2.25,1.5,'Source records','Costs and ranges\nContext and units\nURI, digest, locator',BLUE)
    box(.15,.45,2.25,1.4,'Decision inputs','Candidates + budgets\nProtection policy\nWidening scales',BLUE)
    box(3.05,1.48,2.1,1.62,'Eligibility','Schema and bounds\nContext / metrics\nRequested evidence',INK)
    box(5.83,2.6,3.88,1.43,'Accepted premises','Nominal / certain costs\nInterval budget decisions\nConditional widening certificates',TEAL)
    box(5.83,.48,3.88,1.36,'Informative refusal','Identify incompatible premises\nReview source or correct input\nKeep distinct contexts separate',RED)
    arrow((2.48,3.13),(3.0,2.65)); arrow((2.48,1.15),(3.0,1.98))
    arrow((5.23,2.6),(5.75,3.05),TEAL); arrow((5.23,1.97),(5.75,1.18),RED)
    ax.text(5,.12,'CLI adds version, options and input hash; API callers retain execution metadata.',
        ha='center',va='center',fontsize=7.5)
    ax.text(5,4.48,'Source-linked inputs, explicit eligibility and conditional decisions',ha='center',fontsize=9.3,fontweight='bold')
    save(fig,'figure1_workflow')


def architectural():
    rows=read(ROOT/'benchmarks/published_case/decision_atlas/results/design_metrics.csv')
    rows=[r for r in rows if r['structure'] in LABELS]
    assert len(rows)==4
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.7),gridspec_kw={'width_ratios':[1.1,1]})
    for r in rows:
        name=r['structure']; x=float(r['cells_per_bit']); y=float(r['fmean_mhz'])
        lo,hi=float(r['fmin_mhz']),float(r['fmax_mhz'])
        color=BLUE if name in ['DF-TMR-DFF-1.28','DCLR-TMR-DFF'] else GRAY
        axs[0].errorbar(x,y,yerr=[[y-lo],[hi-y]],fmt='o',capsize=4,ms=6,color=color)
        offset=(-35,9) if name=='DCLR-TMR-DFF' else (6,7)
        axs[0].annotate(LABELS[name],(x,y),xytext=offset,textcoords='offset points',fontsize=8.5,color=color)
    axs[0].set(xlim=(26,39.5),ylim=(30,45.7),xlabel='Reported VersaTiles per logic bit',ylabel='Reported maximum frequency (MHz)')
    axs[0].grid(color='#E9EDF0',lw=.6); title(axs[0],'A','Restricted architectural portfolio')
    axs[0].text(.03,.96,'Blue: cost-frontier alternatives\nBars: three-run extrema',transform=axs[0].transAxes,fontsize=7.5,va='top')
    names=['set_subset_area_priority','set_subset_ambiguous','set_subset_frequency_priority']
    values={'definitely_feasible':0,'uncertain':1,'definitely_infeasible':2}
    matrix=[]
    for name in names:
        result=read(ROOT/'benchmarks/workflow_comparison/results/outputs'/(name+'_radpareto.json'))['result']
        matrix.append([values[result['feasibility'][r['structure']]['status']] for r in rows])
    matrix=np.array(matrix).T
    axs[1].imshow(matrix,cmap=ListedColormap(['#CDE9DD','#F9DFB8','#E8C6C3']),vmin=0,vmax=2,aspect='auto')
    for i in range(4):
        for j in range(3): axs[1].text(j,i,['F','U','I'][matrix[i,j]],ha='center',va='center',fontsize=11,fontweight='bold')
    axs[1].set(yticks=range(4),yticklabels=[LABELS[r['structure']] for r in rows],xticks=range(3),
        xticklabels=['35 cells\n40 MHz','40 cells\n40.7 MHz','40 cells\n42 MHz'])
    axs[1].tick_params(axis='both',length=0,labelsize=8)
    axs[1].set_xticks(np.arange(-.5,3,1),minor=True);axs[1].set_yticks(np.arange(-.5,4,1),minor=True)
    axs[1].grid(which='minor',color='white',lw=3);axs[1].tick_params(which='minor',length=0)
    for spine in axs[1].spines.values():spine.set_visible(False)
    title(axs[1],'B','Declared budgets change the decision')
    axs[1].text(.5,-.2,'F feasible   U uncertain   I infeasible\nProtection equivalence remains unverified',ha='center',va='top',transform=axs[1].transAxes,fontsize=8)
    fig.subplots_adjust(left=.085,right=.99,bottom=.25,top=.85,wspace=.42)
    save(fig,'figure2_architectural_decision')


def synthesis():
    rows=read(ROOT/'benchmarks/priority_encoder_mapping/results/metrics.json')
    decisions=read(ROOT/'benchmarks/priority_encoder_mapping/results/decisions.json')
    assert len(rows)==8 and all(r['source_function_sat_equivalence']=='passed' for r in rows)
    assert decisions['area_budget']['definitely_feasible_nominal_front']==['area_map']
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.85),gridspec_kw={'width_ratios':[1.05,1]})
    grouped={}
    for r in rows:grouped.setdefault((r['cells'],r['logic_depth']),[]).append(r['method'])
    shorts={'simple_map':'simple','area_map':'area','dc2_map':'dc2','balance_map':'balance',
            'rewrite_map':'rewrite','dch_map':'dch','dch_area_map':'dch-area','default':'default'}
    offsets={(84,7):(-15,-20),(58,8):(5,8),(111,10):(-10,-22),(113,10):(0,28),(101,10):(-8,13),(79,13):(5,0),(80,12):(5,0)}
    for (x,y),names in grouped.items():
        frontier=any(n in ['simple_map','balance_map','area_map'] for n in names)
        axs[0].scatter(x,y,s=47,color=BLUE if frontier else GRAY,zorder=3)
        align='right' if (x,y) in [(111,10),(101,10)] else 'center' if (x,y)==(113,10) else 'left'
        axs[0].annotate(' / '.join(shorts[n] for n in names),(x,y),xytext=offsets[(x,y)],textcoords='offset points',fontsize=7.8,ha=align,
            arrowprops=dict(arrowstyle='-',lw=.5,color=GRAY) if y==10 else None)
    axs[0].axvline(60,color=TEAL,ls='--',lw=1);axs[0].axhline(8,color=TEAL,ls='--',lw=1)
    axs[0].axvline(90,color=ORANGE,ls=':',lw=1.1);axs[0].axhline(7,color=ORANGE,ls=':',lw=1.1)
    axs[0].set(xlim=(49,122),ylim=(5.9,14),xticks=[60,80,100,120],yticks=range(7,14),xlabel='Generic cell count',ylabel='Logic depth (levels)')
    axs[0].grid(color='#E9EDF0',lw=.6);title(axs[0],'A','Same function, competing mappings')
    axs[0].text(.5,-.26,'Dashed: 60 cells / 8 levels\nDotted: 90 cells / 7 levels',transform=axs[0].transAxes,ha='center',va='top',fontsize=7.6)
    order=sorted(rows,key=lambda r:(r['cells'],r['logic_depth'],r['method']))
    ys=np.arange(8);left=np.zeros(8)
    colors=['#0072B2','#00866A','#E0A83D','#8C8FAD']
    for key,color in zip(['$_AND_','$_OR_','$_MUX_','$_NOT_'],colors):
        vals=np.array([r['cell_types'].get(key,0) for r in order]);axs[1].barh(ys,vals,left=left,color=color,height=.62,label=key[2:-1]);left+=vals
    assert all(left[i]==r['cells'] for i,r in enumerate(order))
    for i,r in enumerate(order):axs[1].text(r['cells']+2,i,str(r['cells']),va='center',fontsize=7.5)
    axs[1].set(yticks=ys,yticklabels=[shorts[r['method']] for r in order],xlim=(0,128),xlabel='Cells by primitive type')
    axs[1].invert_yaxis();axs[1].legend(loc='lower center',bbox_to_anchor=(.5,-.29),ncol=4,frameon=False,fontsize=7,columnspacing=.8,handlelength=1)
    title(axs[1],'B','All eight recipes retained')
    fig.subplots_adjust(left=.075,right=.99,bottom=.24,top=.85,wspace=.42)
    save(fig,'figure3_synthesis_tradeoff')


def scales():
    rows=read(ROOT/'benchmarks/workflow_comparison/results/scale_sensitivity.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.15),sharey=True)
    selections=[('DF-TMR-DFF-1.28','period_ns','DF1.28 timing'),('DCLR-TMR-DFF','cells','DCLR resources')]
    for ax,scenario,letter,label in zip(axs,['A_count_and_timing_stress','B_timing_only_stress'],['A','B'],
            ['Count + timing stress','Timing-only stress']):
        for i,(record,objective,name) in enumerate(selections):
            r=next(v for v in rows if v['scenario']==scenario and v['record']==record and v['objective']==objective)
            initial=r['initial_status'];color=TEAL if initial=='definitely_feasible' else RED
            end=float(r['transition_t']) if r['transition_t'] else 8
            ax.barh(i,min(end,8),height=.38,color=color,alpha=.85)
            if r['transition_t']:
                ax.barh(i,8-end,left=end,height=.38,color='#EFC58A')
                included=r['boundary_included']=='True'
                ax.plot(end,i,'o',ms=5,mec=INK,mfc=INK if included else 'white',zorder=4)
                ax.text(end+.1,i-.28,f"t* = {end:.6f}",fontsize=8,va='bottom')
            else:
                ax.text(4,i,'No finite transition: count scale = 0',ha='center',va='center',fontsize=7.5,color='white')
        ax.set(xlim=(0,8),ylim=(1.65,-.65),xticks=[0,2,4,6,8],yticks=[0,1],yticklabels=[x[2] for x in selections],xlabel='Dimensionless widening t')
        ax.grid(axis='x',color='#E9EDF0',lw=.6);ax.set_axisbelow(True);title(ax,letter,label)
        scale='1 cell/bit and 0.1 ns per t' if letter=='A' else '0 cells/bit and 0.5 ns per t'
        ax.text(.5,1.03,scale,ha='center',va='bottom',transform=ax.transAxes,fontsize=8)
    axs[0].tick_params(axis='y',labelsize=8.3)
    fig.legend(handles=[Patch(facecolor=TEAL,label='Feasible supplied interval'),Patch(facecolor='#EFC58A',label='Uncertain'),Patch(facecolor=RED,label='Infeasible supplied interval')],
        loc='lower center',ncol=3,frameon=False,fontsize=8)
    fig.subplots_adjust(left=.16,right=.99,top=.72,bottom=.27,wspace=.18)
    save(fig,'figure4_scale_scenarios')


def main():
    global ROOT,OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();ROOT=args.repo_root.resolve();OUT=args.out.resolve()
    OUT.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'axes.titlesize':9.5,
        'xtick.labelsize':8,'ytick.labelsize':8,'axes.spines.top':False,'axes.spines.right':False,
        'axes.edgecolor':'#99A3AC','axes.linewidth':.6,'text.color':INK,'axes.labelcolor':INK,
        'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'radpareto-applications-v1'})
    workflow();architectural();synthesis();scales()
    outputs={p.name:digest(p) for p in sorted(OUT.iterdir())}
    manifest=dict(script_sha256=digest(Path(__file__)),inputs_sha256=SOURCES,outputs_sha256=outputs,
        dependencies=dict(python=platform.python_version(),matplotlib=matplotlib.__version__,numpy=np.__version__),
        scope='One workflow diagram and three plots of retained engineering/scenario outputs; no new physical observations or user-benefit measurements')
    (OUT/'application_plot_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(plot_sets=4,input_files=len(SOURCES),outputs=len(outputs))))


if __name__=='__main__':main()
