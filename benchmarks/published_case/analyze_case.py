"""Reproduce the attributed Ma et al. Table 9/10 cost-only case with RadPareto.

python analyze_case.py --engine-src /path/to/radpareto/src --out run_001
Outputs are never overwritten. Source inputs must match source_freeze.json.
No raw P&R runs, radiation bounds, or protection claims are manufactured.
"""
import argparse
import copy
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write('\n')


def csv_out(path, rows):
    with path.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fraction_number(r):
    return None if r is None else float(Fraction(int(r['numerator']), int(r['denominator'])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine-src', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    freeze = json.loads((here/'source_freeze.json').read_text(encoding='utf-8'))
    for name, info in freeze['files'].items():
        assert digest(here/name) == info['sha256'], f'Frozen input changed: {name}'
    rows = json.loads((here/'source_exact.json').read_text(encoding='utf-8'))['records']
    metadata = json.loads((here/'source_metadata.json').read_text(encoding='utf-8'))
    with (here/'source_tables.csv').open(encoding='utf-8', newline='') as f:
        assert list(csv.DictReader(f)) == rows
    sys.path.insert(0, str(args.engine_src.resolve()))
    from radpareto.compare import compare
    from radpareto.stability import stability
    from radpareto.validation import validate_document
    from radpareto.units import period_ns_from_mhz
    args.out.mkdir(parents=True, exist_ok=False)
    records, derived = [], []
    for row in rows:
        # Source table arithmetic provides meaningful independent consistency checks.
        assert int(row['dfn1c1']) + int(row['comb_versatiles']) - int(row['public_versatiles']) == int(row['structure_only_versatiles'])
        assert int(row['structure_only_versatiles']) == 486*int(row['versatiles_per_bit'])
        assert row['versatiles_per_bit'] == row['model_versatiles_per_bit']
        ratio = Decimal(row['versatiles_per_bit'])/Decimal(11)
        assert ratio.quantize(Decimal('0.01')) == Decimal(row['resource_ratio'])
        with localcontext() as ctx:
            ctx.prec = 40
            per = Decimal(1000)/Decimal(row['fmax_mean_mhz'])
            lo = Decimal(1000)/Decimal(row['fmax_max_mhz'])
            hi = Decimal(1000)/Decimal(row['fmax_min_mhz'])
        assert lo <= per <= hi
        cells = int(row['versatiles_per_bit'])
        records.append({
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
                'period_ns': {'value': period_ns_from_mhz(row['fmax_mean_mhz']), 'lower': period_ns_from_mhz(row['fmax_max_mhz']), 'upper': period_ns_from_mhz(row['fmax_min_mhz']), 'unit': 'ns', 'denominator': 'clock_cycle_reciprocal_of_standalone_fmax', 'uncertainty_kind': 'bounded'}},
            'provenance': {'source_uri': 'benchmarks/published_case/source_tables.csv', 'source_sha256': digest(here/'source_tables.csv'),
                'locator': f"Tables 9 and 10, row {row['structure']}; SHA-256 identifies source_tables.csv original transcription, not publisher bytes",
                'extraction': 'Cell-checked original transcription; period=1000/mean MHz; closed box uses reversed reciprocal observed three-run min-max endpoints; exact source decimals in source_exact.json'},
            'protection': {'status': 'unverified', 'fault_model': 'not_assessed', 'scope': 'cost_only_no_protection_equivalence', 'evidence_uri': metadata['source']['url']}})
        derived.append({'structure': row['structure'], 'cells': cells,
            'fmax_mean_mhz': row['fmax_mean_mhz'], 'fmax_min_mhz': row['fmax_min_mhz'], 'fmax_max_mhz': row['fmax_max_mhz'],
            'period_ns': str(per), 'period_lower_ns': str(lo), 'period_upper_ns': str(hi),
            'source_critical_delay_mean_ns': row['critical_path_delay_mean_ns'],
            'period_minus_source_critical_delay_ns': str(per-Decimal(row['critical_path_delay_mean_ns'])),
            'nominal_front': False, 'not_certainly_dominated': False})
    validate_document({'schema_version': '1.0', 'records': records})
    base = compare(records)
    assert base['status'] == 'accepted', base['reasons']
    assert base['nominal_front'] == ['BL-DFF']
    assert base['not_certainly_dominated'] == ['BL-DFF']
    for row in derived:
        row['nominal_front'] = row['structure'] in base['nominal_front']
        row['not_certainly_dominated'] = row['structure'] in base['not_certainly_dominated']
    scopes = {'all_six': records, 'tmr_based_five': records[1:], 'set_suppression_architectures_four': records[2:]}
    scope_results = {name: compare(rs) for name, rs in scopes.items()}
    assert scope_results['set_suppression_architectures_four']['nominal_front'] == ['DF-TMR-DFF-1.28', 'DCLR-TMR-DFF']
    rejection = compare(records, require_verified_protection=True)
    assert rejection['status'] == 'refused'
    limits_grid, outcomes = [], []
    for cells_cap in (20, 30, 40):
        for frequency in (30, 32, 40, 50):
            limits = {'cells': cells_cap, 'period_ns': period_ns_from_mhz(frequency)}
            result = compare(records, limits=limits)
            assert result['status'] == 'accepted'
            limits_grid.append({'cells_cap': cells_cap, 'frequency_requirement_mhz': frequency, 'result': result})
            for record in records:
                state = result['feasibility'][record['id']]
                outcomes.append({'structure': record['id'], 'cells_cap': cells_cap,
                    'frequency_requirement_mhz': frequency, 'period_cap_ns': limits['period_ns'],
                    'overall_status': state['status'], 'cells_status': state['per_limit']['cells'],
                    'timing_status': state['per_limit']['period_ns'],
                    'on_definitely_feasible_cost_front': record['id'] in result['definitely_feasible_nominal_front']})
    scales = {'cells': 1, 'period_ns': 1}
    selected_limits = {'cells': 40, 'period_ns': period_ns_from_mhz(30)}
    cert = stability(records, scales=scales, limits=selected_limits)
    assert cert['status'] == 'accepted'
    dominance_rows = [{'dominant_id': c['dominant_id'], 'dominated_id': c['dominated_id'],
        'transition_t_decimal': fraction_number(c['transition_t']),
        'boundary_included': c['initial_relation_includes_boundary'],
        'limiting_objectives': '|'.join(c['limiting_objectives']),
        'exact_numerator': c['transition_t']['numerator'] if c['transition_t'] else '',
        'exact_denominator': c['transition_t']['denominator'] if c['transition_t'] else ''} for c in cert['dominance_certificates']]
    constraint_rows = [{'structure': c['record_id'], 'objective': c['objective'], 'initial_status': c['initial_status'],
        'transition_t_decimal': fraction_number(c['transition_t']), 'boundary_included': c['initial_status_includes_boundary'],
        'after': c['status_after_transition']} for c in cert['constraint_certificates']]
    sweeps = []
    for t in metadata['analysis_plan_before_run']['evaluation_t_grid']:
        widened = copy.deepcopy(records)
        for record in widened:
            for name, metric in record['metrics'].items():
                metric['lower'] = max(0, metric['lower']-t*scales[name])
                metric['upper'] += t*scales[name]
                metric['uncertainty_kind'] = 'bounded'
        result = compare(widened, limits=selected_limits)
        assert result['status'] == 'accepted'
        for record in records:
            rid = record['id']
            sweeps.append({'t': t, 'structure': rid,
                'not_certainly_dominated': rid in result['not_certainly_dominated'],
                'feasibility': result['feasibility'][rid]['status']})
    # Scalar independent arithmetic audit of each exact dominance threshold.
    by_id = {r['id']: r for r in records}
    max_threshold_error = 0.0
    for c in cert['dominance_certificates']:
        a, b = by_id[c['dominant_id']], by_id[c['dominated_id']]
        expected = min((b['metrics'][n]['lower']-a['metrics'][n]['upper'])/(2*scales[n]) for n in scales)
        error = abs(expected-fraction_number(c['transition_t']))
        max_threshold_error = max(error, max_threshold_error)
        assert error <= 1e-12
    dump(args.out/'records.json', {'schema_version': '1.0', 'records': records})
    dump(args.out/'comparison.json', base)
    dump(args.out/'scope_comparisons.json', scope_results)
    dump(args.out/'protection_required_refusal.json', rejection)
    dump(args.out/'budget_grid.json', limits_grid)
    dump(args.out/'stability.json', cert)
    csv_out(args.out/'derived_costs.csv', derived)
    csv_out(args.out/'budget_outcomes.csv', outcomes)
    decision_rows = []
    for record in records:
        rid = record['id']
        row = {'structure': rid, 'cells': record['metrics']['cells']['value'],
            'period_ns': record['metrics']['period_ns']['value'],
            'all_six_cost_front': rid in base['nominal_front'],
            'set_architecture_scope_cost_front': rid in scope_results['set_suppression_architectures_four']['nominal_front']}
        for cells_cap, frequency in ((40, 30), (40, 32), (30, 40), (40, 40), (40, 50)):
            selected = next(x for x in outcomes if x['structure'] == rid and x['cells_cap'] == cells_cap and x['frequency_requirement_mhz'] == frequency)
            row[f'cap{cells_cap}_freq{frequency}mhz'] = selected['overall_status']
        relevant = [x for x in constraint_rows if x['structure'] == rid and x['transition_t_decimal'] is not None]
        first = min(relevant, key=lambda x: x['transition_t_decimal'])
        row['first_feasibility_transition_t_cap40_freq30'] = first['transition_t_decimal']
        row['limiting_objective'] = first['objective']
        decision_rows.append(row)
    csv_out(args.out/'design_selection_table.csv', decision_rows)
    grid_summary = []
    for item in limits_grid:
        states = item['result']['feasibility']
        row = {k: item[k] for k in ('cells_cap', 'frequency_requirement_mhz')}
        for state in ('definitely_feasible', 'uncertain', 'definitely_infeasible'):
            ids = [rid for rid, v in states.items() if v['status'] == state]
            row[state+'_n'] = len(ids)
            row[state+'_ids'] = '|'.join(ids)
        grid_summary.append(row)
    csv_out(args.out/'budget_summary.csv', grid_summary)
    csv_out(args.out/'dominance_transitions.csv', dominance_rows)
    csv_out(args.out/'constraint_transitions.csv', constraint_rows)
    csv_out(args.out/'widening_grid.csv', sweeps)
    dump(args.out/'run_manifest.json', {
        'python': platform.python_version(), 'command': sys.argv,
        'source_files': freeze['files'], 'analysis_script_sha256': digest(Path(__file__)),
        'engine_files': {p.name: digest(p) for p in sorted((args.engine_src/'radpareto').glob('*.py'))},
        'checks': {'source_hashes_match': True, 'csv_equals_exact_json': True,
            'resource_arithmetic_all_six': True, 'rounded_resource_ratios_all_six': True,
            'comparison_accepted': True, 'protection_aware_comparison_refused': True,
            'independent_dominance_threshold_max_error': max_threshold_error, 'tolerance': 1e-12},
        'limitations': metadata['verification']['unresolved'],
        'interval_semantics': 'bounded is a computational closed-box representation of observed three-run range only; no coverage guarantee',
        'results': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(args.out.iterdir()) if p.is_file() and p.name != 'run_manifest.json'}})
    print(json.dumps({'status': 'complete_with_limitations', 'output': str(args.out),
        'nominal_front': base['nominal_front'], 'interval_screen': base['not_certainly_dominated'],
        'dominance_certificates': len(dominance_rows), 'budget_rows': len(outcomes)}, indent=2))


if __name__ == '__main__':
    main()
