"""Matched original-scenario evaluation; no population or human-utility inference."""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(result):
    projection = {"status": result.get("status")}
    for key in ("nominal_front", "not_certainly_dominated", "definitely_feasible_nominal_front"):
        value = result.get(key)
        projection[key] = sorted(value) if isinstance(value, list) else value
    projection["feasibility"] = {
        key: val.get("status") if isinstance(val, dict) else val
        for key, val in (result.get("feasibility") or {}).items()
    }
    return projection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--engine-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--performance", action="store_true")
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new output directory; earlier results must be preserved")
    args.output.mkdir(parents=True)
    sys.path.insert(0, str(args.engine_root.resolve() / "src"))
    from radpareto import compare, validate_document, __version__
    from radpareto.validation import EvidenceError
    spec = importlib.util.spec_from_file_location("independent_reference", args.baseline)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)

    def product(document, **options):
        try:
            records = validate_document(document)
        except EvidenceError as exc:
            return {"status": "refused", "reasons": [exc.as_dict()]}
        return compare(records, **options)

    methods = {"radpareto": product,
               "checked_tabular": baseline.compare_document,
               "nominal_ablation": baseline.nominal_only_document}
    data = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    cases = data["cases"]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated case identifier")
    rows, details = [], []
    for case in cases:
        expected = canonical(case["expected"])
        scored = list(case["expected"]) if expected["status"] == "accepted" else ["status"]
        scored = [key for key in scored if key in expected]
        for name, method in methods.items():
            error = None
            try:
                result = method(copy.deepcopy(case["document"]), **case["options"])
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
                result = {"status": "error", "reasons": [error]}
            actual = canonical(result)
            mismatches = [key for key in scored if actual[key] != expected[key]]
            row = {"case_id": case["case_id"], "family": case["family"], "method": name,
                   "expected_status": expected["status"], "actual_status": actual["status"],
                   "status_correct": actual["status"] == expected["status"],
                   "full_decision_correct": not mismatches,
                   "unsafe_acceptance": expected["status"] == "refused" and actual["status"] == "accepted",
                   "false_refusal": expected["status"] == "accepted" and actual["status"] == "refused",
                   "unexpected_exception": error is not None,
                   "mismatched_fields": ";".join(mismatches)}
            rows.append(row)
            details.append(dict(row, expected=expected, actual=actual,
                                reasons=result.get("reasons", []), exception=error))
    with (args.output / "case_results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)
    totals = {}
    for method, entries in grouped.items():
        totals[method] = {"cases": len(entries), **{key: sum(r[key] for r in entries) for key in
            ("status_correct", "full_decision_correct", "unsafe_acceptance", "false_refusal", "unexpected_exception")}}
    report = {"scope": "constructed software-contract scenarios, not human utility or real-world error prevalence",
              "software_version": __version__, "case_count": len(cases),
              "expected_status_counts": dict(Counter(c["expected"]["status"] for c in cases)),
              "family_counts": dict(Counter(c["family"] for c in cases)), "methods": totals,
              "ablation_scoring_note": "Full-decision counts for nominal_ablation include deliberate absence of interval/feasibility outputs; they are capability-completeness counts, not a fair full-feature accuracy comparison. Interpret status and nominal results separately.",
              "hashes": {"cases": digest(args.cases), "baseline": digest(args.baseline),
                         "runner": digest(Path(__file__)),
                         "engine_sources": {p.name: digest(p) for p in sorted((args.engine_root/"src/radpareto").glob("*.py"))}},
              "environment": {"python": platform.python_version(), "platform": platform.platform(),
                              "processor": platform.processor(),
                              "pandas": importlib.metadata.version("pandas")}}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    (args.output / "decisions.json").write_text(json.dumps(details, indent=2)+"\n", encoding="utf-8")

    if args.performance:
        seed_record = next(c["document"]["records"][0] for c in cases if c["expected"]["status"] == "accepted")
        durations, summary = [], []
        for count in (8, 32, 128):
            # Deliberately all-trade-off synthetic costs, not a representative workload.
            points = [{"id": f"s{i:04d}", "cost_a": i+1, "cost_b": count-i} for i in range(count)]
            source = args.output / f"timing_source_{count}.json"
            source.write_text(json.dumps(points, indent=2)+"\n", encoding="utf-8")
            records = []
            for point in points:
                record = copy.deepcopy(seed_record)
                record.update(id=point["id"], design="original_synthetic_tradeoff", method="synthetic_method")
                record["context"]["source_kind"] = "synthetic_example"
                record["metrics"] = {key: {"value": point[key], "lower": point[key], "upper": point[key],
                    "unit": "synthetic_cost_units", "denominator": "absolute", "uncertainty_kind": "exact"}
                    for key in ("cost_a", "cost_b")}
                record["provenance"] = {"source_uri": source.name, "source_sha256": digest(source),
                    "locator": point["id"], "extraction": "original synthetic timing fixture"}
                records.append(record)
            document = {"schema_version": "1.0", "records": records}
            active = {key: methods[key] for key in ("radpareto", "checked_tabular")}
            reference = None
            for method in active.values():
                result = canonical(method(document))
                assert result["status"] == "accepted"
                assert len(result["nominal_front"]) == count
                if reference is not None:
                    assert result == reference, "Timing comparison requires matching decisions"
                reference = result
            for _ in range(2):
                for method in active.values():
                    method(document)
            for repeat in range(7):
                order = list(active) if repeat % 2 == 0 else list(reversed(active))
                for name in order:
                    start = time.perf_counter_ns()
                    active[name](document)
                    elapsed_ms = (time.perf_counter_ns()-start)/1e6
                    durations.append({"method": name, "records": count, "repeat": repeat+1,
                                      "elapsed_ms": elapsed_ms, "input_source_sha256": digest(source)})
            for name in active:
                values = [r["elapsed_ms"] for r in durations if r["method"] == name and r["records"] == count]
                summary.append({"method": name, "records": count, "repeats": len(values),
                                "median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values)})
        (args.output / "timing.json").write_text(json.dumps({
            "scope": "local warm in-process complete validation and comparison; imports, startup and JSON disk loading excluded",
            "input_design": "all-trade-off synthetic records; not representative workload sampling",
            "raw": durations, "summary": summary}, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report["methods"], indent=2))


if __name__ == "__main__":
    main()
