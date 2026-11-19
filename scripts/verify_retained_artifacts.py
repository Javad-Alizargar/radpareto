"""Verify retained experiment bytes and reimport their structural metrics."""
import hashlib
import json
from pathlib import Path
from radpareto import validate_document
from radpareto.yosys import summarize_yosys

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples/generated"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    execution = json.loads((GENERATED / "execution.json").read_text())
    metrics = json.loads((GENERATED / "metrics.json").read_text())
    evidence = validate_document(json.loads((GENERATED / "evidence.json").read_text()))
    hashes = 0
    for run in execution["runs"]:
        assert run["returncode"] == 0, run["script"]
        for kind in ("script", "log"):
            assert digest(ROOT / run[kind]) == run[kind + "_sha256"], run[kind]
            hashes += 1
    for metric in metrics:
        design, method = metric["design"], metric["method"]
        netlist = GENERATED / f"{design}_{method}.json"
        assert digest(netlist) == metric["netlist_sha256"], str(netlist)
        assert digest(ROOT / f"examples/hdl/{design}.v") == metric["source_sha256"], design
        summary = summarize_yosys(json.loads(netlist.read_text()), method)
        for name in ("cell_count", "logic_depth", "flip_flops"):
            assert summary[name] == metric[name], (design, method, name)
        hashes += 2
    for record in evidence:
        path = ROOT / record["provenance"]["source_uri"]
        assert digest(path) == record["provenance"]["source_sha256"], record["id"]
        hashes += 1
    print(json.dumps({"status": "passed", "hash_checks": hashes,
                      "netlists_reimported": len(metrics), "evidence_records": len(evidence),
                      "successful_tool_runs": len(execution["runs"])}))


if __name__ == "__main__":
    main()
