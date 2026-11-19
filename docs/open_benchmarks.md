# Open generic synthesis examples

These eight original small Verilog examples exercise the resource-import and
comparison workflow independently of the historical Smith paper tables. They
are newly constructed software-validation fixtures, not an external laboratory
dataset, a representative sample of FPGA designs, or radiation experiments.

The categories were fixed in the runner before synthesis: arithmetic (4/8-bit
adders), selection/reduction (4-bit mux, 8-bit parity), and state (4/8-bit counters
and shift registers). Each has an unprotected baseline and a TMR wrapper with
three explicitly preserved core instances and a Boolean majority voter. Baseline
and TMR have different protection structures; a cost-only frontier does not
select the better radiation mitigation.

## Reproduction

Install the pinned development dependencies in an isolated Python environment:

```text
python -m pip install -r requirements-benchmarks.txt
python scripts/run_open_benchmarks.py --yosys yowasp-yosys
python scripts/verify_retained_artifacts.py
python -m unittest discover -s tests -p test_yosys.py -v
```

On Windows, the explicit executable can be `.venv/Scripts/yowasp-yosys.exe`.
An alternative Yosys binary can be supplied, but a different version constitutes
a new experiment. The pinned run used yowasp-yosys 0.71.0.0.post1285, wrapping
Yosys 0.71, git b4c586fd3. The core RadPareto package itself does not require Yosys
to read the retained JSON examples.

`examples/generated/execution.json` records tool/version, all 24 script invocations,
their return codes and script/log SHA-256 hashes, and eight equivalence outcomes.
`metrics.json` retains 16 source/netlist hashes and structural summaries.
`evidence.json` contains 16 records for the RadPareto comparison contract.
Full logs, native Yosys JSON netlists, and generated `.ys` scripts are retained.
The original Verilog inputs are in `examples/hdl/`.

## Metrics and independent cross-checks

- `cell_count` counts recursively expanded mapped generic one-bit primitives,
  including flip-flops. It is not physical area, LUT usage or a vendor tile count.
- `logic_depth` is the maximum number of combinational primitives from a primary
  input or flip-flop output. Flip-flops break feedback paths. This is a structural
  surrogate, not nanoseconds, cycle time, frequency, timing closure or a place-and-route result.
- Counts were checked against Yosys's own hierarchical `stat` output. Depth was
  checked against `ltp -noff` after flattening the design without subsequent
  optimization. Both checks passed for all 16 netlists.
- Three core instances must survive in every TMR netlist; otherwise the runner
  stops. No abstract delay element or analog guard-gate is included.

Exact intervals in the evidence records mean exact integer counts for that
saved netlist under this definition. They do not imply physical certainty or
cross-tool/device invariance. The timing-corner field explicitly denotes a
logic-depth surrogate where no physical timing corner applies.

## Functional check and its boundary

The runner builds a baseline/TMR equality miter and separately flattens it for
Yosys SAT. All four combinational designs passed the all-input fault-free proof.
The four sequential designs passed a 12-step bounded check from zero initial
state with arbitrary Boolean inputs. This is not an unbounded sequential proof.
The proof task may simplify equivalent logic; its resulting structure is not
used for reported resource counts. No fault injection or radiation protection
validation was performed. Fault models, fault coverage and mission error rates
remain unverified in the output records.

## Supported importer scope

`radpareto.yosys.import_yosys` accepts saved Yosys JSON with a named top module.
It supports hierarchy composed of BUF, NOT, AND, NAND, OR, NOR, XOR, XNOR, MUX,
and simple positive/negative-edge DFF generic primitives. Other mapped cells,
memories, processes, inout ports, black/white boxes, unresolved signals and
combinational cycles are rejected. Integer cells are counted equally; no
cell-library delay weights are inferred. Hierarchical pass-through/fanout and
constant outputs are handled explicitly. The importer rejects duplicate JSON
keys, nonfinite constants, x/z literal bits and malformed primitive ports.
The input is read with a 10 MiB bound. Expanded hierarchy size is not separately
bounded; use netlists from trusted local tool runs rather than untrusted uploads.

Context values come from the caller and retained experiment manifest. A hash
binds the imported bytes; it does not independently authenticate the producer or
prove its metadata are true. Core evidence validation must run before ranking.

## Primary tool sources

- YoWASP package and usage overview: https://yowasp.org/
- Published package: https://pypi.org/project/yowasp-yosys/
- Yosys source: https://github.com/YosysHQ/yosys
- Version-matched command help inspected locally: `help synth`, `help sat`,
  `help write_json`, `help ltp`; the retained runner records actual commands.

The YoWASP distribution is an unofficial WebAssembly build of upstream Yosys.
It is not a new synthesis algorithm contributed by RadPareto.
