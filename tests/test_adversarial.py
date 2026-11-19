"""Independent regressions; expected behavior is asserted, failures are findings."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from radpareto import compare
from radpareto import yosys


def record():
    return {'id':'r', 'design':'fixture', 'method':'test',
      'context':dict(baseline_id='b',device='generic',toolchain='test',tool_version='1',
                    implementation='generic',constraints_id='c',timing_corner='abstract',
                    workload_id='w',source_kind='synthetic_example'),
      'metrics':{'cost':dict(value=1,lower=1,upper=1,unit='cells',denominator='absolute',uncertainty_kind='exact')},
      'provenance':dict(source_uri='fixture.py',source_sha256='0'*64,locator='test',extraction='test'),
      'protection':dict(status='verified_within_model',fault_model='not_tested',scope='resource measurement only',evidence_uri='not_available')}


class AdversarialTests(unittest.TestCase):
    def test_protection_placeholders_do_not_count_as_evidence(self):
        result = compare([record()], require_verified_protection=True)
        self.assertEqual(result['status'], 'refused', result)

    def test_missing_context_not_available_refuses(self):
        r = record()
        r['context']['device'] = 'not_available'
        result = compare([r])
        self.assertEqual(result['status'], 'refused', result)

    def test_hierarchical_literal_output_constant(self):
        # A zero-cell submodule assigning y=0 is legal and has depth zero.
        data = {'modules':{
            'zero':{'ports':{'y':{'direction':'output','bits':['0']}}, 'cells':{}},
            'top':{'ports':{'y':{'direction':'output','bits':[2]}},
                   'cells':{'u':{'type':'zero','connections':{'y':[2]}}}}}}
        result = yosys.summarize_yosys(data, 'top')
        self.assertEqual((result['cell_count'],result['logic_depth']), (0,0))

    def test_hierarchy_rejects_invalid_unreferenced_child_output(self):
        # The adapter must not ignore an unknown literal in a child port.
        data = {'modules':{
            'bad':{'ports':{'y':{'direction':'output','bits':['x']}}, 'cells':{}},
            'top':{'ports':{},'cells':{'u':{'type':'bad','connections':{'y':[2]}}}}}}
        with self.assertRaises(ValueError):
            yosys.summarize_yosys(data, 'top')

    def test_hierarchy_constant_output_conflicts_with_external_input(self):
        # A constant child output is a driver and cannot silently be ignored
        # when it is wired to an independent top-level input.
        data = {'modules':{
            'zero':{'ports':{'y':{'direction':'output','bits':['0']}}, 'cells':{}},
            'top':{'ports':{'a':{'direction':'input','bits':[2]}},
                   'cells':{'u':{'type':'zero','connections':{'y':[2]}}}}}}
        with self.assertRaises(ValueError):
            yosys.summarize_yosys(data, 'top')

    def test_interval_and_limit_boundary_hand_cases(self):
        # Robust screening differs intentionally from nominal screening.
        a, b = record(), record()
        a['id'], b['id'] = 'a', 'b'
        a['metrics']['cost'].update(value=1,lower=0,upper=2,uncertainty_kind='bounded')
        b['metrics']['cost'].update(value=3,lower=2,upper=4,uncertainty_kind='bounded')
        result = compare([a,b],limits={'cost':2})
        self.assertEqual(result['nominal_front'], ['a'])
        self.assertEqual(result['not_certainly_dominated'], ['a','b'])
        self.assertEqual(result['feasibility']['a']['status'], 'definitely_feasible')
        self.assertEqual(result['feasibility']['b']['status'], 'uncertain')
        a['metrics']['cost']['upper'] = 1
        self.assertEqual(compare([a,b])['not_certainly_dominated'], ['a'])

    def test_unknown_source_kind_refuses(self):
        r = record()
        r['context']['source_kind'] = 'laboratory_observation'
        self.assertEqual(compare([r])['status'], 'refused')


if __name__ == '__main__':
    unittest.main(verbosity=2)
