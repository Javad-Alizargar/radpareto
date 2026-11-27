"""Regenerate data-analysis plots and table CSVs from permitted public outputs.

Generated artwork is a local analysis product, excluded from the source release.
Input hashes, dependency versions and output hashes accompany each run.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, platform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch, Rectangle
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DEST=None
DATA=None
MUTATION=None
SOURCES={}
INK,BLUE,TEAL,ORANGE,RED,GRAY='#253444','#0072B2','#00866A','#D77B13','#B64646','#718096'
COLORS=[GRAY,BLUE,TEAL,'#7D8B38',ORANGE,'#986AA0']
LABELS=['BL','TMR','DF1.28','DF2.56','DF5.12','DCLR']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.labelsize':9,'axes.titlesize':10,
 'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,'axes.spines.top':False,
 'axes.spines.right':False,'axes.edgecolor':'#99A3AC','text.color':INK,'axes.labelcolor':INK,
 'xtick.color':INK,'ytick.color':INK,'axes.linewidth':.6,'pdf.fonttype':42,'ps.fonttype':42,
 'svg.fonttype':'none','svg.hashsalt':'radpareto-data-plots-v1','figure.facecolor':'white','savefig.facecolor':'white'})

def read(name):
    p=(ROOT/Path(name)).resolve()
    key=p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()
    SOURCES[key]=hashlib.sha256(p.read_bytes()).hexdigest()
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def save(fig,name):
    DEST.mkdir(parents=True,exist_ok=True)
    for ext in ('pdf','svg','png'):
        meta={'Creator':'RadPareto data-derived plotting','CreationDate':None,'ModDate':None} if ext=='pdf' else {'Creator':'RadPareto data-derived plotting','Date':None} if ext=='svg' else None
        fig.savefig(DEST/f'{name}.{ext}',bbox_inches='tight',pad_inches=.07,dpi=320,metadata=meta)
    plt.close(fig)

def title(ax,letter,text): ax.set_title(f'{letter}  {text}',loc='left',fontweight='bold',pad=11)

def published(rows):
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.65),gridspec_kw={'width_ratios':[1.15,1]})
    for i,r in enumerate(rows):
        x,y,lo,hi=[float(r[k]) for k in ('cells_per_bit','fmean_mhz','fmin_mhz','fmax_mhz')]
        axs[0].errorbar(x,y,yerr=[[y-lo],[hi-y]],fmt='o',ms=5.5,capsize=3,color=COLORS[i],zorder=3)
        offset=[(7,1),(7,-1),(5,-13),(5,-13),(5,-12),(-39,6)][i]
        axs[0].annotate(LABELS[i],(x,y),xytext=offset,textcoords='offset points',color=COLORS[i],fontsize=8)
    axs[0].set(xlim=(8,40),ylim=(29,63),xlabel='Reported VersaTiles per logic bit',ylabel='Reported maximum frequency (MHz)')
    axs[0].grid(axis='y',color='#E9EDF0',lw=.6); title(axs[0],'A','Six separate implementations')
    left=np.array([float(r['nominal_pass_but_range_not_supported_width_mhz']) for r in rows])
    right=np.array([float(r['nominal_fail_but_range_possible_width_mhz']) for r in rows]); y=np.arange(6)
    axs[1].barh(y,left,color=ORANGE,height=.5,label='Minimum to mean')
    axs[1].barh(y,right,left=left,color='#94BFDA',height=.5,label='Mean to maximum')
    for j,v in enumerate(left+right): axs[1].text(v+.06,j,f'{v:.3f}',va='center',fontsize=8)
    axs[1].set(yticks=y,yticklabels=LABELS,xlim=(0,2.9),xlabel='Span of three reported runs (MHz)')
    axs[1].invert_yaxis(); axs[1].legend(frameon=False,loc='lower right',fontsize=7.5)
    title(axs[1],'B','Observed span, not a confidence interval')
    fig.tight_layout(w_pad=2.2); save(fig,'figure1_published_evidence')

def atlas(rows):
    data=read(f'{DATA}/exact_atlas.csv')
    x=sorted({0.,40.,*[float(r['cells_per_bit']) for r in rows]})
    y=sorted({0.,62.,*[float(r[k]) for r in rows for k in ('fmin_mhz','fmean_mhz','fmax_mhz')]})
    open_rows=[r for r in data if r['resource_region'].startswith('(') and r['frequency_region_mhz'].startswith('(')]
    def bounds(s): return tuple(float(t) for t in s[1:-1].split(','))
    z=np.zeros((len(y)-1,len(x)-1))
    for iy,(a,b) in enumerate(zip(y,y[1:])):
        for ix,(c,d) in enumerate(zip(x,x[1:])):
            xx,yy=(c+d)/2,(a+b)/2
            found=[r for r in open_rows if bounds(r['resource_region'])[0]<xx<bounds(r['resource_region'])[1] and bounds(r['frequency_region_mhz'])[0]<yy<bounds(r['frequency_region_mhz'])[1]]
            assert len(found)==1; z[iy,ix]=int(found[0]['feasible_n'])
    fig,axs=plt.subplots(1,2,figsize=(7.4,4),sharey=True,gridspec_kw={'width_ratios':[1.12,1]})
    cm=ListedColormap(['#F1F3F4','#D7E8F2','#AACFE3','#78B4D5','#4694C0','#2176A7','#085581'])
    im=axs[0].pcolormesh(x,y,z,cmap=cm,norm=BoundaryNorm(np.arange(-.5,7.5),7),shading='flat')
    cb=fig.colorbar(im,ax=axs[0],ticks=range(7),fraction=.046,pad=.03); cb.set_label('Number of designs')
    for i,r in enumerate(rows):
        c,lo,hi=[float(r[k]) for k in ('cells_per_bit','fmin_mhz','fmax_mhz')]
        axs[1].add_patch(Rectangle((c,lo),40-c,hi-lo,color=COLORS[i],alpha=.8,lw=0))
        axs[1].text(40.55,(lo+hi)/2,LABELS[i],va='center',fontsize=7.6,color=COLORS[i],clip_on=False)
    for ax in axs:
        ax.set(xlim=(8,40),ylim=(30,61.5),xticks=[11,20,30,40],xlabel='Resource cap (VersaTiles per bit)')
        ax.axhline(32,color=INK,ls='--',lw=.75)
    axs[0].set_ylabel('Required frequency (MHz)')
    title(axs[0],'A','Passes cap and reported minimum')
    title(axs[1],'B','Between reported timing extrema')
    axs[1].text(8.5,33,'32 MHz',fontsize=7.5)
    axs[1].text(9,48,'White: no uncertain design\nat that resource/clock requirement',fontsize=7.2,color=GRAY)
    fig.text(.48,.015,'At a passing resource cap: F <= minimum passes; minimum < F <= maximum is uncertain.',ha='center',fontsize=7.4,color=GRAY)
    fig.subplots_adjust(left=.09,right=.9,bottom=.20,top=.87,wspace=.48)
    save(fig,'figure2_exact_atlas')

def margins(rows):
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.8),gridspec_kw={'width_ratios':[1.1,1]})
    for i,r in enumerate(rows):
        lo,mean,hi=[float(r[k])-32 for k in ('fmin_mhz','fmean_mhz','fmax_mhz')]
        axs[0].plot([lo,hi],[i,i],color=COLORS[i],lw=3,solid_capstyle='round')
        axs[0].scatter([mean],[i],color=INK,s=22,zorder=3)
        axs[0].text(hi+.6,i,f'{lo:+.3f}',va='center',fontsize=7.6,color=COLORS[i])
    axs[0].axvline(0,color=RED,ls='--',lw=.9)
    axs[0].set(yticks=range(6),yticklabels=LABELS,xlim=(-2,34),xlabel='Frequency margin relative to 32 MHz')
    axs[0].invert_yaxis(); title(axs[0],'A','One range crosses the requirement')
    fig.text(.08,.025,'Dots: means. Labels: minimum minus 32 MHz.',fontsize=7.3,color=GRAY)
    ax=axs[1]
    for yy,label,color in [(1.05,'At a printed minimum',TEAL),(.05,'At a printed maximum',ORANGE)]:
        ax.plot([-.8,.8],[yy,yy],color='#CCD4DA',lw=7,solid_capstyle='butt')
        ax.plot([-.5,.5],[yy,yy],color=color,lw=7,alpha=.45,solid_capstyle='butt')
        ax.scatter([0],[yy],color=INK,s=23,zorder=4)
        ax.text(-.8,yy+.27,label,fontsize=8.2,fontweight='bold')
    ax.plot([-.5,0],[1.05,1.05],color=RED,lw=3); ax.plot([0,.5],[.05,.05],color=RED,lw=3)
    ax.scatter([-.5,0],[1.05,.05],s=30,facecolors='white',edgecolors=RED,zorder=5)
    ax.scatter([0,.5],[1.05,.05],s=22,color=RED,zorder=5)
    ax.text(-.23,.78,'F to U',ha='center',fontsize=8,color=RED); ax.text(.25,-.22,'I to U',ha='center',fontsize=8,color=RED)
    ax.axvline(0,color=GRAY,ls=':',lw=.8)
    ax.set(xlim=(-.9,.9),ylim=(-.48,1.65),yticks=[],xticks=[-.5,0,.5],xlabel='Requirement minus printed endpoint (kHz)')
    ax.spines['left'].set_visible(False); title(ax,'B','Assumed rounding to 0.001 MHz')
    fig.text(.74,.012,'Expanded span: +0.001 MHz; 0.0413-0.2519%\nof the observed spans. Means held fixed.',ha='center',fontsize=7.3,color=GRAY)
    fig.subplots_adjust(left=.09,right=.98,bottom=.30,top=.85,wspace=.42); save(fig,'figure3_margins_precision')

def conversion():
    rows=read(f'{DATA}/conversion_boundary_audit.csv'); errors=[r for r in rows if r['naive_class']!=r['expected_class']]
    assert len(errors)==2
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.15),sharey=True)
    short={'definitely_feasible':'Feasible','uncertain':'Uncertain','definitely_infeasible':'Infeasible'}
    for ax,r,letter in zip(axs,errors,['A','B']):
        fixed=float.fromhex(r['consistent_period_hex']); naive=float.fromhex(r['naive_period_hex'])
        error=(naive-fixed)/math.ulp(fixed); assert error==-1
        ax.axvline(0,color=GRAY,ls='--',lw=.8); ax.plot([error,0],[.5,.5],color='#D3D9DF',lw=2)
        ax.scatter([error],[.5],s=70,marker='x',color=RED,lw=2,zorder=3); ax.scatter([0],[.5],s=48,color=TEAL,zorder=3)
        ax.text(error,.73,'Former mixed path\n'+short[r['naive_class']],ha='center',fontsize=8,color=RED)
        ax.text(0,.21,'Shared decimal path\n'+short[r['consistent_class']],ha='center',fontsize=8,color=TEAL)
        ax.text(.5,.94,f'One binary64 step = {math.ulp(fixed):.2e} ns',transform=ax.transAxes,ha='center',fontsize=7.5,color=GRAY)
        ax.set(xlim=(-1.65,.65),ylim=(-.05,1.1),yticks=[],xticks=[-1,0],xlabel='Limit minus source endpoint (binary64 steps)')
        ax.spines['left'].set_visible(False); title(ax,letter,f"DF1.28 at {r['frequency_mhz']} MHz")
    fig.text(.5,.035,'Equal printed values share one conversion. Distinct very close decimal inputs can still co-round.',ha='center',fontsize=7.5,color=GRAY)
    fig.subplots_adjust(left=.04,right=.98,bottom=.23,top=.82,wspace=.35); save(fig,'figure4_conversion_boundaries')

def contexts():
    rows=read(f'{DATA}/context_comparison.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.4,3.9),gridspec_kw={'width_ratios':[1.25,1]})
    for i,r in enumerate(rows):
        stand,merged=float(r['standalone_mean_mhz']),float(r['merged_worst_mhz'])
        axs[0].plot([stand,merged],[i,i],color=COLORS[i],lw=1,alpha=.7)
        axs[0].scatter([stand],[i],s=33,color=COLORS[i],marker='o',zorder=3)
        axs[0].scatter([merged],[i],s=35,facecolors='white',edgecolors=COLORS[i],marker='s',zorder=3)
        a,b=int(r['standalone_rank']),int(r['merged_rank'])
        axs[1].plot([0,1],[a,b],color=COLORS[i],lw=2.3 if a!=b else 1.2,marker='o',ms=4)
        axs[1].text(-.1,a,LABELS[i],ha='right',va='center',fontsize=8,color=COLORS[i])
        axs[1].text(1.1,b,LABELS[i],ha='left',va='center',fontsize=8,color=COLORS[i])
    axs[0].set(yticks=range(6),yticklabels=LABELS,xlim=(29,62),xlabel='Reported frequency (MHz)'); axs[0].invert_yaxis()
    axs[0].plot([],[],marker='o',ls='',color=INK,label='Standalone: three-run mean')
    axs[0].plot([],[],marker='s',ls='',mfc='white',color=INK,label='Merged: worst-case domain')
    axs[0].legend(frameon=False,loc='lower right',fontsize=7.1); title(axs[0],'A','Different contexts and statistics')
    axs[1].set(xlim=(-.6,1.6),ylim=(6.6,.4),xticks=[0,1],xticklabels=['Standalone','Merged'],yticks=[])
    axs[1].spines['left'].set_visible(False); axs[1].spines['bottom'].set_visible(False); title(axs[1],'B','Two of 15 pair orders reverse')
    fig.text(.5,.025,'Lines track design identity, not paired trials or a causal implementation effect.',ha='center',fontsize=7.5,color=GRAY)
    fig.subplots_adjust(left=.1,right=.99,bottom=.19,top=.85,wspace=.28); save(fig,'figure5_context_comparison')

def mutation():
    rows=read(MUTATION)
    ids=['CONTROL']+[f'M{i:02}' for i in range(1,13)]
    families=['metamorphic','quarter_grid','certificate_grid','targeted_stability']
    labels=['Control','M01  Ties dominate','M02  All coordinates strict','M03  Context guard off','M04  Nominal for lower bound','M05  Feasible equality lost','M06  Infeasible equality added','M07  Factor two lost','M08  Endpoint strictness lost','M09  Zero-scale division','M10  Integer through float','M11  Wrong infeasible endpoint','M12  Record-cap off-by-one']
    lookup={(r['variant'],r['family']):r for r in rows}
    z=np.array([[0 if lookup[(v,n)]['not_assessed_reason'] else 2 if lookup[(v,n)]['detected']=='True' else 1 for n in families] for v in ids])
    fig,ax=plt.subplots(figsize=(7.4,4.5)); colors=['#F2F3F4','#D6E8F1','#DFAC63']
    ax.imshow(z,cmap=ListedColormap(colors),vmin=0,vmax=2,aspect='auto')
    for i,v in enumerate(ids):
        for j,f in enumerate(families):
            r=lookup[(v,f)]; label='Not assessed' if z[i,j]==0 else 'Detected' if z[i,j]==2 else 'No detection'
            if int(r['runtime_error_cases']): label+='\n'+r['runtime_error_cases']+' errors'
            ax.text(j,i,label,ha='center',va='center',fontsize=6.7)
    ax.set(yticks=range(len(ids)),yticklabels=labels,xticks=range(4),xticklabels=['Transformations','Quarter grid','Certificate probes','Targeted stability'])
    ax.xaxis.tick_top(); ax.tick_params(axis='both',length=0)
    ax.set_xticks(np.arange(-.5,4,1),minor=True); ax.set_yticks(np.arange(-.5,len(ids),1),minor=True)
    ax.grid(which='minor',color='white',linewidth=2); ax.tick_params(which='minor',length=0)
    for s in ax.spines.values(): s.set_visible(False)
    ax.legend(handles=[Patch(facecolor=colors[0],label='Not assessed by this family'),Patch(facecolor=colors[1],label='Not detected'),Patch(facecolor=colors[2],label='Detected, including runtime failures')],loc='upper center',bbox_to_anchor=(.42,-.06),ncol=1,frameon=False,fontsize=7.2)
    fig.subplots_adjust(left=.30,right=.99,top=.9,bottom=.22); save(fig,'figure6_mutation_detection')

def export_table(name, rows, fields):
    with (DEST/name).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)


def main():
    global DEST, DATA, MUTATION
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--atlas-dir',type=Path,
        default=ROOT/'benchmarks/published_case/decision_atlas/results')
    parser.add_argument('--mutation-csv',type=Path,
        default=ROOT/'benchmarks/mutation/retained/detection_matrix.csv')
    parser.add_argument('--out',required=True,type=Path,help='Fresh local output directory')
    args=parser.parse_args()
    DEST=args.out.resolve(); DATA=args.atlas_dir.resolve(); MUTATION=args.mutation_csv.resolve()
    if DEST.exists(): parser.error('Choose a fresh output directory')
    rows=read(DATA/'design_metrics.csv')
    published(rows); atlas(rows); margins(rows); conversion(); contexts(); mutation()
    export_table('table_source_summary.csv',rows,
        ['structure','cells_per_bit','fmean_mhz','fmin_mhz','fmax_mhz',
         'nominal_pass_but_range_not_supported_width_mhz',
         'nominal_fail_but_range_possible_width_mhz'])
    for filename in ['context_comparison.csv','conversion_boundary_audit.csv']:
        table=read(DATA/filename)
        export_table('table_'+filename,table,list(table[0]))
    table=read(MUTATION)
    export_table('table_historical_mutation.csv',table,list(table[0]))
    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.iterdir())}
    manifest=dict(inputs_sha256=SOURCES,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        dependencies=dict(python=platform.python_version(),matplotlib=matplotlib.__version__,numpy=np.__version__),
        outputs_sha256=outputs,
        scope='Six data-derived plot sets and four table CSVs. Historical mutation outcomes retain their frozen study meaning; plots do not add observations or establish physical protection.')
    (DEST/'plot_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(plot_sets=6,table_csvs=4,input_files=len(SOURCES),output_files=len(outputs))))


if __name__=='__main__':
    main()
