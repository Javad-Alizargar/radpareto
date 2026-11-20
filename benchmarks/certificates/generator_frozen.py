"""Freeze exact endpoint decisions without reading the new certificate module."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime, timezone
import hashlib
import json
import random

DEST = Path(__file__).resolve().parent / "certificate_oracle"


def rational(x):
    return {"numerator": x.numerator, "denominator": x.denominator}


def main():
    if DEST.exists():
        raise SystemExit("Refusing to overwrite frozen certificate oracle")
    DEST.mkdir()
    cases = []
    for m in (1, 2, 3):
        for i in range(120):
            rng = random.Random(f"20261120-certificate-m{m}-case{i}")
            rows = [{}, {}]
            scales, limits = {}, {}
            for j in range(m):
                name = f"cost_{j}"
                if i % 4 == 0:  # nested-free separated boxes, including touching
                    la = rng.randint(0, 4); ua = la+rng.randint(0, 3)
                    lb = ua+rng.randint(0, 4); ub = lb+rng.randint(0, 3)
                elif i % 4 == 1:  # identical points: strictness must prevent dominance
                    la = ua = lb = ub = rng.randint(0, 10)
                elif i % 4 == 2:  # overlapping intervals
                    la = rng.randint(0, 5); ua = la+4
                    lb = la+1; ub = ua+2
                else:
                    la = rng.randint(0, 10); ua = la+rng.randint(0, 4)
                    lb = rng.randint(0, 10); ub = lb+rng.randint(0, 4)
                rows[0][name] = {"lower": la, "value": (la+ua)//2, "upper": ua}
                rows[1][name] = {"lower": lb, "value": (lb+ub)//2, "upper": ub}
                scales[name] = rng.randint(0, 3)
                limits[name] = rng.randint(0, 20)
            cases.append({"case_id": f"m{m}-case{i:03d}", "layout": ("separated", "identical", "overlap", "mixed")[i % 4],
                          "metrics": rows, "scales": scales, "limits": limits})
    # Fixed rational probes include all possible finite transition values for
    # these integer domains, their adjacent midpoints and a trailing value.
    endpoints = sorted({Fraction(k, d) for k in range(25) for d in range(1, 7)})
    probes = sorted(set(endpoints) | {(a+b)/2 for a, b in zip(endpoints, endpoints[1:])} | {Fraction(25)})
    expected = []
    for case in cases:
        rows = []
        for t in probes:
            lower = [{n: max(Fraction(0), Fraction(v["lower"])-t*case["scales"][n]) for n, v in r.items()}
                     for r in case["metrics"]]
            upper = [{n: Fraction(v["upper"])+t*case["scales"][n] for n, v in r.items()} for r in case["metrics"]]
            dominates = []
            for a, b in ((0, 1), (1, 0)):
                if all(upper[a][n] <= lower[b][n] for n in case["scales"]) and any(
                        upper[a][n] < lower[b][n] for n in case["scales"]):
                    dominates.append([a, b])
            classes = []
            for i in range(2):
                per_limit = {n: ("definitely_infeasible" if lower[i][n] > limit else
                                 "definitely_feasible" if upper[i][n] <= limit else "uncertain")
                             for n, limit in case["limits"].items()}
                overall = ("definitely_infeasible" if "definitely_infeasible" in per_limit.values() else
                           "uncertain" if "uncertain" in per_limit.values() else "definitely_feasible")
                classes.append({"status": overall, "per_limit": per_limit})
            rows.append({"t": rational(t), "certain_dominance_pairs": dominates, "classes": classes})
        expected.append({"case_id": case["case_id"], "expected": rows})
    for name, data in (("cases.json", cases), ("expected.json", expected)):
        (DEST/name).write_text(json.dumps(data, separators=(",", ":"))+"\n", encoding="utf-8")
    freeze = {"frozen_utc": datetime.now(timezone.utc).isoformat(), "cases": len(cases),
              "probes_per_case": len(probes), "case_probe_decisions": len(cases)*len(probes),
              "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "hashes": {n: hashlib.sha256((DEST/n).read_bytes()).hexdigest() for n in ("cases.json", "expected.json")},
              "oracle_method": "Direct exact-rational endpoint inequalities at a fixed grid; no breakpoint formula or certificate implementation inspected",
              "scope": "Constructed finite-domain check, not formal proof for arbitrary inputs; includes dependent cases/probes"}
    (DEST/"freeze.json").write_text(json.dumps(freeze, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in freeze.items() if k != "hashes"}, indent=2))


if __name__ == "__main__":
    main()
