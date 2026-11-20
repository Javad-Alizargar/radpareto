"""Freeze and run a bounded mutation study of copied production modules.

Only standard-library Python is required. Nothing writes to --repo. Freeze and
run are separate commands, and a run rejects any hashed input/source drift.
"""
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import unittest


HERE = Path(__file__).resolve().parent


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def operators():
    # Each mutation is a single exact, unique anchor replacement. The witnesses
    # are diagnostic inputs, not tests added to the scored validation families.
    return [
        ("M01", "Ties incorrectly dominate", "compare.py",
         "and any(v < w for v, w in zip(x, y))", "and any(v <= w for v, w in zip(x, y))", "ties"),
        ("M02", "Weak dominance requires every coordinate strict", "compare.py",
         "return all(v <= w for v, w in zip(x, y))", "return all(v < w for v, w in zip(x, y))", "weak"),
        ("M03", "Context mismatch guard disabled", "compare.py",
         'if r["context"][key] != ref["context"][key]:', 'if False and r["context"][key] != ref["context"][key]:', "context"),
        ("M04", "Certain dominance substitutes nominal for lower bound", "compare.py",
         'y = [b["metrics"][n]["lower" if box else "value"] for n in names]',
         'y = [b["metrics"][n]["value"] for n in names]', "box_lower"),
        ("M05", "Feasible upper-budget equality excluded", "compare.py",
         'r["metrics"][n]["upper"] <= bound', 'r["metrics"][n]["upper"] < bound', "feasible_equal"),
        ("M06", "Infeasible lower-budget equality included", "compare.py",
         'r["metrics"][n]["lower"] > bound', 'r["metrics"][n]["lower"] >= bound', "infeasible_equal"),
        ("M07", "Two moving endpoints lose factor two", "stability.py",
         'gaps[n]/(2*scale[n])', 'gaps[n]/scale[n]', "factor_two"),
        ("M08", "Dominance endpoint strictness lost", "stability.py",
         'any(gaps[n]-2*scale[n]*threshold > 0 for n in names)',
         'any(gaps[n]-2*scale[n]*threshold >= 0 for n in names)', "inclusion"),
        ("M09", "Zero-scale objectives enter division", "stability.py",
         'for n in names if scale[n] > 0}', 'for n in names if scale[n] >= 0}', "zero_scale"),
        ("M10", "Integer lower endpoints coerced through float", "stability.py",
         'Fraction(r["metrics"][n]["lower"])', 'Fraction(float(r["metrics"][n]["lower"]))', "precision"),
        ("M11", "Infeasible threshold uses upper endpoint", "stability.py",
         '(lower[rid][name]-limit)/scale[name], False', '(upper[rid][name]-limit)/scale[name], False', "constraint_lower"),
        ("M12", "Record-cap off-by-one rejects 128", "stability.py",
         'len(records) > MAX_STABILITY_RECORDS', 'len(records) >= MAX_STABILITY_RECORDS', "record_cap"),
    ]


def freeze(repo, target):
    if target.exists():
        raise SystemExit("Freeze directory exists; preserving it")
    target.mkdir(parents=True)
    frozen = target / "frozen"
    frozen.mkdir()
    shutil.copy2(HERE / "protocol.json", frozen / "protocol.json")
    shutil.copy2(Path(__file__), frozen / "run_mutation.py")
    for relative in ("scripts/evaluate_properties.py", "scripts/evaluate_certificates.py", "tests/test_stability.py",
                     "benchmarks/properties/cases.json", "benchmarks/properties/source_records.json",
                     "benchmarks/properties/response_surface_source.json", "benchmarks/properties/freeze.json",
                     "benchmarks/certificates/cases.json", "benchmarks/certificates/expected.json",
                     "benchmarks/certificates/freeze.json"):
        destination = frozen / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / relative, destination)
    variants = [{"id": "CONTROL", "label": "Unmodified production", "module": None, "witness": None}]
    variants.extend({"id": mid, "label": label, "module": module, "before": before, "after": after, "witness": witness}
                    for mid, label, module, before, after, witness in operators())
    for variant in variants:
        destination = target / "variants" / variant["id"] / "src" / "radpareto"
        destination.mkdir(parents=True)
        for source in sorted((repo / "src/radpareto").glob("*.py")):
            shutil.copy2(source, destination / source.name)
        if variant["module"]:
            path = destination / variant["module"]
            source = path.read_text(encoding="utf-8")
            if source.count(variant["before"]) != 1:
                raise ValueError("Non-unique mutation anchor: " + variant["id"])
            changed = source.replace(variant["before"], variant["after"])
            compile(changed, str(path), "exec")
            path.write_text(changed, encoding="utf-8", newline="\n")
            variant["patch"] = {"source_sha256": sha(repo / "src/radpareto" / variant["module"]),
                                "mutant_sha256": sha(path)}
    save(frozen / "operators.json", variants)
    # A concrete, reviewable diagnostic input is frozen for each mutant.
    tests = load_module_for_freeze(repo, frozen / "tests/test_stability.py")
    for variant in variants[1:]:
        save(frozen / (variant["id"] + "_witness.json"), make_witness(variant["witness"], tests))
    manifest = {"frozen_utc": utc(), "study_id": "bounded-source-mutation-v1", "variants": len(variants)-1,
                "production_hashes": {p.name: sha(p) for p in sorted((repo / "src/radpareto").glob("*.py"))},
                "files": {str(p.relative_to(target)).replace("\\", "/"): sha(p)
                          for p in sorted(target.rglob("*")) if p.is_file() and "__pycache__" not in p.parts},
                "freeze_scope": "Local immutable manifest before any mutant evaluation; investigator knows source/tests"}
    save(target / "freeze.json", manifest)
    print(json.dumps({"freeze": str(target), "files": len(manifest["files"]), "frozen_utc": manifest["frozen_utc"]}))


def load_module_for_freeze(repo, path):
    # Importing definitions only; no test case or production function executes.
    sys.path.insert(0, str(repo / "src"))
    return load_module("witness_record_builders", path)


def make_witness(name, tests):
    p, r = tests.point, tests.record
    cases = {
        "ties": ([p("A", 1), p("B", 1)], {}, "compare"),
        "weak": ([p("A", 1, 1), p("B", 1, 2)], {}, "compare"),
        "context": ([p("A", 1), p("B", 2)], {}, "compare"),
        "box_lower": ([p("A", 2), r("B", {"cost_0": (1, 4)})], {}, "compare"),
        "feasible_equal": ([p("A", 1)], {"limits": {"cost_0": 1}}, "compare"),
        "infeasible_equal": ([p("A", 1)], {"limits": {"cost_0": 1}}, "compare"),
        "factor_two": ([p("A", 1), p("B", 3)], {"scales": {"cost_0": 1}}, "stability"),
        "inclusion": ([p("A", 1), p("B", 3)], {"scales": {"cost_0": 1}}, "stability"),
        "zero_scale": ([p("A", 1), p("B", 3)], {"scales": {"cost_0": 0}}, "stability"),
        "precision": ([p("A", 2**53+1), p("B", 2**53+3)], {"scales": {"cost_0": 1}}, "stability"),
        "constraint_lower": ([r("A", {"cost_0": (2, 4)})], {"scales": {"cost_0": 1}, "limits": {"cost_0": 1}}, "stability"),
        "record_cap": ([p(str(i), 1) for i in range(128)], {"scales": {"cost_0": 0}}, "stability"),
    }
    records, kwargs, api = cases[name]
    if name == "context":
        records[1]["context"]["device"] = "different"
    if name == "box_lower":
        records[1]["metrics"]["cost_0"]["value"] = 3
    return {"name": name, "api": api, "records": records, "kwargs": kwargs,
            "purpose": "Non-equivalence diagnostic excluded from all detection scores"}


def verify(target):
    manifest = json.loads((target / "freeze.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        if sha(target / relative) != expected:
            raise ValueError("Frozen file drift: " + relative)
    if sha(Path(__file__)) != sha(target / "frozen/run_mutation.py"):
        raise ValueError("Runner differs from frozen runner")
    return manifest


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def family_result(planned, checked, mismatch=0, errors=0, unassessed=0, reason=None):
    return {"planned": planned, "checked": checked, "mismatches": mismatch,
            "runtime_error_cases": errors, "unassessed": unassessed,
            "detected": bool(mismatch or errors), "not_assessed_reason": reason}


def evaluate_certificates(target, output):
    frozen = target / "frozen"
    helper = load_module("frozen_certificate_helpers", frozen / "scripts/evaluate_certificates.py")
    from radpareto.stability import stability
    cases_path = frozen / "benchmarks/certificates/cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    expected = {r["case_id"]: r["expected"] for r in json.loads((frozen / "benchmarks/certificates/expected.json").read_text(encoding="utf-8"))}
    case_rows, first_examples = [], []
    for case in cases:
        cid = case["case_id"]
        probes = expected[cid]
        checked = mismatches = errors = 0
        try:
            rows = helper.rows_from_case(case, sha(cases_path))
            original = deepcopy(rows)
            actual = stability(rows, scales=case["scales"], limits=case["limits"])
            if actual["status"] != "accepted" or rows != original:
                raise ValueError("Unexpected refusal or input mutation: " + str(actual))
            for probe in probes:
                pairs, classes = helper.predict(actual, helper.q(probe["t"]), sorted(case["limits"]))
                checked += 1
                if pairs != probe["certain_dominance_pairs"] or classes != probe["classes"]:
                    mismatches += 1
                    if mismatches == 1:
                        first_examples.append({"case_id": cid, "input": case, "probe": probe,
                                               "actual_pairs": pairs, "actual_classes": classes,
                                               "certificates": {k: actual[k] for k in ("dominance_certificates", "constraint_certificates")}})
        except Exception:
            errors = 1
            first_examples.append({"case_id": cid, "input": case, "exception": traceback.format_exc()})
        case_rows.append({"case_id": cid, "layout": case["layout"], "planned": len(probes), "checked": checked,
                          "mismatches": mismatches, "error_cases": errors, "unassessed": len(probes)-checked})
    write_csv(output / "certificate_case_counts.csv", case_rows)
    save(output / "certificate_first_examples.json", first_examples)
    return family_result(sum(r["planned"] for r in case_rows), sum(r["checked"] for r in case_rows),
                         sum(r["mismatches"] for r in case_rows), sum(r["error_cases"] for r in case_rows),
                         sum(r["unassessed"] for r in case_rows))


def evaluate_unit(target, output):
    module = load_module("frozen_test_stability", target / "frozen/tests/test_stability.py")
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (output / "targeted_stability.log").write_text(stream.getvalue(), encoding="utf-8")
    save(output / "targeted_stability_failures.json", {"failures": [(t.id(), trace) for t, trace in result.failures],
                                                       "errors": [(t.id(), trace) for t, trace in result.errors]})
    return family_result(result.testsRun, result.testsRun, len(result.failures), len(result.errors))


def evaluate_properties(target, engine, output):
    helper = load_module("frozen_property_evaluator", target / "frozen/scripts/evaluate_properties.py")
    args = argparse.Namespace(engine_root=engine, cases=target / "frozen/benchmarks/properties/cases.json",
                              output=output / "properties")
    helper.evaluate(args)
    summary = json.loads((args.output / "summary.json").read_text(encoding="utf-8"))
    by_property = {name: family_result(v["checked"], v["checked"], v["checked"]-v["passed"])
                   for name, v in summary["by_property"].items()}
    return {"metamorphic": family_result(summary["property_instances"], summary["property_instances"],
                                        summary["property_instances"]-summary["property_passes"]),
            "quarter_grid": family_result(summary["response_surface_cells"], summary["response_surface_cells"],
                                         summary["response_surface_cells"]-summary["response_surface_agreement"]),
            "input_nonmutation": family_result(summary["nonmutation_calls"], summary["nonmutation_calls"],
                                              summary["nonmutation_calls"]-summary["nonmutation_passes"]),
            "by_property": by_property}


def witness_outputs(target, variant, output):
    from radpareto.compare import compare
    from radpareto.stability import stability
    helper = load_module("witness_projection", target / "frozen/scripts/evaluate_properties.py")
    names = [v[0] for v in operators()] if variant["id"] == "CONTROL" else [variant["id"]]
    results = {}
    for mid in names:
        case = json.loads((target / "frozen" / (mid + "_witness.json")).read_text(encoding="utf-8"))
        try:
            result = {"compare": compare, "stability": stability}[case["api"]](case["records"], **case["kwargs"])
            if case["api"] == "compare":
                result = helper.projection(result)
            else:
                result = {k: result[k] for k in ("status", "reasons", "dominance_certificates", "constraint_certificates")}
            results[mid] = {"result": result}
        except Exception as exc:
            results[mid] = {"exception": type(exc).__name__, "message": str(exc)}
    save(output / "activation_witness_outputs.json", results)


def child(target, mid):
    verify(target)
    variant = next(v for v in json.loads((target / "frozen/operators.json").read_text(encoding="utf-8")) if v["id"] == mid)
    engine = target / "variants" / mid
    sys.path.insert(0, str(engine / "src"))
    output = target / "results" / mid
    output.mkdir(parents=True)
    started = utc()
    if variant["module"] == "stability.py":
        reason = "The family calls compare() only and cannot execute stability.py"
        result = {"metamorphic": family_result(720, 0, unassessed=720, reason=reason),
                  "quarter_grid": family_result(1625, 0, unassessed=1625, reason=reason), "by_property": {}}
    else:
        result = evaluate_properties(target, engine, output)
    result["certificate_grid"] = evaluate_certificates(target, output)
    result["targeted_stability"] = evaluate_unit(target, output)
    save(output / "family_summary.json", {"variant": variant, "started_utc": started, "finished_utc": utc(), "families": result})
    # Deliberately after the scored families, never included in the score.
    witness_outputs(target, variant, output)
    print(json.dumps({"variant": mid, "finished_utc": utc(), "families": result}, indent=2))


def run(target):
    manifest = verify(target)
    if (target / "results").exists():
        raise SystemExit("Results already exist; create a new freeze/run to preserve them")
    (target / "results").mkdir()
    variants = json.loads((target / "frozen/operators.json").read_text(encoding="utf-8"))
    commands = []
    for variant in variants:
        command = [sys.executable, str(target / "frozen/run_mutation.py"), "child", "--target", str(target), "--variant", variant["id"]]
        start = time.perf_counter()
        completed = subprocess.run(command, capture_output=True, text=True)
        elapsed = time.perf_counter()-start
        (target / "results" / (variant["id"] + ".stdout.log")).write_text(completed.stdout, encoding="utf-8")
        (target / "results" / (variant["id"] + ".stderr.log")).write_text(completed.stderr, encoding="utf-8")
        commands.append({"variant": variant["id"], "command": command, "returncode": completed.returncode, "elapsed_s": elapsed})
        save(target / "results/commands.json", commands)
        print(variant["id"], "exit", completed.returncode, "seconds", round(elapsed, 2), flush=True)
        if completed.returncode:
            raise SystemExit("Unexpected harness failure; preserve results and inspect " + variant["id"])
    family_names = ("metamorphic", "quarter_grid", "certificate_grid", "targeted_stability")
    all_results = [json.loads((target / "results" / v["id"] / "family_summary.json").read_text(encoding="utf-8")) for v in variants]
    if any(all_results[0]["families"][name]["detected"] for name in family_names):
        raise SystemExit("Control failed; inference blocked")
    witness_control = json.loads((target / "results/CONTROL/activation_witness_outputs.json").read_text(encoding="utf-8"))
    matrix, overview = [], []
    for result in all_results:
        mid = result["variant"]["id"]
        for name in family_names:
            matrix.append({"variant": mid, "label": result["variant"]["label"], "family": name, **result["families"][name]})
        if mid != "CONTROL":
            witness_mutant = json.loads((target / "results" / mid / "activation_witness_outputs.json").read_text(encoding="utf-8"))[mid]
            overview.append({"variant": mid, "label": result["variant"]["label"],
                             "detected_by_existing_families": any(result["families"][name]["detected"] for name in family_names),
                             "non_equivalence_witness_differs": witness_control[mid] != witness_mutant,
                             "detected_families": [name for name in family_names if result["families"][name]["detected"]]})
    write_csv(target / "results/detection_matrix.csv", matrix)
    save(target / "results/mutant_overview.json", overview)
    summary = {"finished_utc": utc(), "freeze_sha256": sha(target / "freeze.json"), "mutants": len(overview),
               "detected": sum(r["detected_by_existing_families"] for r in overview),
               "survivors": [r["variant"] for r in overview if not r["detected_by_existing_families"]],
               "diagnostically_non_equivalent": sum(r["non_equivalence_witness_differs"] for r in overview),
               "excluded_equivalent": 0, "control_all_families_pass": True,
               "by_family_detected_mutants": {name: sum(r["families"][name]["detected"] for r in all_results[1:]) for name in family_names},
               "python": platform.python_version(), "platform": platform.platform(),
               "scope": "Purposive source defects and selected dependent validation families; no population accuracy or arbitrary-input proof",
               "elapsed_s": sum(c["elapsed_s"] for c in commands),
               "input_hashes_verified": len(manifest["files"])}
    save(target / "results/summary.json", summary)
    save(target / "results/artifact_hashes.json", {str(p.relative_to(target)).replace("\\", "/"): sha(p)
                                                  for p in sorted((target / "results").rglob("*")) if p.is_file()})
    verify(target)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "run", "child", "verify"])
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--variant")
    args = parser.parse_args()
    args.target = args.target.resolve()
    if args.action == "freeze":
        freeze(args.repo.resolve(), args.target)
    elif args.action == "run":
        run(args.target)
    elif args.action == "child":
        child(args.target, args.variant)
    else:
        print(json.dumps({"verified_files": len(verify(args.target)["files"])}))
