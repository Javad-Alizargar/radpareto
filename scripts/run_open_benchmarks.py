"""Original small HDL synthesis workflow; no vendor/physical timing claims.

Run with Python 3.11+ and yowasp-yosys or a compatible native Yosys executable.
The preserved-hierarchy flow measures generic primitive structure. SAT is
fault-free equivalence (12 bounded steps for sequential designs), not radiation.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from radpareto.yosys import import_yosys

DESIGNS = [
    ("add4", 4, "arithmetic", "assign y = a + b;", False),
    ("add8", 8, "arithmetic", "assign y = a + b;", False),
    ("mux4", 4, "selection", "assign y = sel ? a : b;", False),
    ("parity8", 8, "selection", "assign y = {8{^a}};", False),
    ("counter4", 4, "state", "reg [3:0] q = 0; always @(posedge clk) q <= q + 1'b1; assign y = q;", True),
    ("counter8", 8, "state", "reg [7:0] q = 0; always @(posedge clk) q <= q + 1'b1; assign y = q;", True),
    ("shift4", 4, "state", "reg [3:0] q = 0; always @(posedge clk) q <= {q[2:0],a[0]}; assign y = q;", True),
    ("shift8", 8, "state", "reg [7:0] q = 0; always @(posedge clk) q <= {q[6:0],a[0]}; assign y = q;", True),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_hdl(name, width, body):
    decl = f"input clk, input sel, input [{width-1}:0] a,b, output [{width-1}:0] y"
    src = f"// Original RadPareto benchmark. Generic functional model, no physical timing.\n(* keep_hierarchy = 1 *) module core_{name}({decl});\n{body}\nendmodule\n"
    src += f"module base({decl}); core_{name} dut(clk,sel,a,b,y); endmodule\n"
    src += f"module tmr({decl});\nwire [{width-1}:0] y0,y1,y2;\n"
    for i in range(3):
        src += f"(* keep = 1, keep_hierarchy = 1 *) core_{name} replica{i}(clk,sel,a,b,y{i});\n"
    src += "assign y = (y0 & y1) | (y0 & y2) | (y1 & y2);\nendmodule\n"
    src += f"module check(input clk, input sel, input [{width-1}:0] a,b, output ok);\nwire [{width-1}:0] ref_y, tmr_y;\nbase refdut(clk,sel,a,b,ref_y); tmr testdut(clk,sel,a,b,tmr_y);\nassign ok = ref_y == tmr_y;\nendmodule\n"
    return src


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yosys", default="yowasp-yosys")
    args = parser.parse_args()
    executable = str(Path(args.yosys).resolve()) if Path(args.yosys).exists() else args.yosys
    out = ROOT / "examples/generated"
    hdl = ROOT / "examples/hdl"
    out.mkdir(parents=True, exist_ok=True)
    hdl.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([executable, "-V"], capture_output=True, text=True, check=True, timeout=180).stdout.strip()
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "tool_version": version,
                "python": platform.python_version(), "runs": [], "checks": [], "scope": "generic synthesis and bounded fault-free equivalence only"}
    records, metrics = [], []

    def execute(script, stem):
        scriptpath = out / f"{stem}.ys"
        scriptpath.write_text(script, encoding="utf-8")
        command = [executable, "-T", "-s", scriptpath.relative_to(ROOT).as_posix()]
        run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
        logfile = out / f"{stem}.log"
        logfile.write_text(run.stdout + run.stderr, encoding="utf-8")
        manifest["runs"].append({"command": [Path(executable).name]+command[1:], "cwd": ".", "returncode": run.returncode,
                                 "script": scriptpath.relative_to(ROOT).as_posix(), "script_sha256": digest(scriptpath),
                                 "log": logfile.relative_to(ROOT).as_posix(), "log_sha256": digest(logfile)})
        if run.returncode:
            (out / "execution.json").write_text(json.dumps(manifest, indent=2)+"\n")
            raise RuntimeError(f"Yosys failed for {stem}; see {logfile}")
        return run.stdout + run.stderr

    for name, width, category, body, sequential in DESIGNS:
        vpath = hdl / f"{name}.v"
        vpath.write_text(write_hdl(name, width, body), encoding="utf-8")
        context = {"baseline_id": f"original-{name}-v1-{digest(vpath)[:12]}", "device": "abstract_generic_logic",
                   "toolchain": "Yosys generic synth -noabc preserved hierarchy", "tool_version": version,
                   "implementation": "mapped generic one-bit primitives; no place-and-route",
                   "constraints_id": "preserve-replicas-v1-no-physical-constraints", "timing_corner": "not_applicable_logic_depth_surrogate",
                   "workload_id": "all Boolean input combinations; state initial zero", "source_kind": "synthesis"}
        for method in ("base", "tmr"):
            stem = f"{name}_{method}"
            jsonpath = out / f"{stem}.json"
            script = f"read_verilog {vpath.relative_to(ROOT).as_posix()}\nsynth -top {method} -noabc\ncheck -assert\nstat\nwrite_json {jsonpath.relative_to(ROOT).as_posix()}\n"
            # Keep the measured hierarchical JSON intact; flatten a copy in
            # tool memory without optimizing it to independently cross-check
            # our depth against Yosys's own longest-topological-path command.
            script += "setattr -mod -unset keep_hierarchy\nsetattr -unset keep_hierarchy\nflatten\nltp -noff\n"
            log = execute(script, stem)
            rec, summary = import_yosys(jsonpath, top=method, record_id=stem, design=name, method=method,
                                        context=context, source_uri=jsonpath.relative_to(ROOT).as_posix())
            instances = summary["hierarchy_instances"].get(f"core_{name}", 0)
            assert instances == (3 if method == "tmr" else 1), (stem, instances)
            counts = re.findall(r"\n\s*(\d+) cells\n", log)
            depths = re.findall(r"Longest topological path in \S+ \(length=(\d+)\)", log)
            assert counts and int(counts[-1]) == summary["cell_count"], (stem, counts, summary)
            assert depths and max(map(int, depths)) == summary["logic_depth"], (stem, depths, summary)
            summary.update({"design": name, "method": method, "category": category, "source_sha256": digest(vpath), "netlist_sha256": digest(jsonpath)})
            summary["independent_yosys_stat_and_ltp_check"] = "passed"
            records.append(rec); metrics.append(summary)
        # Flatten only in the separate correctness task. This proof does not
        # claim that optimizations in the proof preserve the measured structure.
        script = f"read_verilog {vpath.relative_to(ROOT).as_posix()}\nhierarchy -top check\nproc\nsetattr -mod -unset keep_hierarchy\nsetattr -unset keep_hierarchy\nflatten\nopt\n"
        script += "sat -verify -prove ok 1 -seq 12 -set-init-zero\n" if sequential else "sat -verify -prove ok 1\n"
        log = execute(script, f"{name}_equivalence")
        assert "SUCCESS!" in log
        manifest["checks"].append({"design": name, "fault_free_equivalence": "passed", "bounded_steps": 12 if sequential else None,
                                   "scope": "all combinational inputs; initial-zero bounded sequential states" if sequential else "all Boolean inputs",
                                   "tmr_instance_count": 3, "radiation_effectiveness": "not_tested"})
    (out / "evidence.json").write_text(json.dumps({"schema_version": "1.0", "records": records}, indent=2)+"\n", encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2)+"\n", encoding="utf-8")
    (out / "execution.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"designs":len(DESIGNS), "records":len(records), "checks":len(manifest["checks"]), "version":version}))


if __name__ == "__main__":
    main()
