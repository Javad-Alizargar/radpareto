"""Check certificate predictions against frozen direct endpoint decisions."""
import argparse
import hashlib
import importlib.util
import json
from fractions import Fraction
from pathlib import Path
import platform
import statistics
import sys
import time


def q(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")


def rows_from_case(case, source_hash, source_uri="cases.json", locator_prefix=None):
    context = {"baseline_id": "original-certificate-fixture", "device": "synthetic-device",
               "toolchain": "exact-rational-oracle", "tool_version": "1.0", "implementation": "synthetic-closed-boxes",
               "constraints_id": "certificate-domain-v1", "timing_corner": "nonphysical-cost-coordinates",
               "workload_id": "declared-additive-dilation", "source_kind": "synthetic_example"}
    return [{"id": f"r{i}", "design": case["case_id"], "method": f"alternative-{i}", "context": context.copy(),
             "metrics": {n: dict(v, unit="synthetic_cost", denominator="same_fixture_baseline", uncertainty_kind="bounded")
                         for n, v in row.items()},
             "provenance": {"source_uri": source_uri, "source_sha256": source_hash,
                            "locator": f"{case['case_id'] if locator_prefix is None else locator_prefix}/metrics/{i}",
                            "extraction": "Original constructed integer endpoints; direct rational oracle retained separately."},
             "protection": {"status": "unverified", "fault_model": "unverified", "scope": "synthetic costs only", "evidence_uri": "unverified"}}
            for i, row in enumerate(case["metrics"])]


def before_transition(certificate, t, inclusion_key):
    end = certificate["transition_t"]
    if end is None:
        return True
    threshold = q(end)
    if threshold < 0 or not isinstance(certificate[inclusion_key], bool):
        raise ValueError("Malformed finite certificate boundary")
    return t < threshold or (t == threshold and certificate[inclusion_key])


def predict(result, t, objective_names):
    pairs = sorted([[int(c["dominant_id"][1:]), int(c["dominated_id"][1:])]
                    for c in result["dominance_certificates"] if before_transition(c,t,"initial_relation_includes_boundary")])
    by_limit = {(c["record_id"], c["objective"]): c for c in result["constraint_certificates"]}
    if len(by_limit) != 2*len(objective_names):
        raise ValueError("Missing or duplicate per-limit certificate")
    classes = []
    for i in range(2):
        per_limit = {}
        for name in objective_names:
            c = by_limit[(f"r{i}",name)]
            per_limit[name] = c["initial_status"] if before_transition(c,t,"initial_status_includes_boundary") else c["status_after_transition"]
        status = ("definitely_infeasible" if "definitely_infeasible" in per_limit.values() else
                  "uncertain" if "uncertain" in per_limit.values() else "definitely_feasible")
        classes.append({"status": status, "per_limit": per_limit})
    return pairs, classes


def run(args):
    sys.path.insert(0, str(args.engine_root.resolve()/"src"))
    from radpareto import __version__
    if args.module:
        spec = importlib.util.spec_from_file_location("evaluated_stability", args.module.resolve())
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        implementation = args.module.resolve()
        stability = module.stability
    else:
        from radpareto.stability import stability
        implementation = args.engine_root.resolve()/"src/radpareto/stability.py"
    if args.output.exists():
        raise SystemExit("Refusing to overwrite earlier certificate evaluation")
    args.output.mkdir(parents=True)
    cases_path, expected_path = args.oracle/"cases.json", args.oracle/"expected.json"
    freeze = json.loads((args.oracle/"freeze.json").read_text(encoding="utf-8"))
    for path in (cases_path,expected_path):
        if hashlib.sha256(path.read_bytes()).hexdigest() != freeze["hashes"][path.name]:
            raise ValueError("Frozen oracle hash mismatch: "+path.name)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    expected = {r["case_id"]:r["expected"] for r in json.loads(expected_path.read_text(encoding="utf-8"))}
    results, failures, checked = [], [], 0
    for case in cases:
        records = rows_from_case(case,freeze["hashes"]["cases.json"])
        original = json.dumps(records,sort_keys=True)
        actual = stability(records,scales=case["scales"],limits=case["limits"])
        if actual["status"] != "accepted":
            failures.append({"case_id":case["case_id"],"error":"unexpected_refusal","result":actual})
            continue
        if json.dumps(records,sort_keys=True) != original:
            failures.append({"case_id":case["case_id"],"error":"input_mutation"})
        correct = 0
        for row in expected[case["case_id"]]:
            t = q(row["t"])
            pairs, classes = predict(actual,t,sorted(case["limits"]))
            checked += 1
            if pairs == row["certain_dominance_pairs"] and classes == row["classes"]:
                correct += 1
            else:
                failures.append({"case_id":case["case_id"],"t":row["t"],"actual_pairs":pairs,
                                 "actual_classes":classes,"expected":row})
        results.append({"case_id":case["case_id"],"checked":len(expected[case["case_id"]]),"correct":correct,
                        "dominance_certificates":actual["dominance_certificates"],"constraint_certificates":actual["constraint_certificates"]})
    summary = {"software_version":__version__,"cases":len(cases),"case_probe_decisions":checked,
               "matching_decisions":sum(r["correct"] for r in results),"failures":len(failures),
               "oracle_hashes":freeze["hashes"],"implementation_sha256":hashlib.sha256(implementation.read_bytes()).hexdigest(),
               "evaluator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "python":platform.python_version(),"platform":platform.platform(),
               "scope":"Exact predictions vs a frozen finite endpoint grid; dependent constructed cases, no arbitrary-input proof"}
    save(args.output/"summary.json",summary); save(args.output/"case_certificates.json",results); save(args.output/"failures.json",failures)
    if args.performance:
        observations, timings, inputs = [], [], []
        for n in (8,32,128):
            case = {"case_id":f"timing-chain-{n}","metrics":[{"cost_0":{"lower":10+2*i,"value":10+2*i,"upper":10+2*i},
                     "cost_1":{"lower":20+3*i,"value":20+3*i,"upper":20+3*i}} for i in range(n)]}
            encoded = json.dumps(case,sort_keys=True).encode()
            digest = hashlib.sha256(encoded).hexdigest()
            source_name = f"timing_source_{n}.json"
            (args.output/source_name).write_bytes(encoded)
            records = rows_from_case(case,digest,source_name,"")
            scales, limits = {"cost_0":1,"cost_1":1},{"cost_0":100,"cost_1":200}
            inputs.append({"records":n,"source":case,"source_sha256":digest,"scales":scales,"limits":limits})
            for _ in range(2):
                result = stability(records,scales=scales,limits=limits)
            times = []
            for repeat in range(7):
                start = time.perf_counter_ns()
                result = stability(records,scales=scales,limits=limits)
                elapsed = time.perf_counter_ns()-start
                if result["status"] != "accepted" or len(result["dominance_certificates"]) != n*(n-1)//2:
                    raise AssertionError("Unexpected certificate workload result")
                times.append(elapsed/1e6)
                observations.append({"records":n,"repeat":repeat,"elapsed_ns":elapsed,"elapsed_ms":elapsed/1e6})
            timings.append({"records":n,"median_ms":statistics.median(times),"min_ms":min(times),"max_ms":max(times),
                            "pair_certificates":len(result["dominance_certificates"]),
                            "compact_json_bytes":len(json.dumps(result,separators=(",",":"),sort_keys=True).encode())})
        save(args.output/"timing_inputs.json",inputs)
        save(args.output/"timing.json",{"summary":timings,"observations":observations,"warmups":2,"repeats":7,
             "python":platform.python_version(),"platform":platform.platform(),"processor":platform.processor(),
             "included":"Complete stability API including eligibility/comparison and rational certificates",
             "excluded":"Startup/imports,input creation,JSON serialization; output bytes measured separately",
             "implementation_sha256":summary["implementation_sha256"]})
    print(json.dumps(summary,indent=2))
    return int(bool(failures))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--engine-root",type=Path,required=True)
    parser.add_argument("--oracle",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--module",type=Path,help="Optional explicitly selected local candidate implementation")
    parser.add_argument("--performance",action="store_true")
    raise SystemExit(run(parser.parse_args()))
