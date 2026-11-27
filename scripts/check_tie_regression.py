"""Probe existing current regressions against current and frozen tie defects.

This post-study coverage check does not change the frozen mutation experiment,
its four scored diagnostic families, or its 11/12 detection result.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'benchmarks/mutation/frozen_study'
TESTS = [
    'test_known_tradeoff_dominance_and_equal_points',
    'test_rounding_tie_changes_certainty_not_nominal',
]
CHILD = r'''
import importlib.util, json, pathlib, sys, unittest
source, test_file, name = sys.argv[1:]
sys.path.insert(0, source)
import radpareto
candidate = pathlib.Path(radpareto.__file__).resolve()
assert candidate.parent == pathlib.Path(source).resolve() / 'radpareto'
spec = importlib.util.spec_from_file_location('selected_current_test', test_file)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.TestSuite([module.ComparisonTests(name)])
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps(dict(tests_run=result.testsRun, failures=len(result.failures),
    errors=len(result.errors), skipped=len(result.skipped),
    software_version=radpareto.__version__)))
sys.exit(0 if result.wasSuccessful() else 1)
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a fresh output path')
    freeze = json.loads((STUDY / 'freeze.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        if digest(STUDY / name) != expected:
            raise ValueError('Frozen-study hash mismatch: ' + name)
    rows = []
    for variant, source in [('CURRENT', ROOT / 'src'),
                            ('M01', STUDY / 'variants/M01/src'),
                            ('M02', STUDY / 'variants/M02/src')]:
        for test in TESTS:
            proc = subprocess.run([sys.executable, '-B', '-c', CHILD,
                str(source), str(ROOT / 'tests/test_core.py'), test],
                text=True, capture_output=True, check=False)
            observed = json.loads(proc.stdout.strip().splitlines()[-1])
            assert observed['tests_run'] == 1 and observed['errors'] == 0
            expected_failure = (variant, test) in {
                ('M01', TESTS[0]), ('M02', TESTS[1])}
            assert observed['failures'] == int(expected_failure), (variant, test, proc.stderr)
            assert proc.returncode == int(expected_failure)
            rows.append(dict(variant=variant, test='ComparisonTests.'+test,
                outcome='assertion_failure' if expected_failure else 'pass',
                returncode=proc.returncode, **observed,
                compare_sha256=digest(source / 'radpareto/compare.py'),
                test_output=proc.stderr))
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
        status='passed', probe_kind='post-study execution of existing regression methods',
        test_file='tests/test_core.py', test_sha256=digest(ROOT / 'tests/test_core.py'),
        frozen_manifest_sha256=digest(STUDY / 'freeze.json'), frozen_files_checked=len(freeze['files']),
        historical_mutation_result_unchanged=dict(detected=11,total=12,survivor='M01'),
        rows=rows, scope='Current existing regressions detect the retained M01/M02 defects; '
            'this is additional coverage evidence, not a retrospective change to the frozen experiment.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], current_regressions=2,
        expected_mutant_assertion_failures=2, runtime_errors=0,
        historical_detection_result='11/12 unchanged')))


if __name__ == '__main__':
    main()
