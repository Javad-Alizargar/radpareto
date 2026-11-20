"""Pinned external HDL structural validation; no physical radiation claims."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "48ff7a7e2ef782cf778d47910cf85835c64b1bce"
FILES = {"rtl/priority_encoder.v":"df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5",
         "rtl/arbiter.v":"d54d337db4812f927b2e9b5788dfa39f9bd578ad01b7846c5fa7f2610b0923fa",
         "COPYING":"8ea57f95365e9b16a5b516f422b71269183a1ae53bab5878ae6d69039e58fe77",
         "AUTHORS":None}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2)+"\n",encoding="utf-8")


def fetch_sources(vendor):
    vendor.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name, expected in FILES.items():
        url=f"https://raw.githubusercontent.com/alexforencich/verilog-axis/{COMMIT}/{name}"
        target=vendor/Path(name).name
        if not target.exists():
            with urlopen(Request(url,headers={"User-Agent":"RadPareto-research"}),timeout=30) as response:
                data=response.read(1024*1024+1)
            if len(data)>1024*1024:
                raise ValueError("Unexpected source size")
            if expected and hashlib.sha256(data).hexdigest()!=expected:
                raise ValueError("Pinned source hash mismatch before write: "+name)
            target.write_bytes(data)
        if expected and digest(target)!=expected:
            raise ValueError("Retained source hash mismatch: "+name)
        rows.append({"upstream_path":name,"url":url,"file":target.name,"sha256":digest(target),"bytes":target.stat().st_size})
    manifest={"repository":"https://github.com/alexforencich/verilog-axis","commit":COMMIT,
              "license":"MIT; original COPYING, AUTHORS and embedded copyright notices preserved",
              "selection":"Four parameter configurations of two related modules from one project; upstream is deprecated/superseded",
              "files":rows}
    save(vendor/"source_manifest.json",manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--engine-root",type=Path,default=ROOT)
    parser.add_argument("--yosys",default="yowasp-yosys")
    parser.add_argument("--fetch-only",action="store_true")
    parser.add_argument("--output",type=Path,help="Fresh output directory inside the repository; retained results are never overwritten")
    args=parser.parse_args()
    base=ROOT/"benchmarks/external_hdl"
    vendor=base/"vendor"
    source=fetch_sources(vendor)
    if args.fetch_only:
        print(json.dumps(source,indent=2)); return
    out=args.output.resolve() if args.output else base/"generated"; hdl=base/"wrappers"
    out.relative_to(ROOT)
    if out.exists():
        raise SystemExit("Preserving prior results: move this benchmark to a fresh checkout/output tree before rerun")
    out.mkdir(parents=True); hdl.mkdir(parents=True,exist_ok=True)
    engine=args.engine_root.resolve()
    sys.path.insert(0,str(engine/"src"))
    from radpareto.yosys import import_yosys
    helper_path=engine/"scripts/run_open_benchmarks.py"
    spec=importlib.util.spec_from_file_location("original_wrapper_helper",helper_path)
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    executable=str(Path(args.yosys).resolve()) if Path(args.yosys).exists() else args.yosys
    version=subprocess.run([executable,"-V"],capture_output=True,text=True,check=True,timeout=180).stdout.strip()
    manifest={"generated_utc":datetime.now(timezone.utc).isoformat(),"tool_version":version,"python":platform.python_version(),
              "source_commit":COMMIT,"wrapper_helper_sha256":digest(helper_path),"runs":[],"checks":[],
              "scope":"Generic structural costs and fault-free equivalence only; related convenience configurations"}
    records,metrics=[],[]
    def execute(script,stem):
        scriptpath=out/f"{stem}.ys"; scriptpath.write_text(script,encoding="utf-8")
        command=[executable,"-T","-s",scriptpath.relative_to(ROOT).as_posix()]
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=180)
        log=out/f"{stem}.log"; log.write_text(run.stdout+run.stderr,encoding="utf-8")
        manifest["runs"].append({"command":[Path(executable).name]+command[1:],"returncode":run.returncode,
            "script":scriptpath.relative_to(ROOT).as_posix(),"script_sha256":digest(scriptpath),
            "log":log.relative_to(ROOT).as_posix(),"log_sha256":digest(log)})
        save(out/"execution.json",manifest)
        if run.returncode:
            raise RuntimeError("Yosys failed; preserved log: "+str(log))
        return run.stdout+run.stderr
    for module in ("priority_encoder","arbiter"):
        for ports in (4,8):
            bits=(ports-1).bit_length(); width=ports+bits+1
            name=f"{module}{ports}"
            if module=="priority_encoder":
                body=f"priority_encoder #(.WIDTH({ports}), .LSB_HIGH_PRIORITY(0)) dut(.input_unencoded(a[{ports-1}:0]), .output_valid(y[{ports}]), .output_encoded(y[{width-1}:{ports+1}]), .output_unencoded(y[{ports-1}:0]));"
                parameters={"WIDTH":ports,"LSB_HIGH_PRIORITY":0}
            else:
                body=f"arbiter #(.PORTS({ports}), .ARB_TYPE_ROUND_ROBIN(0), .ARB_BLOCK(0), .ARB_BLOCK_ACK(1), .ARB_LSB_HIGH_PRIORITY(0)) dut(.clk(clk), .rst(sel), .request(a[{ports-1}:0]), .acknowledge(b[{ports-1}:0]), .grant(y[{ports-1}:0]), .grant_valid(y[{ports}]), .grant_encoded(y[{width-1}:{ports+1}]));"
                parameters={"PORTS":ports,"ARB_TYPE_ROUND_ROBIN":0,"ARB_BLOCK":0,"ARB_BLOCK_ACK":1,"ARB_LSB_HIGH_PRIORITY":0}
            wrapper=hdl/f"{name}.v"
            wrapper.write_text(helper.write_hdl(name,width,body).replace("Original RadPareto benchmark.","Original RadPareto wrapper around attributed external RTL."),encoding="utf-8")
            sourcepaths=[vendor/"priority_encoder.v",vendor/"arbiter.v",wrapper]
            read="read_verilog "+" ".join(p.relative_to(ROOT).as_posix() for p in sourcepaths)+"\n"
            context={"baseline_id":f"external-{name}-{digest(wrapper)[:12]}","device":"abstract_generic_logic",
                "toolchain":"Yosys synth -noabc; dffunmap; techmap; opt_clean; preserved hierarchy","tool_version":version,
                "implementation":"generic one-bit primitives; no place-and-route",
                "constraints_id":"preserve-replicas-v1-no-physical-constraints","timing_corner":"not_applicable_logic_depth_surrogate",
                "workload_id":"all Boolean inputs; sequential check limited to 12 initial-zero steps","source_kind":"synthesis"}
            for method in ("base","tmr"):
                stem=f"{name}_{method}"; netlist=out/f"{stem}.json"
                script=read+f"synth -top {method} -noabc\ndffunmap\ntechmap\nopt_clean\ncheck -assert\nstat\nwrite_json {netlist.relative_to(ROOT).as_posix()}\n"
                script+="setattr -mod -unset keep_hierarchy\nsetattr -unset keep_hierarchy\nflatten\nltp -noff\n"
                log=execute(script,stem)
                record,summary=import_yosys(netlist,top=method,record_id=stem,design=name,method=method,
                                            context=context,source_uri=netlist.relative_to(ROOT).as_posix())
                count=summary["hierarchy_instances"].get(f"core_{name}",0)
                assert count==(3 if method=="tmr" else 1),(name,method,count)
                cells=re.findall(r"\n\s*(\d+) cells\n",log)
                depths=re.findall(r"Longest topological path in \S+ \(length=(\d+)\)",log)
                assert cells and int(cells[-1])==summary["cell_count"],(name,cells,summary)
                assert depths and max(map(int,depths))==summary["logic_depth"],(name,depths,summary)
                summary.update(design=name,module=module,parameters=parameters,method=method,wrapper_sha256=digest(wrapper),
                               netlist_sha256=digest(netlist),independent_yosys_stat_and_ltp_check="passed")
                records.append(record); metrics.append(summary)
            script=read+"hierarchy -top check\nproc\nsetattr -mod -unset keep_hierarchy\nsetattr -unset keep_hierarchy\nflatten\nopt\ndffunmap\n"
            script+="sat -verify -prove ok 1 -seq 12 -set-init-zero\n" if module=="arbiter" else "sat -verify -prove ok 1\n"
            log=execute(script,f"{name}_equivalence"); assert "SUCCESS!" in log
            manifest["checks"].append({"design":name,"module":module,"parameters":parameters,"fault_free_equivalence":"passed",
                  "bounded_steps":12 if module=="arbiter" else None,"tmr_core_instances":3,"radiation_effectiveness":"not_tested"})
            save(out/"execution.json",manifest)
    save(out/"evidence.json",{"schema_version":"1.0","records":records}); save(out/"metrics.json",metrics)
    print(json.dumps({"configurations":4,"modules":2,"records":len(records),"runs":len(manifest["runs"]),"checks":len(manifest["checks"]),"tool":version}))


if __name__=="__main__":
    main()
