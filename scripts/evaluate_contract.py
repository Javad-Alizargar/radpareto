"""Independent hand-specified contracts and enumeration oracle for the alpha."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import random
from radpareto import compare, validate_document

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT
data = json.loads((PUBLIC/"examples/rounded_costs.json").read_text())
rows = validate_document(data)
checks = []


def check(name, passed):
    checks.append({"case": name, "passed": bool(passed)})
    if not passed:
        raise AssertionError(name)


result = compare(rows, limits={"area_ratio": 2.02})
check("nominal_front_hand_expected", set(result["nominal_front"]) == {"alpha", "gamma"})
check("rounded_front_hand_expected", set(result["not_certainly_dominated"]) == {"alpha", "beta", "gamma"})
check("rounded_feasibility_uncertain", result["feasibility"]["alpha"]["status"] == "uncertain")
check("infeasible_gamma", result["feasibility"]["gamma"]["status"] == "definitely_infeasible")
check("no_definitely_feasible_recommendation", result["definitely_feasible_nominal_front"] == [])
check("protection_unknown_refused", compare(rows, require_verified_protection=True)["status"] == "refused")
for field in rows[0]["context"]:
    altered = copy.deepcopy(rows)
    altered[1]["context"][field] = "measurement" if field == "source_kind" else "different_valid_context"
    check("mismatch_"+field, compare(altered)["status"] == "refused")
for field in ("unit", "denominator", "uncertainty_kind"):
    altered = copy.deepcopy(rows)
    altered[1]["metrics"]["area_ratio"][field] = "bounded" if field == "uncertainty_kind" else "different_semantics"
    check("mismatch_"+field, compare(altered)["status"] == "refused")

# Independent brute force over all endpoint corners, avoiding the engine's
# algebraic worst-case dominance test. Closed boxes, 2 metrics, 3 alternatives.
rng = random.Random(71391)
oracle_checks = 0
for case in range(40):
    sample = copy.deepcopy(rows)
    for row in sample:
        for m in row["metrics"].values():
            lo = rng.randint(0, 5)
            hi = lo+rng.randint(0, 2)
            m.update(lower=lo, upper=hi, value=(lo+hi)/2, uncertainty_kind="bounded")
    corners = [[tuple(p) for p in itertools.product(*[(m["lower"],m["upper"]) for m in r["metrics"].values()])] for r in sample]
    retained = []
    for j, row in enumerate(sample):
        certainly_dominated = False
        for i in range(len(sample)):
            if i == j:
                continue
            dominates_every_corner = all(
                all(a<=b for a,b in zip(x,y)) and any(a<b for a,b in zip(x,y))
                for x in corners[i] for y in corners[j])
            certainly_dominated |= dominates_every_corner
        if not certainly_dominated:
            retained.append(row["id"])
    check("endpoint_enumeration_"+str(case), compare(sample)["not_certainly_dominated"] == retained)
    oracle_checks += 1
out = {"scope": "software correctness, original synthetic tests; no human utility or radiation validation",
       "tests": checks, "endpoint_enumeration_cases": oracle_checks,
       "fixture_sha256": hashlib.sha256((PUBLIC/"examples/rounded_costs.json").read_bytes()).hexdigest(),
       "seed": 71391}
dest = ROOT/"validation"
dest.mkdir(exist_ok=True, parents=True)
(dest/"independent_contract_evaluation.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps({"passed":len(checks),"enumeration_cases":oracle_checks}))
