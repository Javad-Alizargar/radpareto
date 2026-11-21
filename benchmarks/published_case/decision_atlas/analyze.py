"""Exact published-frequency budget partitions and context diagnostics.

Run from the public repository root:
python benchmarks/published_case/decision_atlas/analyze.py --engine-src src --out atlas-replay
"""
import argparse
import copy
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import platform
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def write_csv(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def decimal_text(value):
    value = Fraction(value)
    with localcontext() as context:
        context.prec = 60
        return format(Decimal(value.numerator) / Decimal(value.denominator), 'f')


def state(source, cells_cap, required_mhz, precision=Fraction(0)):
    """Independent direct-frequency rule: never calls the cost converter."""
    if Fraction(source['versatiles_per_bit']) > cells_cap:
        return 'definitely_infeasible'
    if required_mhz <= Fraction(source['fmax_min_mhz']) - precision:
        return 'definitely_feasible'
    if required_mhz > Fraction(source['fmax_max_mhz']) + precision:
        return 'definitely_infeasible'
    return 'uncertain'


def faces(breaks):
    """Complete point/open-interval partition of the nonnegative half-line."""
    breaks = sorted(set([Fraction(0), *breaks]))
    output = []
    for i, value in enumerate(breaks):
        output.append(dict(kind='point', lower=value, upper=value, probe=value))
        if i + 1 < len(breaks):
            upper = breaks[i + 1]
            output.append(dict(kind='open', lower=value, upper=upper, probe=(value + upper) / 2))
    output.append(dict(kind='open_unbounded', lower=breaks[-1], upper=None, probe=breaks[-1] + 1))
    return output


def label(face):
    if face['kind'] == 'point':
        return '{' + decimal_text(face['lower']) + '}'
    return '(' + decimal_text(face['lower']) + ',' + (decimal_text(face['upper']) if face['upper'] is not None else 'infinity') + ')'


def build_records(rows, metadata, converter, precision=Fraction(0)):
    result = []
    for row in rows:
        cells = int(row['versatiles_per_bit'])
        result.append({
            'id': row['structure'], 'design': 'dual_243_bit_shift_register_486_logic_bits', 'method': row['structure'],
            'context': {
                'baseline_id': 'Ma2026_BL-DFF_11_VersaTiles_per_logic_bit',
                'device': metadata['context']['device'], 'toolchain': 'Libero SoC',
                'tool_version': metadata['context']['tool_version'],
                'implementation': metadata['context']['implementation'],
                'constraints_id': 'Ma2026_standalone_common_flow_30MHz_reference_33.333ns',
                'timing_corner': metadata['context']['timing_corner'],
                'workload_id': metadata['context']['workload'], 'source_kind': 'published_table'},
            'metrics': {
                'cells': {'value': cells, 'lower': cells, 'upper': cells, 'unit': 'VersaTiles', 'denominator': 'logic_bit_excluding_one_off_project_overhead', 'uncertainty_kind': 'exact'},
                'period_ns': {'value': converter(row['fmax_mean_mhz']),
                    'lower': converter(decimal_text(Fraction(row['fmax_max_mhz']) + precision)),
                    'upper': converter(decimal_text(Fraction(row['fmax_min_mhz']) - precision)),
                    'unit': 'ns', 'denominator': 'clock_cycle_reciprocal_of_standalone_fmax', 'uncertainty_kind': 'bounded'}},
            'provenance': {'source_uri': 'benchmarks/published_case/source_tables.csv', 'source_sha256': digest(Path(__file__).resolve().parent.parent / 'source_tables.csv'),
                'locator': 'Tables 9 and 10, row ' + row['structure'],
                'extraction': 'Original exact-decimal numerical transcription; reciprocal summary/range costs, no raw-run reconstruction'},
            'protection': {'status': 'unverified', 'fault_model': 'not_assessed', 'scope': 'cost_only_no_protection_equivalence', 'evidence_uri': metadata['source']['url']}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-src', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    parent = here.parent
    frozen = json.loads((here / 'source_manifest.json').read_text(encoding='utf-8'))
    for name, sha in frozen['input_sha256'].items():
        assert digest(here / name) == sha, 'Input hash mismatch: ' + name
    rows = json.loads((parent / 'source_exact.json').read_text(encoding='utf-8'))['records']
    metadata = json.loads((parent / 'source_metadata.json').read_text(encoding='utf-8'))
    with (here / 'merged_context.csv').open(encoding='utf-8', newline='') as stream:
        merged_rows = list(csv.DictReader(stream))
    assert [r['structure'] for r in rows] == [r['structure'] for r in merged_rows]
    sys.path.insert(0, str(args.engine_src.resolve()))
    from radpareto.compare import compare, batch_compare
    from radpareto.units import period_ns_from_mhz
    args.out.mkdir(parents=True, exist_ok=False)
    records = build_records(rows, metadata, period_ns_from_mhz)
    precision = Fraction(1, 2000)
    expanded = build_records(rows, metadata, period_ns_from_mhz, precision)
    design_metrics = []
    for row in rows:
        mean, lower, upper = (Fraction(row[k]) for k in ('fmax_mean_mhz', 'fmax_min_mhz', 'fmax_max_mhz'))
        design_metrics.append({
            'structure': row['structure'], 'cells_per_bit': int(row['versatiles_per_bit']),
            'fmin_mhz': decimal_text(lower), 'fmean_mhz': decimal_text(mean), 'fmax_mhz': decimal_text(upper),
            'observed_span_mhz': decimal_text(upper - lower),
            'nominal_pass_but_range_not_supported_width_mhz': decimal_text(mean - lower),
            'nominal_fail_but_range_possible_width_mhz': decimal_text(upper - mean),
            'downside_relative_to_mean_percent': float((mean - lower) / mean * 100),
            'worst_reported_headroom_at_30mhz': decimal_text(lower - 30),
            'worst_reported_headroom_at_32mhz': decimal_text(lower - 32),
            'precision_enclosed_min_mhz': decimal_text(lower - precision),
            'precision_enclosed_max_mhz': decimal_text(upper + precision),
            'precision_added_span_percent': float(2 * precision / (upper - lower) * 100),
            'nominal_period_exact_fraction_ns': str(Fraction(1000) / mean),
            'lower_period_exact_fraction_ns': str(Fraction(1000) / upper),
            'upper_period_exact_fraction_ns': str(Fraction(1000) / lower)})
    write_csv(args.out / 'design_metrics.csv', design_metrics)
    cfaces = faces(Fraction(r['versatiles_per_bit']) for r in rows)
    fbreaks = [Fraction(r[k]) for r in rows for k in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz')]
    ffaces = faces(fbreaks)
    cells, mismatches, checks = [], [], 0
    for cf, ff in itertools.product(cfaces, ffaces):
        cap, frequency = cf['probe'], ff['probe']
        limits = {'cells': float(cap)}
        if frequency:
            limits['period_ns'] = period_ns_from_mhz(decimal_text(frequency))
        actual = compare(records, limits=limits)
        assert actual['status'] == 'accepted'
        expected = {r['structure']: state(r, cap, frequency) for r in rows}
        for rid, classification in expected.items():
            checks += 1
            observed = actual['feasibility'][rid]['status']
            if observed != classification:
                mismatches.append(dict(structure=rid, cap=str(cap), frequency=str(frequency), expected=classification, actual=observed))
        nominal = [r['structure'] for r in rows if Fraction(r['versatiles_per_bit']) <= cap and frequency <= Fraction(r['fmax_mean_mhz'])]
        groups = {name: [rid for rid, value in expected.items() if value == name] for name in ('definitely_feasible', 'uncertain', 'definitely_infeasible')}
        cells.append(dict(resource_region=label(cf), frequency_region_mhz=label(ff), resource_probe=decimal_text(cap), frequency_probe_mhz=decimal_text(frequency),
            feasible_n=len(groups['definitely_feasible']), uncertain_n=len(groups['uncertain']), infeasible_n=len(groups['definitely_infeasible']),
            feasible_ids='|'.join(groups['definitely_feasible']), uncertain_ids='|'.join(groups['uncertain']),
            nominal_pass_ids='|'.join(nominal), nominal_pass_without_range_support_ids='|'.join(rid for rid in nominal if expected[rid] != 'definitely_feasible')))
    assert not mismatches, mismatches
    write_csv(args.out / 'exact_atlas.csv', cells)
    # Exact source boundary values and adjacent midpoints expose adapter errors.
    conversion_rows = []
    for row in rows:
        for key in ('fmax_min_mhz', 'fmax_mean_mhz', 'fmax_max_mhz'):
            f = row[key]
            expected = state(row, Fraction(40), Fraction(f))
            naive = 1000 / float(f)
            fixed = period_ns_from_mhz(f)
            naive_result = compare(records, limits={'cells': 40, 'period_ns': naive})
            fixed_result = compare(records, limits={'cells': 40, 'period_ns': fixed})
            conversion_rows.append(dict(structure=row['structure'], source_field=key, frequency_mhz=f,
                exact_reciprocal_ns=str(Fraction(1000) / Fraction(f)), naive_period_hex=naive.hex(), consistent_period_hex=fixed.hex(),
                expected_class=expected, naive_class=naive_result['feasibility'][row['structure']]['status'],
                consistent_class=fixed_result['feasibility'][row['structure']]['status']))
    assert all(r['consistent_class'] == r['expected_class'] for r in conversion_rows)
    write_csv(args.out / 'conversion_boundary_audit.csv', conversion_rows)
    old_scenarios = []
    for cap, frequency in itertools.product((20, 30, 40), (30, 32, 40, 50)):
        previous = compare(records, limits={'cells': cap, 'period_ns': 1000 / frequency})
        updated = compare(records, limits={'cells': cap, 'period_ns': period_ns_from_mhz(frequency)})
        enclosure = compare(expanded, limits={'cells': cap, 'period_ns': period_ns_from_mhz(frequency)})
        for row in rows:
            rid = row['structure']
            old_scenarios.append(dict(structure=rid, cells_cap=cap, frequency_mhz=frequency,
                previous=previous['feasibility'][rid]['status'], consistent=updated['feasibility'][rid]['status'],
                precision_enclosure=enclosure['feasibility'][rid]['status']))
    assert all(r['previous'] == r['consistent'] == r['precision_enclosure'] for r in old_scenarios)
    write_csv(args.out / 'old_scenario_recheck.csv', old_scenarios)
    # Expanded-box precision sensitivity, checked at all new boundaries/interiors.
    pbreaks = [*fbreaks, *(Fraction(r[k]) + sign * precision for r in rows for k in ('fmax_min_mhz', 'fmax_max_mhz') for sign in (-1, 1))]
    precision_checks, precision_difference_rows = 0, []
    for ff in faces(pbreaks):
        frequency = ff['probe']
        limits = {'cells': 40}
        if frequency:
            limits['period_ns'] = period_ns_from_mhz(decimal_text(frequency))
        actual = compare(expanded, limits=limits)
        for row in rows:
            rid = row['structure']
            expected = state(row, Fraction(40), frequency, precision)
            precision_checks += 1
            assert actual['feasibility'][rid]['status'] == expected
            original = state(row, Fraction(40), frequency)
            if original != expected:
                precision_difference_rows.append(dict(structure=rid, frequency_region_mhz=label(ff), frequency_probe_mhz=decimal_text(frequency),
                    printed_range_class=original, precision_enclosed_class=expected))
    write_csv(args.out / 'precision_changed_regions.csv', precision_difference_rows)
    # Do not combine standalone resource costs with merged timing summaries.
    standalone_timing, merged_timing = [], []
    for record, source, merged in zip(records, rows, merged_rows):
        stand = copy.deepcopy(record)
        stand['id'] += '__standalone'
        stand['metrics'].pop('cells')
        standalone_timing.append(stand)
        other = copy.deepcopy(stand)
        other['id'] = source['structure'] + '__merged'
        other['context']['implementation'] = 'merged_six_structure_irradiation_project_post_layout_STA'
        other['context']['constraints_id'] = 'Ma2026_merged_CLKA_to_CLKF_30MHz_timing_closure'
        other['context']['workload_id'] = 'six_domains_on_one_A3PE3000_merged_project_Table11'
        period = period_ns_from_mhz(merged['merged_worst_fmax_mhz'])
        other['metrics']['period_ns'] = dict(value=period, lower=period, upper=period, unit='ns',
            denominator='reciprocal_of_reported_worst_merged_project_fmax_summary', uncertainty_kind='exact')
        other['provenance'] = dict(source_uri='benchmarks/published_case/decision_atlas/merged_context.csv', source_sha256=digest(here / 'merged_context.csv'),
            locator='Table11 Achievable fmax per domain, ' + merged['domain'],
            extraction='Exact printed worst-case summary only; no uncertainty interval or individual runs supplied')
        merged_timing.append(other)
    refusal = compare(standalone_timing + merged_timing)
    partitions = batch_compare(standalone_timing + merged_timing)
    assert refusal['status'] == 'refused'
    assert partitions['status'] == 'accepted' and sorted(len(g['record_ids']) for g in partitions['groups']) == [6, 6]
    standalone_order = sorted(rows, key=lambda r: Fraction(r['fmax_mean_mhz']), reverse=True)
    merged_order = sorted(merged_rows, key=lambda r: Fraction(r['merged_worst_fmax_mhz']), reverse=True)
    context_rows = []
    for source, merged in zip(rows, merged_rows):
        a, b = Fraction(source['fmax_mean_mhz']), Fraction(merged['merged_worst_fmax_mhz'])
        context_rows.append(dict(structure=source['structure'], standalone_mean_mhz=decimal_text(a),
            standalone_min_mhz=source['fmax_min_mhz'], standalone_max_mhz=source['fmax_max_mhz'],
            merged_worst_mhz=decimal_text(b), standalone_rank=1 + standalone_order.index(source), merged_rank=1 + merged_order.index(merged),
            descriptive_difference_mhz=decimal_text(b - a), descriptive_relative_difference_percent=float((b - a) / a * 100)))
    rank_rows = []
    for a, b in itertools.combinations(context_rows, 2):
        standalone_sign = (Fraction(a['standalone_mean_mhz']) > Fraction(b['standalone_mean_mhz'])) - (Fraction(a['standalone_mean_mhz']) < Fraction(b['standalone_mean_mhz']))
        merged_sign = (Fraction(a['merged_worst_mhz']) > Fraction(b['merged_worst_mhz'])) - (Fraction(a['merged_worst_mhz']) < Fraction(b['merged_worst_mhz']))
        rank_rows.append(dict(a=a['structure'], b=b['structure'], standalone_order_sign=standalone_sign, merged_order_sign=merged_sign, reverses=standalone_sign * merged_sign == -1))
    write_csv(args.out / 'context_comparison.csv', context_rows)
    write_csv(args.out / 'context_pair_orders.csv', rank_rows)
    dump(args.out / 'context_records.json', {'schema_version': '1.0', 'records': standalone_timing + merged_timing})
    dump(args.out / 'context_mixing_refusal.json', refusal)
    dump(args.out / 'context_batch_partitions.json', partitions)
    summary = dict(designs=len(rows), new_source_values=len(merged_rows), source_frequency_breakpoints=len(set(fbreaks)),
        resource_faces=len(cfaces), frequency_faces=len(ffaces), atlas_regions=len(cells), direct_mhz_engine_comparisons=checks,
        direct_mhz_engine_mismatches=len(mismatches), source_endpoint_checks=len(conversion_rows),
        naive_conversion_class_mismatches=sum(r['naive_class'] != r['expected_class'] for r in conversion_rows),
        consistent_conversion_class_mismatches=sum(r['consistent_class'] != r['expected_class'] for r in conversion_rows),
        old_scenarios_unchanged=len(old_scenarios), precision_scenario_checks=precision_checks,
        precision_changed_region_rows=len(precision_difference_rows), context_pairs=len(rank_rows),
        context_pair_reversals=sum(r['reverses'] for r in rank_rows), context_mixing_refused=True, context_groups=[6, 6])
    dump(args.out / 'summary.json', summary)
    dump(args.out / 'run_manifest.json', dict(python=platform.python_version(), command=sys.argv,
        input_sha256=frozen['input_sha256'], analysis_script_sha256=digest(Path(__file__)),
        engine_files_sha256={p.name: digest(p) for p in sorted((args.engine_src / 'radpareto').glob('*.py'))},
        results={p.name: dict(sha256=digest(p), bytes=p.stat().st_size) for p in sorted(args.out.iterdir()) if p.is_file() and p.name != 'run_manifest.json'},
        scope='Printed numerical summaries and specified computational decisions; no raw hardware, radiation inference or causal context comparison'))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
