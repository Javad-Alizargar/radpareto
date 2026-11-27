"""Reproduce a common-function, common-gate-basis structural mapping example.

Read the attributed external RTL already bundled under external_hdl/vendor.
No network requests, runtime benchmark or physical FPGA timing claim is made.
Requires the pinned yowasp-yosys environment and an installed RadPareto package
or --engine-src. Each mapped netlist is SAT-checked against the source function.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

RECIPES={
 'simple_map':'strash; map',
 'area_map':'strash; map -a',
 'dc2_map':'strash; dc2; map',
 'balance_map':'strash; balance; map',
 'rewrite_map':'strash; rewrite; refactor; balance; rewrite -z; refactor -z; balance; map',
 'dch_map':'strash; dch; map',
 'dch_area_map':'strash; dch; map -a',
 'default':None,
}
SOURCE_SHA='df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5'
SOURCE_COMMIT='48ff7a7e2ef782cf778d47910cf85835c64b1bce'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path,value):
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2);handle.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1]/'external_hdl/vendor/priority_encoder.v')
    parser.add_argument('--engine-src',type=Path)
    parser.add_argument('--yosys',default='yowasp-yosys')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.engine_src:sys.path.insert(0,str(args.engine_src.resolve()))
    from radpareto import __version__
    from radpareto.compare import compare
    from radpareto.yosys import import_yosys
    source=args.source.resolve();assert digest(source)==SOURCE_SHA
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    # A local source copy keeps command files relocatable and avoids quoting OS paths.
    (out/'priority_encoder.v').write_bytes(source.read_bytes())
    version=subprocess.run([args.yosys,'-V'],check=True,capture_output=True,text=True).stdout.strip()
    execution=[];records=[];metrics=[]
    def execute(stem,script):
        path=out/(stem+'.ys');path.write_text(script,encoding='utf-8')
        command=[args.yosys,'-T','-l',stem+'.full.log','-s',path.name]
        run=subprocess.run(command,cwd=out,capture_output=True,text=True,timeout=180)
        (out/(stem+'.process.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
        execution.append(dict(stem=stem,command=['yowasp-yosys']+command[1:],returncode=run.returncode,script_sha256=digest(path)))
        if run.returncode:raise RuntimeError('Synthesis/SAT failed; inspect preserved '+stem+' logs')
    context=dict(baseline_id='priority_encoder_width16_msb_'+SOURCE_SHA[:12],device='abstract_generic_logic',
        toolchain='Yosys synth -noabc plus ABC; common gate basis AND OR XOR MUX NOT',tool_version=version,
        implementation='flattened generic Boolean gates; mapping recipe varies explicitly as method',
        constraints_id='same WIDTH16 MSB-priority function and generic gate library; no physical constraints',
        timing_corner='not_applicable_logic_depth_surrogate',workload_id='all 65536 Boolean input vectors; source output behavior preserved',
        source_kind='synthesis')
    read='read_verilog priority_encoder.v\nchparam -set WIDTH 16 -set LSB_HIGH_PRIORITY 0 priority_encoder\n'
    for method,recipe in RECIPES.items():
        mapping='abc -g simple'
        if recipe:
            (out/(method+'.abc')).write_text(recipe+'\n',encoding='utf-8')
            mapping+=' -script '+method+'.abc'
        script=read+'synth -top priority_encoder -flatten -noabc\n'+mapping+'\nopt_clean\ncheck -assert\n'+\
            f'tee -o {method}.stat stat\nwrite_json {method}.json\ntee -o {method}.ltp ltp -noff\n'
        execute(method,script)
        net=out/(method+'.json')
        record,summary=import_yosys(net,top='priority_encoder',record_id=method,design='priority_encoder_width16_msb',
            method=method,context=context,source_uri='benchmarks/priority_encoder_mapping/results/'+net.name)
        stat=(out/(method+'.stat')).read_text();ltp=(out/(method+'.ltp')).read_text()
        assert int(re.findall(r'\n\s*(\d+) cells\n',stat)[-1])==summary['cell_count']
        assert int(re.findall(r'Longest topological path in \S+ \(length=(\d+)\)',ltp)[-1])==summary['logic_depth']
        proof=read+'hierarchy -top priority_encoder\nproc\nflatten\nopt\nrename priority_encoder gold\n'+\
            f'read_json {method}.json\nrename priority_encoder gate\nmiter -equiv -flatten gold gate equivalence\n'+\
            f'hierarchy -top equivalence\ntee -o {method}.sat sat -verify -prove trigger 0 -set-def-inputs\n'
        execute(method+'_equivalence',proof)
        assert 'SUCCESS!' in (out/(method+'.sat')).read_text(),method
        records.append(record)
        metrics.append(dict(method=method,abc_script=recipe or 'pinned Yosys default',cells=summary['cell_count'],
            logic_depth=summary['logic_depth'],cell_types=summary['cell_types'],netlist_sha256=digest(net),
            importer_matches_stat_and_ltp=True,source_function_sat_equivalence='passed'))
    document=dict(schema_version='1.0',records=records)
    dump(out/'records.json',document)
    dump(out/'metrics.json',metrics)
    decisions={name:compare(records,limits=limits) for name,limits in {
        'area_budget':dict(cell_count=60,logic_depth=8),
        'depth_budget':dict(cell_count=90,logic_depth=7),
        'joint_infeasible':dict(cell_count=60,logic_depth=7),
        'unconstrained':{},
    }.items()}
    assert all(v['status']=='accepted' for v in decisions.values())
    assert decisions['area_budget']['definitely_feasible_nominal_front']==['area_map']
    assert decisions['depth_budget']['definitely_feasible_nominal_front']==['simple_map','balance_map']
    assert decisions['joint_infeasible']['definitely_feasible_nominal_front']==[]
    dump(out/'decisions.json',decisions)
    dump(out/'run_manifest.json',dict(tool_version=version,radpareto_version=__version__,python=platform.python_version(),
        source_sha256=SOURCE_SHA,source_commit=SOURCE_COMMIT,source_repository='https://github.com/alexforencich/verilog-axis',
        source_license='MIT; original notice in priority_encoder.v and external_hdl/vendor/COPYING',
        conditions=context,recipes=RECIPES,runs=execution,generated_utc=datetime.now(timezone.utc).isoformat(),
        selection='Eight recipes retained after exploratory WIDTH16/32 sweep; illustrative demonstration, not a preregistered optimization benchmark',
        limits='Generic cell count and graph depth only; no target FPGA mapping, place-and-route, physical timing, power or radiation result'))
    print(json.dumps(dict(records=len(records),sat_proofs=len(records),metrics=metrics,
        front=decisions['unconstrained']['nominal_front'])))


if __name__=='__main__':main()
