"""Generate original integer-box cases before any production evaluation."""
from pathlib import Path
import hashlib
import json
import random
from datetime import datetime, timezone

DEST = Path(__file__).resolve().parent / "frozen"


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    if DEST.exists():
        raise SystemExit("Refusing to overwrite frozen cases")
    DEST.mkdir()
    source = []
    for layout in ("mixed", "chain", "tradeoff", "ties"):
        for n in (3, 8, 16):
            for m in (2, 3):
                for seed in range(20261120, 20261125):
                    rng = random.Random(f"{layout}:{n}:{m}:{seed}")
                    values = []
                    for i in range(n):
                        row = {}
                        for j in range(m):
                            v = (rng.randint(10, 90) if layout == "mixed" else
                                 10 + 5*i + 2*j if layout == "chain" else
                                 10 + 5*(i if j % 2 == 0 else n-1-i) if layout == "tradeoff" else
                                 10 + 10*(i % 3) + 2*j)
                            row[f"cost_{j}"] = {"value": v, "lower": max(0, v-rng.randint(0, 3)),
                                                 "upper": v+rng.randint(0, 3)}
                        values.append(row)
                    limits = {f"cost_{j}": (min(r[f"cost_{j}"]["value"] for r in values) +
                                             max(r[f"cost_{j}"]["value"] for r in values)) // 2 for j in range(m)}
                    source.append({"case_id": f"{layout}-n{n}-m{m}-s{seed}", "layout": layout,
                                   "record_count": n, "objective_count": m, "seed": seed,
                                   "values": values, "limits": limits})
    dump(DEST / "source_records.json", source)
    source_sha = hashlib.sha256((DEST / "source_records.json").read_bytes()).hexdigest()
    cases = []
    context = {"baseline_id": "synthetic-fixture-v1", "device": "synthetic-device",
               "toolchain": "original-integer-generator", "tool_version": "1.0",
               "implementation": "synthetic-boxes", "constraints_id": "property-protocol-v1",
               "timing_corner": "nonphysical-cost-coordinates", "workload_id": "constructed-fixture",
               "source_kind": "synthetic_example"}
    for case in source:
        records = []
        for i, values in enumerate(case["values"]):
            records.append({"id": f"r{i:02d}", "design": case["case_id"], "method": f"alternative-{i}",
                            "context": context.copy(), "metrics": {
                                k: dict(v, unit="synthetic_cost", denominator="same_fixture_baseline",
                                        uncertainty_kind="bounded") for k, v in values.items()},
                            "provenance": {"source_uri": "source_records.json", "source_sha256": source_sha,
                                           "locator": f"{case['case_id']}/values/{i}",
                                           "extraction": "Original constructed coordinates; transformations are explicit in the study protocol."},
                            "protection": {"status": "unverified", "fault_model": "unverified",
                                           "scope": "synthetic costs only", "evidence_uri": "unverified"}})
        cases.append({k: case[k] for k in ("case_id", "layout", "record_count", "objective_count", "seed", "limits")} |
                     {"document": {"schema_version": "1.0", "records": records}})
    dump(DEST / "cases.json", cases)
    dump(DEST / "freeze.json", {"frozen_utc": datetime.now(timezone.utc).isoformat(), "cases": len(cases),
                               "planned_properties": 6, "planned_property_instances": 720,
                               "case_sha256": hashlib.sha256((DEST / "cases.json").read_bytes()).hexdigest(),
                               "source_sha256": source_sha,
                               "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                               "scope": "Local pre-execution freeze of dependent synthetic transformations, not independent preregistration."})
    print(json.dumps({"cases": len(cases), "path": str(DEST)}, indent=2))


if __name__ == "__main__":
    main()
