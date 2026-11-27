"""Additional numeric-scope probes, separate from the 23 workflow cases.

Ensures the conventional baseline refuses out-of-scope large integers without
raising during implicit int-to-float conversion. Artificial schema-valid records
are used only to exercise the adapter contract, not as engineering observations.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from conventional import compare_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path(__file__).with_name('results')/'inputs/set_subset_unconstrained.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    base=json.loads(args.input.read_text(encoding='utf-8'))['records'][0]
    cases=[('zero',0,'accepted',None),('largest_declared_integer',2**53,'accepted',None),
        ('first_outside_integer',2**53+1,'refused','BASELINE_NUMERIC_SCOPE'),
        ('positive_huge_integer',10**400,'refused','BASELINE_NUMERIC_SCOPE'),
        ('negative_huge_integer',-(10**400),'refused','INVALID_NUMBER'),
        ('negative_integer',-1,'refused','INVALID_NUMBER'),
        ('positive_infinity',float('inf'),'refused','INVALID_NUMBER'),
        ('nan',float('nan'),'refused','INVALID_NUMBER'),
        ('boolean',True,'refused','INVALID_NUMBER')]
    rows=[]
    for label,value,status,code in cases:
        r=deepcopy(base)
        for key in ('lower','value','upper'):r['metrics']['cells'][key]=value
        result=compare_document(dict(schema_version='1.0',records=[r]))
        assert result['status']==status,(label,result)
        assert code is None or result['reasons'][0]['code']==code,(label,result)
        rows.append(dict(probe=label,status=result['status'],reason_code=None if not result['reasons'] else result['reasons'][0]['code'],passed=True))
    result=dict(probe_count=len(rows),all_passed=True,main_workflow_cases_unchanged=23,probes=rows,
        conventional_sha256=hashlib.sha256(Path(__file__).with_name('conventional.py').read_bytes()).hexdigest(),
        scope='Artificial baseline-adapter numeric contract checks, not RadPareto superiority or additional application observations')
    with args.output.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
