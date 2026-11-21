"""Regression tests for declared decimal frequency/requirement equality."""
from fractions import Fraction
import json
import math
from pathlib import Path
import unittest

from radpareto.units import period_ns_from_mhz


ROOT = Path(__file__).resolve().parents[1]


class DecimalFrequencyConversion(unittest.TestCase):
    def test_source_reciprocals_match_rational_reference(self):
        rows = json.loads((ROOT / 'benchmarks/published_case/source_exact.json').read_text(encoding='utf-8'))['records']
        for row in rows:
            for field in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'):
                with self.subTest(structure=row['structure'], field=field):
                    text = row[field]
                    self.assertEqual(period_ns_from_mhz(text), float(Fraction(1000) / Fraction(text)))
                    self.assertEqual(period_ns_from_mhz(text), period_ns_from_mhz(float(text)))

    def test_endpoint_regression_40578(self):
        upper = period_ns_from_mhz('40.578')
        consistent_limit = period_ns_from_mhz(40.578)
        naive_limit = 1000 / 40.578
        self.assertEqual(upper, consistent_limit)
        self.assertGreater(upper, naive_limit)
        self.assertEqual(math.nextafter(naive_limit, math.inf), upper)

    def test_endpoint_regression_40975(self):
        lower = period_ns_from_mhz('40.975')
        consistent_limit = period_ns_from_mhz(40.975)
        naive_limit = 1000 / 40.975
        self.assertEqual(lower, consistent_limit)
        self.assertGreater(lower, naive_limit)
        self.assertEqual(math.nextafter(naive_limit, math.inf), lower)

    def test_equivalent_decimal_spellings(self):
        values = ['40.578', '4.0578e1', '40578e-3', '+40.5780', ' 40.578 ']
        self.assertEqual(len({period_ns_from_mhz(value) for value in values}), 1)

    def test_decimal_parser_exponent_overflow_uses_value_error(self):
        for value in ['1e' + '9' * 100, '1e-' + '9' * 100]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    period_ns_from_mhz(value)

    def test_distinct_close_decimal_inputs_can_share_binary64_output(self):
        # This documents the representation limit; it is not an exact-decimal
        # ordering guarantee for all inputs between tested representatives.
        for boundary in ['40.578', '40.975']:
            neighbor = boundary + '000000000000000001'
            self.assertGreater(Fraction(neighbor), Fraction(boundary))
            self.assertEqual(period_ns_from_mhz(neighbor), period_ns_from_mhz(boundary))

    def test_strictly_ordered_neighbor_decimal_requirements(self):
        self.assertGreater(period_ns_from_mhz('40.5775'), period_ns_from_mhz('40.578'))
        self.assertGreater(period_ns_from_mhz('40.578'), period_ns_from_mhz('40.5785'))

    def test_invalid_values_rejected(self):
        for value in [True, False, None, {}, [], 0, -1, '-2', 'nan', 'inf', float('nan'), float('inf'),
                      '1/2', '40_578', 'x', '1e99999999', '1e-99999999', '1' * 129, '1e-400', '1e400']:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    period_ns_from_mhz(value)


if __name__ == '__main__':
    unittest.main()
