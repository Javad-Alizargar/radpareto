"""Run identical decision specifications through RadPareto and a composed baseline.

The baseline imports no RadPareto code. This harness is a developer-run workflow
demonstration, not an independent human usability or speed study. Every input,
option, output, dependency version and mismatch is retained in a fresh directory.
"""
import argparse
from copy import deepcopy
import csv
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

from conventional import compare_document


def dump(path,value):
    with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2);handle.write('\n')


def csv_out(path,rows):
    with path.open('x',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def project(result):
    if result['status']=='refused':return dict(status='refused',reason_codes=sorted({r['code'] for r in result['reasons']}))
    return {k:result[k] for k in ('status','nominal_front','not_certainly_dominated','feasibility','definitely_feasible_nominal_front')}


def rational_number(value):
    return None if value is None else float(Fraction(int(value['numerator']),int(value['denominator'])))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-src',type=Path)
    parser.add_argument('--published-records',type=Path,default=Path(__file__).resolve().parents[1]/'published_case/results/records.json')
    parser.add_argument('--synthesis-records',type=Path,default=Path(__file__).resolve().parents[1]/'priority_encoder_mapping/results/records.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.engine_src:sys.path.insert(0,str(args.engine_src.resolve()))
    from radpareto import __version__
    from radpareto.compare import compare
    from radpareto.stability import stability
    from radpareto.units import period_ns_from_mhz
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'inputs').mkdir();(out/'outputs').mkdir()
    published=json.loads(args.published_records.read_text(encoding='utf-8'))
    full=published['records'];subset=[r for r in full if r['id'] not in {'BL-DFF','TMR-DFF'}]
    assert len(full)==6 and len(subset)==4
    synthesis=json.loads(args.synthesis_records.read_text(encoding='utf-8'))['records']
    specifications=[]
    def add(name,records,limits=None,protection=False,kind='engineering_application',purpose=''):
        specifications.append(dict(name=name,document=dict(schema_version='1.0',records=deepcopy(records)),
            limits={} if limits is None else limits,require_verified_protection=protection,kind=kind,purpose=purpose))
    add('six_designs_cost_only',full,purpose='Retain full-set BL cost advantage; do not infer admissibility for a protection goal')
    add('six_designs_32MHz',full,dict(cells=40,period_ns=period_ns_from_mhz('32')),purpose='Observed-range uncertainty of DF5.12')
    add('set_subset_unconstrained',subset,purpose='SET-suppression architectural investigation; membership is not verified protection equivalence')
    add('set_subset_area_priority',subset,dict(cells=35,period_ns=period_ns_from_mhz('40')),purpose='35 VersaTiles/bit cap and40MHz require the lower-resource frontier alternative')
    add('set_subset_frequency_priority',subset,dict(cells=40,period_ns=period_ns_from_mhz('42')),purpose='42MHz requirement permits only the faster higher-resource alternative')
    add('set_subset_ambiguous',subset,dict(cells=40,period_ns=period_ns_from_mhz('40.7')),purpose='DF1.28 nominally passes but range straddles budget; DCLR is definitely feasible under supplied bounds')
    first=subset[0]
    assert first['id']=='DF-TMR-DFF-1.28'
    upper=first['metrics']['period_ns']['upper'];lower=first['metrics']['period_ns']['lower']
    for name,limit in [('minimum_frequency_equality',upper),('maximum_frequency_equality',lower),
                       ('one_binary64_step_below_upper',math.nextafter(upper,-math.inf)),
                       ('one_binary64_step_above_lower',math.nextafter(lower,math.inf))]:
        add(name,subset,dict(cells=40,period_ns=limit),kind='numeric_boundary_probe',purpose='Same represented endpoint/adjacent limit supplied to both workflows')
    add('protection_required',subset,dict(cells=40,period_ns=25),True,purpose='Refuse unsupported protection comparison rather than interpreting architecture labels as evidence')
    mismatch=deepcopy(subset);mismatch[-1]['context']['device']='controlled_diagnostic_alternate_device'
    add('context_mismatch',mismatch,kind='diagnostic_fixture',purpose='One deliberately changed device declaration must be diagnosed')
    missing=deepcopy(subset);missing[0]['context']['tool_version']='not reported'
    add('unknown_context',missing,kind='diagnostic_fixture',purpose='Unknown required context cannot be treated as a shared known condition')
    wrongunit=deepcopy(subset);wrongunit[-1]['metrics']['period_ns']['unit']='ps'
    add('unit_semantics_mismatch',wrongunit,kind='diagnostic_fixture',purpose='No implicit unit conversion; mismatched supplied semantics refuse')
    duplicates=deepcopy(subset);duplicates[1]['id']=duplicates[0]['id']
    add('duplicate_identifier',duplicates,kind='diagnostic_fixture',purpose='Reject ambiguous record identity')
    reversedbox=deepcopy(subset);reversedbox[0]['metrics']['period_ns']['lower']=100
    add('reversed_interval',reversedbox,kind='diagnostic_fixture',purpose='Reject malformed interval')
    nosource=deepcopy(subset);del nosource[0]['provenance']['locator']
    add('missing_source_locator',nosource,kind='diagnostic_fixture',purpose='Reject missing required traceability field')
    tie=[deepcopy(subset[0]),deepcopy(subset[0])];tie[0]['id']='tie_probe_A';tie[1]['id']='tie_probe_B'
    for r in tie:r['provenance']['extraction']+='; artificial duplicate-record tie fixture, not an additional published observation'
    add('equal_cost_alternatives',tie,kind='diagnostic_fixture',purpose='Preserve tied alternatives using weak-all/strict-one dominance and paretoset distinct=False')
    for name,limits in [('mapping_unconstrained',{}),('mapping_area_budget',dict(cell_count=60,logic_depth=8)),
                        ('mapping_depth_budget',dict(cell_count=90,logic_depth=7)),('mapping_joint_infeasible',dict(cell_count=60,logic_depth=7))]:
        add(name,synthesis,limits,purpose='Same Boolean function/tool/gate basis; mapped generic structural costs only')
    changed=deepcopy(synthesis);changed[-1]['context']['tool_version']='controlled_alternate_tool_version'
    add('mapping_context_mismatch',changed,kind='diagnostic_fixture',purpose='Do not pool different declared synthesis-tool versions')
    rows=[];provenance_rows=[]
    for spec in specifications:
        name=spec['name'];input_path=out/'inputs'/(name+'.json');dump(input_path,spec['document'])
        rad=compare(spec['document']['records'],spec['limits'],spec['require_verified_protection'])
        baseline=compare_document(spec['document'],spec['limits'],spec['require_verified_protection'])
        if name=='equal_cost_alternatives':assert rad['status']=='accepted' and rad['nominal_front']==['tie_probe_A','tie_probe_B']
        if name.startswith('mapping_') and name!='mapping_context_mismatch':assert rad['status']=='accepted'
        if name=='mapping_area_budget':assert rad['definitely_feasible_nominal_front']==['area_map']
        if name=='mapping_depth_budget':assert rad['definitely_feasible_nominal_front']==['simple_map','balance_map']
        if name=='mapping_joint_infeasible':assert rad['definitely_feasible_nominal_front']==[]
        options={k:spec[k] for k in ('limits','require_verified_protection')}
        digest=hashlib.sha256(input_path.read_bytes()).hexdigest()
        dump(out/'outputs'/(name+'_radpareto.json'),dict(input_sha256=digest,software_version=__version__,options=options,result=rad))
        dump(out/'outputs'/(name+'_conventional.json'),dict(input_sha256=digest,options=options,result=baseline))
        match=project(rad)==project(baseline)
        rows.append(dict(case=name,kind=spec['kind'],radpareto_status=rad['status'],conventional_status=baseline['status'],
            projected_decisions_equal=match,reason_codes=';'.join(sorted({r['code'] for r in rad['reasons']})),
            nominal_front=';'.join(rad.get('nominal_front',[])),
            definitely_feasible_front=';'.join(rad.get('definitely_feasible_nominal_front',[])),
            records=len(spec['document']['records']),input_sha256=digest))
        if rad['status']=='accepted':
            provenance_rows.append(dict(case=name,records=len(rad['record_evidence']),
                source_fields_identical=rad['record_evidence']==baseline['record_evidence'],input_hashes_identical=True))
        if not match:dump(out/(name+'_MISMATCH.json'),dict(radpareto=project(rad),conventional=project(baseline)))
    csv_out(out/'comparison.csv',rows);csv_out(out/'traceability.csv',provenance_rows)
    dump(out/'specifications.json',[{k:v for k,v in s.items() if k!='document'} for s in specifications])
    # The dependency's documented native grouping capability is demonstrated,
    # rather than incorrectly classified as a domain-specific absence.
    import pandas as pd
    from paretoset import paretoset
    frame=pd.DataFrame(dict(cells=[1,2,0],period=[4,3,0],group=['A','A','B']))
    grouped=paretoset(frame,sense=['min','min','diff'],distinct=False,use_numba=False).tolist()
    global_mask=paretoset(frame[['cells','period']],sense=['min','min'],distinct=False,use_numba=False).tolist()
    assert grouped==[True,True,True] and global_mask==[False,False,True]
    dump(out/'native_grouping_probe.json',dict(kind='synthetic_functionality_probe',input=frame.to_dict(orient='records'),
        native_paretoset_diff_group_mask=grouped,unpartitioned_mask=global_mask,
        interpretation='paretoset natively partitions on supplied diff columns; deciding which context fields define valid groups remains caller configuration'))
    scale_rows=[];scenarios={
        'A_count_and_timing_stress':dict(cells=1,period_ns=0.1),
        'B_timing_only_stress':dict(cells=0,period_ns=0.5)}
    for label,scales in scenarios.items():
        value=stability(subset,scales,dict(cells=35,period_ns=25))
        dump(out/(label+'.json'),value)
        for c in value['constraint_certificates']:
            scale_rows.append(dict(scenario=label,record=c['record_id'],objective=c['objective'],scale=scales[c['objective']],
                initial_status=c['initial_status'],transition_t=rational_number(c['transition_t']),
                exact_numerator=None if c['transition_t'] is None else c['transition_t']['numerator'],
                exact_denominator=None if c['transition_t'] is None else c['transition_t']['denominator'],
                boundary_included=c['initial_status_includes_boundary']))
    csv_out(out/'scale_sensitivity.csv',scale_rows)
    # Execute both public-facing CLIs on the same accepted and refused input bytes.
    command_receipts=[]
    env=os.environ.copy()
    if args.engine_src:env['PYTHONPATH']=str(args.engine_src.resolve())
    for name in ('set_subset_ambiguous','context_mismatch'):
        limits=['--limit','cells=40','--limit','period_ns='+str(period_ns_from_mhz('40.7'))]
        input_path=out/'inputs'/(name+'.json')
        commands=[('radpareto',[sys.executable,'-m','radpareto','compare',str(input_path),*limits,'--output',str(out/(name+'_rad_cli.json'))]),
            ('conventional',[sys.executable,str(Path(__file__).with_name('conventional.py')),str(input_path),*limits,'--output',str(out/(name+'_conventional_cli.json'))])]
        for implementation,command in commands:
            run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=120)
            expected=2 if implementation=='radpareto' and name=='context_mismatch' else 0
            assert run.returncode==expected,(implementation,name,run.stderr)
            normal=lambda value:value.replace(str(out).replace('\\','\\\\'),'benchmarks/workflow_comparison/results').replace(str(out),'benchmarks/workflow_comparison/results').replace(str(Path(__file__).parent),'benchmarks/workflow_comparison').replace('\\','/')
            command_receipts.append(dict(case=name,implementation=implementation,command=['python']+[normal(v) for v in command[1:]],returncode=run.returncode,
                path_policy='Executed absolute paths are expressed as equivalent repository-relative reproduction paths; Python executable is represented as python',
                stdout=normal(run.stdout),stderr=normal(run.stderr)))
        rad_cli=json.loads((out/(name+'_rad_cli.json')).read_text());conv_cli=json.loads((out/(name+'_conventional_cli.json')).read_text())
        assert project(rad_cli)==project(conv_cli['result'])
        assert rad_cli['replay']['input_sha256']==conv_cli['input_sha256']
    dump(out/'cli_execution.json',command_receipts)
    versions={name:importlib.metadata.version(name) for name in ('numpy','pandas','paretoset')}
    summary=dict(cases=len(rows),accepted=sum(r['radpareto_status']=='accepted' for r in rows),
        refused=sum(r['radpareto_status']=='refused' for r in rows),agreements=sum(r['projected_decisions_equal'] for r in rows),
        accepted_traceability_checks=len(provenance_rows),all_traceability_equal=all(r['source_fields_identical'] for r in provenance_rows),
        cli_executions=len(command_receipts),native_grouping_probe='passed',scale_scenarios=len(scenarios),
        radpareto_version=__version__,python=platform.python_version(),dependencies=versions,
        compared_fields=['acceptance/refusal','reason-code classes','nominal frontier','certain-dominance screening set',
            'per-limit and overall interval feasibility','feasible-only frontier','accepted source evidence','input hash'],
        not_compared=['exact diagnostic wording/order','all possible malformed inputs','arbitrary-precision inputs','runtime/user time','human usability'],
        differentiation='Identical specified decisions are achievable with custom conventional code. RadPareto packages those domain rules, diagnostics, source-linked outputs and conditional certificates behind a maintained schema/API/CLI; no algorithmic superiority or measured time saving is inferred.',
        selected_subset='Four source-labelled SET-suppression architectures, chosen as an architectural investigation scope, not verified protection-equivalent alternatives',
        scale_interpretation='A widens cells by1 and period by0.1ns per unit t; B fixes counts and widens period by0.5ns per unit t. Analyst-selected stress scenarios, not data-estimated uncertainty or intrinsic robustness. Counts may be fixed when treating only timing perturbations.',
        baseline_custom_code_sha256=hashlib.sha256(Path(__file__).with_name('conventional.py').read_bytes()).hexdigest())
    dump(out/'summary.json',summary)
    assert summary['agreements']==summary['cases'] and summary['all_traceability_equal'],summary
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
