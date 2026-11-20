"""Reproducible metamorphic checks and exact-quarter response-surface oracle."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys


def projection(result):
    return {"status": result["status"],
            "nominal_front": sorted(result.get("nominal_front", [])),
            "not_certainly_dominated": sorted(result.get("not_certainly_dominated", [])),
            "definitely_feasible_nominal_front": sorted(result.get("definitely_feasible_nominal_front", [])),
            "feasibility": result.get("feasibility", {}),
            "reason_codes": sorted({r["code"] for r in result.get("reasons", [])})}


def class_set(result, label):
    return {k for k, v in result["feasibility"].items() if v["status"] == label}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")


def evaluate(args):
    sys.path.insert(0, str(args.engine_root.resolve()/"src"))
    from radpareto.compare import compare
    from radpareto import __version__
    if args.output.exists():
        raise SystemExit("Output directory already exists; preserving prior results")
    args.output.mkdir(parents=True)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    mutations, outcomes, failures, records = [], [], [], []

    def run(case_id, variant, rows, limits):
        before = json.dumps(rows, sort_keys=True)
        result = compare(rows, limits=limits)
        unmodified = before == json.dumps(rows, sort_keys=True)
        mutations.append({"case_id": case_id, "variant": variant, "input_unchanged": unmodified})
        projected = projection(result)
        records.append({"case_id": case_id, "variant": variant, "limits": limits, "result": projected})
        if not unmodified:
            failures.append({"case_id": case_id, "variant": variant, "error": "input_mutation"})
        return projected

    for case in cases:
        cid, rows, limits = case["case_id"], case["document"]["records"], case["limits"]
        base = run(cid, "base", rows, limits)
        if base["status"] != "accepted":
            raise AssertionError(f"Base case unexpectedly refused: {cid}")
        variants = {}
        variants["permutation"] = (list(reversed(deepcopy(rows))), limits.copy())
        for variant in ("positive_scaling", "translation", "interval_widening"):
            changed = deepcopy(rows)
            new_limits = limits.copy()
            for j, name in enumerate(sorted(limits)):
                factor, shift = j+2, 7*(j+1)
                for r in changed:
                    metric = r["metrics"][name]
                    if variant == "positive_scaling":
                        for k in ("value", "lower", "upper"):
                            metric[k] *= factor
                        metric["unit"] = f"scaled_by_{factor}_synthetic_cost"
                    elif variant == "translation":
                        for k in ("value", "lower", "upper"):
                            metric[k] += shift
                    else:
                        metric["lower"] = max(0, metric["lower"]-4)
                        metric["upper"] += 4
                if variant == "positive_scaling":
                    new_limits[name] *= factor
                elif variant == "translation":
                    new_limits[name] += shift
            variants[variant] = (changed, new_limits)
        variants["limit_relaxation"] = (deepcopy(rows), {n: v+7 for n, v in limits.items()})
        changed = deepcopy(rows)
        changed[-1]["context"]["device"] = "different-synthetic-device"
        variants["context_mutation"] = (changed, limits.copy())
        for variant, (changed, new_limits) in variants.items():
            result = run(cid, variant, changed, new_limits)
            if variant in {"permutation", "positive_scaling", "translation"}:
                passed = result == base
                detail = "All projected decision sets, per-limit classes and eligibility preserved"
            elif variant == "interval_widening":
                passed = (result["status"] == "accepted" and result["nominal_front"] == base["nominal_front"] and
                          set(base["not_certainly_dominated"]) <= set(result["not_certainly_dominated"]) and
                          class_set(result, "definitely_feasible") <= class_set(base, "definitely_feasible") and
                          class_set(result, "definitely_infeasible") <= class_set(base, "definitely_infeasible"))
                detail = "Wider boxes cannot create certain dominance or enlarge either definite feasibility class"
            elif variant == "limit_relaxation":
                passed = (result["status"] == "accepted" and result["nominal_front"] == base["nominal_front"] and
                          result["not_certainly_dominated"] == base["not_certainly_dominated"] and
                          class_set(base, "definitely_feasible") <= class_set(result, "definitely_feasible") and
                          class_set(result, "definitely_infeasible") <= class_set(base, "definitely_infeasible"))
                detail = "Relaxed upper limits preserve fronts and change definite classes monotonically"
            else:
                passed = result["status"] == "refused" and "CONTEXT_MISMATCH" in result["reason_codes"]
                detail = "One incompatible device produces context refusal"
            outcomes.append({"case_id": cid, "layout": case["layout"], "records": case["record_count"],
                             "objectives": case["objective_count"], "property": variant,
                             "passed": passed, "interpretation": detail})
            if not passed:
                failures.append({"case_id": cid, "variant": variant, "base": base, "actual": result})

    surface, surface_errors = [], []
    template = deepcopy(cases[0]["document"]["records"][:3])
    surface_source_path = args.cases.parent / "response_surface_source.json"
    surface_source = json.loads(surface_source_path.read_text(encoding="utf-8"))
    surface_source_sha = hashlib.sha256(surface_source_path.read_bytes()).hexdigest()
    central = surface_source["central_coordinates"]
    assert surface_source["common_denominator"] == 4
    assert surface_source["dilation_numerator_range"] == [0, 24]
    assert surface_source["limit_numerator_range"] == [76, 140]
    for ti in range(25):
        for li in range(65):
            # Oracle works entirely in integers representing quarter units.
            limit4 = 76+li
            lower4 = [[max(0, v*4-ti) for v in row] for row in central]
            upper4 = [[v*4+ti for v in row] for row in central]
            expected_front = [f"r{i:02d}" for i in range(3) if not any(
                j != i and all(upper4[j][k] <= lower4[i][k] for k in range(2)) and
                any(upper4[j][k] < lower4[i][k] for k in range(2)) for j in range(3))]
            expected_classes = {f"r{i:02d}": ("definitely_infeasible" if lower4[i][0] > limit4 else
                                                  "definitely_feasible" if upper4[i][0] <= limit4 else "uncertain") for i in range(3)}
            rows = deepcopy(template)
            for i, r in enumerate(rows):
                for k in range(2):
                    r["metrics"][f"cost_{k}"].update(value=central[i][k], lower=lower4[i][k]/4, upper=upper4[i][k]/4)
                r["provenance"] = {"source_uri": "response_surface_source.json", "source_sha256": surface_source_sha,
                                   "locator": f"central_coordinates/{i}",
                                   "extraction": f"Original fixture, widened by {ti}/4; first-coordinate limit {limit4}/4; prescribed quarter-unit grid."}
            result = compare(rows, limits={"cost_0": limit4/4})
            actual_classes = {k: v["status"] for k, v in result.get("feasibility", {}).items()}
            ok = (result["status"] == "accepted" and sorted(result["not_certainly_dominated"]) == expected_front and
                  actual_classes == expected_classes)
            row = {"dilation": ti/4, "cost_0_limit": limit4/4, "retained_count": len(expected_front),
                   "definitely_feasible": list(expected_classes.values()).count("definitely_feasible"),
                   "uncertain": list(expected_classes.values()).count("uncertain"),
                   "definitely_infeasible": list(expected_classes.values()).count("definitely_infeasible"),
                   "oracle_agreement": ok}
            surface.append(row)
            if not ok:
                surface_errors.append({"coordinates": row, "actual": projection(result), "expected_classes": expected_classes})

    write_json(args.output/"projected_decisions.json", records)
    write_json(args.output/"nonmutation.json", mutations)
    write_json(args.output/"failures.json", {"properties": failures, "response_surface": surface_errors})
    for filename, rows in (("property_results.csv", outcomes), ("response_surface.csv", surface)):
        with (args.output/filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = {"software_version": __version__, "python": platform.python_version(), "platform": platform.platform(),
               "base_cases": len(cases), "property_instances": len(outcomes), "property_passes": sum(r["passed"] for r in outcomes),
               "by_property": {name: {"checked": sum(r["property"] == name for r in outcomes),
                                       "passed": sum(r["property"] == name and r["passed"] for r in outcomes)}
                               for name in sorted({r["property"] for r in outcomes})},
               "nonmutation_calls": len(mutations), "nonmutation_passes": sum(r["input_unchanged"] for r in mutations),
               "response_surface_cells": len(surface), "response_surface_agreement": sum(r["oracle_agreement"] for r in surface),
               "response_surface_class_totals": {k: sum(r[k] for r in surface) for k in ("definitely_feasible", "uncertain", "definitely_infeasible")},
               "response_surface_retained_counts": dict(Counter(r["retained_count"] for r in surface)),
               "case_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
               "response_surface_source_sha256": surface_source_sha,
               "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "engine_sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((args.engine_root/"src/radpareto").glob("*.py"))},
               "scope": "Dependent constructed properties and exact grid agreement, not population accuracy or empirical radiation uncertainty"}
    write_json(args.output/"summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 1 if failures or surface_errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(evaluate(parser.parse_args()))
