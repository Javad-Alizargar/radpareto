"""Direct-MHz regression oracle independent of the reciprocal adapter."""
import copy
import csv
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import unittest

from radpareto.compare import batch_compare, compare
from radpareto.units import period_ns_from_mhz

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'benchmarks/published_case'


def decimal_text(value):
    return str(Decimal(value.numerator) / Decimal(value.denominator))


def record_from_source(row):
    """Independent exact-source fixture, without the conversion helper."""
    low, mean, high = (Fraction(row[key]) for key in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'))
    context = dict(baseline_id='source_BL_DFF', device='A3PE3000', toolchain='Libero', tool_version='11.8.1.12',
        implementation='standalone_post_layout', constraints_id='common_30MHz', timing_corner='1.425V_125C',
        workload_id='dual243bit', source_kind='published_table')
    return dict(id=row['structure'], design='Ma2026_dual243bit', method=row['structure'], context=context,
        metrics=dict(period_ns=dict(value=float(1000 / mean), lower=float(1000 / high), upper=float(1000 / low),
            unit='ns', denominator='reciprocal_standalone_frequency_summary', uncertainty_kind='bounded')),
        provenance=dict(source_uri='benchmarks/published_case/source_exact.json',
            source_sha256=hashlib.sha256((CASE / 'source_exact.json').read_bytes()).hexdigest(),
            locator='Table10 row ' + row['structure'], extraction='Exact-string source-frequency fixture'),
        protection=dict(status='unverified', fault_model='not_assessed', scope='cost_only', evidence_uri='https://doi.org/10.3390/electronics15225390'))


class PublishedBoundaryRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((CASE / 'source_exact.json').read_text(encoding='utf-8'))['records']

    def test_all_source_endpoint_equalities_and_neighbors(self):
        naive_mismatches = []
        checked = 0
        for row in self.rows:
            record = record_from_source(row)
            for field in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'):
                for delta in (Fraction(-1, 1000000), Fraction(0), Fraction(1, 1000000)):
                    frequency = Fraction(row[field]) + delta
                    expected = ('definitely_feasible' if frequency <= Fraction(row['fmax_min_mhz']) else
                                'definitely_infeasible' if frequency > Fraction(row['fmax_max_mhz']) else 'uncertain')
                    token = decimal_text(frequency)
                    with self.subTest(structure=row['structure'], field=field, delta=str(delta)):
                        result = compare([record], limits={'period_ns': period_ns_from_mhz(token)})
                        self.assertEqual(result['status'], 'accepted')
                        self.assertEqual(result['feasibility'][record['id']]['status'], expected)
                        old = compare([record], limits={'period_ns': 1000 / float(token)})
                        if old['feasibility'][record['id']]['status'] != expected:
                            naive_mismatches.append((row['structure'], field, str(delta)))
                        checked += 1
        self.assertEqual(checked, 54)
        self.assertEqual(naive_mismatches, [('DF-TMR-DFF-1.28', 'fmax_min_mhz', '0'),
                                         ('DF-TMR-DFF-1.28', 'fmax_max_mhz', '0')])

    def test_actual_merged_summary_cannot_enter_standalone_group(self):
        with (CASE / 'decision_atlas/merged_context.csv').open(encoding='utf-8', newline='') as stream:
            merged = list(csv.DictReader(stream))
        standalone = [record_from_source(row) for row in self.rows]
        combined = copy.deepcopy(standalone)
        for record, source in zip(standalone, merged):
            other = copy.deepcopy(record)
            other['id'] += '__merged'
            other['context']['implementation'] = 'merged_six_structure_project'
            other['context']['workload_id'] = 'six_clock_domains_on_one_chip'
            cost = period_ns_from_mhz(source['merged_worst_fmax_mhz'])
            other['metrics']['period_ns'].update(value=cost, lower=cost, upper=cost,
                denominator='reciprocal_worst_merged_summary', uncertainty_kind='exact')
            combined.append(other)
        result = compare(combined)
        self.assertEqual(result['status'], 'refused')
        self.assertTrue({'CONTEXT_MISMATCH', 'METRIC_SEMANTICS_MISMATCH'} <= {item['code'] for item in result['reasons']})
        partitions = batch_compare(combined)
        self.assertEqual(partitions['status'], 'accepted')
        self.assertEqual(sorted(len(group['record_ids']) for group in partitions['groups']), [6, 6])


if __name__ == '__main__':
    unittest.main()
