"""Transparent conventional workflow: pandas/NumPy + paretoset + explicit rules.

No RadPareto imports. Pareto sorting is supplied by paretoset; domain eligibility,
range interpretation, diagnostics and provenance packaging below are additional
custom code. Conditional stability certificates are not implemented by this
baseline; the separate scale scenarios use RadPareto. This is a composed
baseline, not a claim that a bare
general-purpose sorter promises domain validation. No runtime speed comparison.
The benchmark costs fit binary64; this baseline deliberately refuses integers
above 2**53 rather than silently coercing them during paretoset table creation.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd
from paretoset import paretoset

CONTEXT={'baseline_id','device','toolchain','tool_version','implementation',
         'constraints_id','timing_corner','workload_id','source_kind'}
SOURCE={'published_table','synthesis','simulation','measurement','analytical','synthetic_example'}
KINDS={'exact','rounding','bounded','statistical'}
UNKNOWN={'unknown','unspecified','undefined','missing','pending','tbd','tbc','?','none','null','n_a','na',
 'unavailable','unreported','unresolved','untested','unmeasured','unverified','unvalidated','unassessed',
 'not_reported','not_available','not_tested','not_measured','not_verified','not_validated','not_assessed',
 'not_evaluated','not_provided','not_supplied','not_recorded','not_known','not_applicable',
 'not_demonstrated','not_established','no_data','no_evidence','insufficient_evidence','no_support'}


class Invalid(ValueError):
    def __init__(self,code,path,message):
        self.reason=dict(code=code,path=path,message=message)
        super().__init__(message)


def fields(value,expected,path):
    if not isinstance(value,dict):
        raise Invalid('INVALID_TYPE',path,'Expected an object')
    if expected-set(value):
        raise Invalid('MISSING_FIELD',path,', '.join(sorted(expected-set(value))))
    if set(value)-expected:
        raise Invalid('UNSUPPORTED_FIELD',path,'Unsupported fields')


def text(value,path):
    if not isinstance(value,str) or not value.strip() or value!=value.strip() or len(value)>4096 or any(ord(c)<32 for c in value):
        raise Invalid('INVALID_STRING',path,'Expected nonempty trimmed text without control characters')


def number(value,path):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or value<0:
        raise Invalid('INVALID_NUMBER',path,'Expected finite nonnegative cost')
    if isinstance(value,int) and not isinstance(value,bool) and value>2**53:
        raise Invalid('BASELINE_NUMERIC_SCOPE',path,'This declared baseline supports integers no larger than 2**53')
    if not math.isfinite(value):
        raise Invalid('INVALID_NUMBER',path,'Expected finite nonnegative cost')


def unknown(value):
    return re.sub(r'[\s_/\-\u2010-\u2015]+','_',value.casefold()).strip('_') in UNKNOWN


def validate(document):
    fields(document,{'schema_version','records'},'document')
    if document['schema_version']!='1.0':
        raise Invalid('UNSUPPORTED_SCHEMA','schema_version','Expected 1.0')
    records=document['records']
    if not isinstance(records,list) or not 1<=len(records)<=2000:
        raise Invalid('INVALID_RECORDS','records','Expected 1 to 2000 records')
    ids=set()
    for i,r in enumerate(records):
        loc=f'records[{i}]'
        fields(r,{'id','design','method','context','metrics','provenance','protection'},loc)
        for k in ('id','design','method'):text(r[k],loc+'.'+k)
        if r['id'] in ids:raise Invalid('DUPLICATE_ID',loc+'.id','Duplicate identifier')
        ids.add(r['id'])
        fields(r['context'],CONTEXT,loc+'.context')
        for k,v in r['context'].items():text(v,loc+'.context.'+k)
        if r['context']['source_kind'] not in SOURCE:raise Invalid('INVALID_SOURCE_KIND',loc,'Unsupported source kind')
        if not isinstance(r['metrics'],dict) or not 1<=len(r['metrics'])<=16:raise Invalid('INVALID_METRICS',loc,'Expected 1 to 16 objectives')
        for n,m in r['metrics'].items():
            if not isinstance(n,str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}',n):raise Invalid('INVALID_METRIC_NAME',loc,'Invalid objective name')
            mp=loc+'.metrics.'+n
            fields(m,{'value','lower','upper','unit','denominator','uncertainty_kind'},mp)
            for k in ('value','lower','upper'):number(m[k],mp+'.'+k)
            if not m['lower']<=m['value']<=m['upper']:raise Invalid('INVALID_INTERVAL',mp,'Require lower <= value <= upper')
            for k in ('unit','denominator','uncertainty_kind'):text(m[k],mp+'.'+k)
            if m['uncertainty_kind'] not in KINDS:raise Invalid('INVALID_UNCERTAINTY_KIND',mp,'Unsupported interval semantics')
            if m['uncertainty_kind']=='exact' and m['lower']!=m['upper']:raise Invalid('NONEXACT_INTERVAL',mp,'Exact metric must have zero width')
        fields(r['provenance'],{'source_uri','source_sha256','locator','extraction'},loc+'.provenance')
        for k,v in r['provenance'].items():text(v,loc+'.provenance.'+k)
        if not re.fullmatch('[0-9a-f]{64}',r['provenance']['source_sha256']):raise Invalid('INVALID_SHA256',loc,'Invalid declared source hash')
        fields(r['protection'],{'status','fault_model','scope','evidence_uri'},loc+'.protection')
        for k,v in r['protection'].items():text(v,loc+'.protection.'+k)
        if r['protection']['status'] not in {'unverified','verified_within_model'}:raise Invalid('INVALID_PROTECTION_STATUS',loc,'Unsupported declaration')
    return deepcopy(records)


def nominal(table):
    if table.empty:return []
    # distinct=False preserves all equal-cost alternatives; no false tie dominance.
    keep=paretoset(table,sense=['min']*len(table.columns),distinct=False,use_numba=False)
    return table.index[keep].tolist()


def compare_document(document,limits=None,require_verified_protection=False):
    try:
        records=validate(document)
        if not isinstance(require_verified_protection,bool):raise Invalid('INVALID_OPTION','options','Protection flag must be boolean')
        first=records[0];names=sorted(first['metrics']);reasons=[]
        def reason(code,message,**kw):reasons.append(dict(code=code,message=message,**kw))
        for r in records:
            for k,v in r['context'].items():
                if unknown(v):reason('UNKNOWN_CONTEXT','Required context is unknown',record=r['id'],field=k)
            for k in ('design','method'):
                if unknown(r[k]):reason('UNKNOWN_IDENTITY','Design/method identity is unknown',record=r['id'],field=k)
            for n,m in r['metrics'].items():
                for k in ('unit','denominator'):
                    if unknown(m[k]):reason('UNKNOWN_METRIC_SEMANTICS','Metric semantics unknown',record=r['id'],metric=n,field=k)
            for k in ('source_uri','locator','extraction'):
                if unknown(r['provenance'][k]):reason('UNKNOWN_PROVENANCE','Source location or extraction unknown',record=r['id'],field=k)
            if r['design']!=first['design']:reason('DESIGN_MISMATCH','Designs differ',record=r['id'])
            for k in CONTEXT:
                if r['context'][k]!=first['context'][k]:reason('CONTEXT_MISMATCH','Comparison context differs',record=r['id'],field=k)
            if set(r['metrics'])!=set(names):reason('METRIC_SET_MISMATCH','Objective names differ',record=r['id'])
            else:
                for n in names:
                    for k in ('unit','denominator','uncertainty_kind'):
                        if r['metrics'][n][k]!=first['metrics'][n][k]:reason('METRIC_SEMANTICS_MISMATCH','Objective semantics differ',record=r['id'],metric=n,field=k)
            if require_verified_protection:
                p=r['protection']
                if p['status']!='verified_within_model' or any(unknown(p[k]) for k in ('fault_model','scope','evidence_uri')):reason('PROTECTION_UNVERIFIED','Explicit model evidence required',record=r['id'])
                for k in ('fault_model','scope','evidence_uri'):
                    if p[k]!=first['protection'][k]:reason('PROTECTION_CONTEXT_MISMATCH','Protection conditions differ',record=r['id'],field=k)
        limits={} if limits is None else limits
        if not isinstance(limits,dict):raise Invalid('INVALID_LIMITS','limits','Expected an objective-number mapping')
        for k,v in limits.items():
            if k not in names:reason('UNKNOWN_LIMIT_METRIC','Absent objective',metric=k)
            number(v,'limits.'+k)
        if reasons:return dict(status='refused',reasons=reasons)
        ids=[r['id'] for r in records]
        tables={f:pd.DataFrame([[r['metrics'][n][f] for n in names] for r in records],index=ids,columns=names) for f in ('value','lower','upper')}
        lower=tables['lower'].to_numpy();upper=tables['upper'].to_numpy()
        # NumPy broadcast compares upper(A) with lower(B), preserving strictness.
        certain=np.all(upper[:,None,:]<=lower[None,:,:],axis=2)&np.any(upper[:,None,:]<lower[None,:,:],axis=2)
        np.fill_diagonal(certain,False)
        feasibility={}
        for rid in ids:
            states={n:('definitely_infeasible' if tables['lower'].loc[rid,n]>bound else 'definitely_feasible' if tables['upper'].loc[rid,n]<=bound else 'uncertain') for n,bound in limits.items()}
            status='definitely_infeasible' if 'definitely_infeasible' in states.values() else 'uncertain' if 'uncertain' in states.values() else 'definitely_feasible'
            feasibility[rid]=dict(status=status,per_limit=states)
        feasible=[rid for rid in ids if feasibility[rid]['status']=='definitely_feasible']
        return dict(status='accepted',reasons=[],nominal_front=nominal(tables['value']),
            not_certainly_dominated=[rid for j,rid in enumerate(ids) if not certain[:,j].any()],
            feasibility=feasibility,definitely_feasible_nominal_front=nominal(tables['value'].loc[feasible]),
            record_evidence={r['id']:{k:r[k] for k in ('method','metrics','provenance','protection')} for r in records},
            limits=limits,warnings=['Source fields are declarations, not authentication.','All supplied boxes and scale scenarios are conditional, not physical reliability guarantees.'])
    except Invalid as error:
        return dict(status='refused',reasons=[error.reason])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--limit',action='append',default=[])
    parser.add_argument('--require-protection',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.input.read_bytes()
    limits={k:float(v) for k,v in (s.split('=',1) for s in args.limit)}
    value=compare_document(json.loads(raw),limits,args.require_protection)
    envelope=dict(input_sha256=hashlib.sha256(raw).hexdigest(),workflow='pandas-numpy-paretoset-custom-domain-rules',
        options=dict(limits=limits,require_verified_protection=args.require_protection),result=value)
    with args.output.open('x',encoding='utf-8') as handle:json.dump(envelope,handle,indent=2);handle.write('\n')
    print(json.dumps(dict(status=value['status'],output=str(args.output))))


if __name__=='__main__':main()
