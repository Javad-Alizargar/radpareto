"""Create original synthetic evidence examples with source hashes."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "examples/fixture_source.json"
source = json.loads(source_path.read_text(encoding="utf-8"))
digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
records = []
for row in source["observations"]:
    records.append({
        "id": row["id"], "design": "synthetic_example", "method": row["id"],
        "context": {"baseline_id": "original-example-v1", "device": "abstract_example",
            "toolchain": "original_fixture", "tool_version": "1.0", "implementation": "abstract_costs",
            "constraints_id": "example-v1", "timing_corner": "not_applicable_abstract_costs",
            "workload_id": "synthetic-v1", "source_kind": "synthetic_example"},
        "metrics": {name: {"value": row[name], "lower": row[name]-.05, "upper": row[name]+.05,
            "unit": "ratio", "denominator": "original-example-v1:"+name,
            "uncertainty_kind": "rounding"} for name in ("area_ratio", "cycle_ratio")},
        "provenance": {"source_uri": "examples/fixture_source.json", "source_sha256": digest,
            "locator": "observations[id="+row["id"]+"]", "extraction": "original deterministic synthetic fixture"},
        "protection": {"status": "unverified", "fault_model": "not_tested",
            "scope": "no_radiation_claim", "evidence_uri": "not_available"},
    })
document = {"schema_version": "1.0", "records": records}
(ROOT/"examples/rounded_costs.json").write_text(json.dumps(document, indent=2)+"\n", encoding="utf-8")
mismatch = copy.deepcopy(document)
mismatch["records"][1]["metrics"]["area_ratio"]["unit"] = "generic_cells"
(ROOT/"examples/incompatible_units.json").write_text(json.dumps(mismatch, indent=2)+"\n", encoding="utf-8")
print("Two original fixture documents generated")
