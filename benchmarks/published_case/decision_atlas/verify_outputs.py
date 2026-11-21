"""Independently check retained atlas outputs using Decimal arithmetic.

Imports neither RadPareto nor the atlas analyzer. The input is this published
case package and its generated outputs, not private source extracts or audits.

python benchmarks/published_case/decision_atlas/verify_outputs.py --case-dir benchmarks/published_case --results atlas-replay --out atlas-check.json
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def classify(row, cap, frequency, epsilon=Decimal(0)):
    if Decimal(row['versatiles_per_bit']) > cap:
        return 'definitely_infeasible'
    lo = Decimal(row['fmax_min_mhz']) - epsilon
    hi = Decimal(row['fmax_max_mhz']) + epsilon
    if frequency > hi:
        return 'definitely_infeasible'
    if frequency > lo:
        return 'uncertain'
    return 'definitely_feasible'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-dir', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Output must not already exist')
    source = json.loads((args.case_dir / 'source_exact.json').read_text(encoding='utf-8'))['records']
    manifest_path = args.case_dir / 'decision_atlas/source_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name, sha in manifest['input_sha256'].items():
        assert digest(manifest_path.parent / name) == sha, 'Changed source input: ' + name
    atlas = csv_rows(args.results / 'exact_atlas.csv')
    # Independently reconstruct the required representative Cartesian product.
    # This also catches duplicate or missing rows that could preserve counts.
    resource_cuts = sorted({Decimal(0), *(Decimal(row['versatiles_per_bit']) for row in source)})
    frequency_cuts = sorted({Decimal(0), *(Decimal(row[field]) for row in source
        for field in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'))})
    expected_representatives = []
    for cuts in (resource_cuts, frequency_cuts):
        values = set(cuts)
        values.update((left + right) / 2 for left, right in zip(cuts, cuts[1:]))
        values.add(cuts[-1] + 1)
        expected_representatives.append(values)
    observed_pairs = {(Decimal(row['resource_probe']), Decimal(row['frequency_probe_mhz'])) for row in atlas}
    assert len(observed_pairs) == len(atlas)
    assert observed_pairs == set(itertools.product(*expected_representatives))
    checked = 0
    for region in atlas:
        cap, frequency = Decimal(region['resource_probe']), Decimal(region['frequency_probe_mhz'])
        expected = {kind: [] for kind in ('definitely_feasible', 'uncertain', 'definitely_infeasible')}
        nominal = []
        for row in source:
            expected[classify(row, cap, frequency)].append(row['structure'])
            if Decimal(row['versatiles_per_bit']) <= cap and frequency <= Decimal(row['fmax_mean_mhz']):
                nominal.append(row['structure'])
            checked += 1
        assert '|'.join(expected['definitely_feasible']) == region['feasible_ids']
        assert '|'.join(expected['uncertain']) == region['uncertain_ids']
        assert '|'.join(nominal) == region['nominal_pass_ids']
        assert int(region['feasible_n']) == len(expected['definitely_feasible'])
        assert int(region['uncertain_n']) == len(expected['uncertain'])
        assert int(region['infeasible_n']) == len(expected['definitely_infeasible'])
        assert '|'.join(rid for rid in nominal if rid not in expected['definitely_feasible']) == region['nominal_pass_without_range_support_ids']
    metrics = csv_rows(args.results / 'design_metrics.csv')
    assert len(metrics) == len(source)
    for row, result in zip(source, metrics):
        assert row['structure'] == result['structure']
        lo, mean, hi = (Decimal(row[key]) for key in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'))
        assert Decimal(result['observed_span_mhz']) == hi - lo
        assert Decimal(result['nominal_pass_but_range_not_supported_width_mhz']) == mean - lo
        assert Decimal(result['nominal_fail_but_range_possible_width_mhz']) == hi - mean
        assert Decimal(result['worst_reported_headroom_at_30mhz']) == lo - 30
        assert Decimal(result['worst_reported_headroom_at_32mhz']) == lo - 32
        assert Decimal(result['precision_enclosed_min_mhz']) == lo - Decimal('0.0005')
        assert Decimal(result['precision_enclosed_max_mhz']) == hi + Decimal('0.0005')
        assert abs(Decimal(result['downside_relative_to_mean_percent']) - (mean - lo) / mean * 100) < Decimal('1e-12')
        assert abs(Decimal(result['precision_added_span_percent']) - Decimal('0.001') / (hi - lo) * 100) < Decimal('1e-12')
    merged = csv_rows(args.case_dir / 'decision_atlas/merged_context.csv')
    assert [row['structure'] for row in source] == [row['structure'] for row in merged]
    context = csv_rows(args.results / 'context_comparison.csv')
    by_id = {row['structure']: row for row in context}
    assert len(context) == len(by_id) == len(source)
    assert set(by_id) == {row['structure'] for row in source}
    source_rank = {row['structure']: i + 1 for i, row in enumerate(sorted(source, key=lambda row: Decimal(row['fmax_mean_mhz']), reverse=True))}
    merged_rank = {row['structure']: i + 1 for i, row in enumerate(sorted(merged, key=lambda row: Decimal(row['merged_worst_fmax_mhz']), reverse=True))}
    for row, other in zip(source, merged):
        actual = by_id[row['structure']]
        a, b = Decimal(row['fmax_mean_mhz']), Decimal(other['merged_worst_fmax_mhz'])
        assert Decimal(actual['standalone_mean_mhz']) == a
        assert Decimal(actual['merged_worst_mhz']) == b
        assert Decimal(actual['descriptive_difference_mhz']) == b - a
        assert int(actual['standalone_rank']) == source_rank[row['structure']]
        assert int(actual['merged_rank']) == merged_rank[row['structure']]
        assert abs(Decimal(actual['descriptive_relative_difference_percent']) - (b - a) / a * 100) < Decimal('1e-12')
    pairs = csv_rows(args.results / 'context_pair_orders.csv')
    expected_pairs = list(itertools.combinations(range(len(source)), 2))
    assert len(pairs) == len(expected_pairs)
    reversals = []
    for result, (a, b) in zip(pairs, expected_pairs):
        original = Decimal(source[a]['fmax_mean_mhz']) - Decimal(source[b]['fmax_mean_mhz'])
        other = Decimal(merged[a]['merged_worst_fmax_mhz']) - Decimal(merged[b]['merged_worst_fmax_mhz'])
        reversal = original * other < 0
        assert [result['a'], result['b']] == [source[a]['structure'], source[b]['structure']]
        assert (result['reverses'] == 'True') == reversal
        if reversal:
            reversals.append([source[a]['structure'], source[b]['structure']])
    precision_rows = csv_rows(args.results / 'precision_changed_regions.csv')
    epsilon = Decimal('0.0005')
    precision_cuts = sorted(set(frequency_cuts) | {
        Decimal(row[field]) + sign * epsilon for row in source
        for field in ('fmax_min_mhz', 'fmax_max_mhz') for sign in (-1, 1)})
    precision_probes = set(precision_cuts)
    precision_probes.update((a + b) / 2 for a, b in zip(precision_cuts, precision_cuts[1:]))
    precision_probes.add(precision_cuts[-1] + 1)
    expected_precision_changes = set()
    for frequency, row in itertools.product(precision_probes, source):
        before = classify(row, Decimal(40), frequency)
        after = classify(row, Decimal(40), frequency, epsilon)
        if before != after:
            expected_precision_changes.add((row['structure'], frequency, before, after))
    observed_precision_changes = {
        (row['structure'], Decimal(row['frequency_probe_mhz']), row['printed_range_class'],
            row['precision_enclosed_class']) for row in precision_rows}
    assert len(observed_precision_changes) == len(precision_rows)
    assert observed_precision_changes == expected_precision_changes
    for entry in precision_rows:
        row = next(row for row in source if row['structure'] == entry['structure'])
        frequency = Decimal(entry['frequency_probe_mhz'])
        assert classify(row, Decimal(40), frequency) == entry['printed_range_class']
        assert classify(row, Decimal(40), frequency, Decimal('0.0005')) == entry['precision_enclosed_class']
        assert entry['printed_range_class'] != entry['precision_enclosed_class']
    summary = json.loads((args.results / 'summary.json').read_text(encoding='utf-8'))
    assert len(atlas) == summary['atlas_regions'] == 532
    assert checked == summary['direct_mhz_engine_comparisons'] == 3192
    assert len(reversals) == summary['context_pair_reversals'] == 2
    assert len(precision_rows) == summary['precision_changed_region_rows'] == 24
    assert len(precision_probes) * len(source) == summary['precision_scenario_checks'] == 516
    report = dict(status='passed', arithmetic='Python Decimal; neither analyzer nor engine imported',
        atlas_regions=len(atlas), direct_classifications=checked, design_metric_rows=len(metrics),
        complete_unique_representative_product=True,
        complete_unique_precision_changes=True, precision_reference_checks=len(precision_probes) * len(source),
        context_pairs=len(pairs), reversed_pairs=reversals, precision_changed_rows=len(precision_rows),
        floating_ratio_tolerance='1e-12 absolute percentage points', exact_decimal_fields_tolerance='zero',
        source_manifest_sha256=digest(manifest_path), checker_sha256=digest(Path(__file__)),
        analyzed_result_hashes={p.name: digest(p) for p in sorted(args.results.glob('*')) if p.is_file() and p.resolve() != args.out.resolve()},
        scope='Separate finite numerical implementation; not blinded external/human validation or continuum-wide binary64 proof')
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'atlas_regions', 'direct_classifications', 'context_pairs', 'precision_changed_rows')}))


if __name__ == '__main__':
    main()
