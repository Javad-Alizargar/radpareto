# Second-source structural mapping application

The independent source is Alex Forencich's MIT-licensed `priority_encoder.v` from
`alexforencich/verilog-axis`, commit `48ff7a7e2ef782cf778d47910cf85835c64b1bce`.
The existing `benchmarks/external_hdl/vendor/` preserves the original source,
COPYING and AUTHORS. Source SHA-256:
`df28220d95b47df349a72803a9751aad331eb8e1435416e8686d00572a974dd5`.
No new numerical observation is copied from a paper: all reported mapping costs
come from the retained execution of the pinned synthesis pipeline.

## Conditions and decision

An engineer explores mapping methods for the same 16-input MSB-priority encoder.
All eight alternatives use the same source function, width, tool version,
flattening flow and generic gate basis (AND, OR, XOR, MUX and NOT). Only the
explicit ABC mapping recipe varies as the method. Source function equivalence is
checked by SAT for all Boolean inputs, including the source's output behavior
when no input is asserted. No protection-equivalence claim is made.

The two minimized metrics are generic cell count and combinational graph depth.
They are exact properties of each retained netlist, not interval estimates of
physical area or timing. Generic logic levels ignore gate/load/routing delay.
No FPGA device mapping, place-and-route, irradiation or physical validation is
performed. This second application demonstrates upstream structural design-space
screening rather than another physical FPGA implementation study.

The `simple_map` and `balance_map` recipes both produce 84 cells and seven levels;
`area_map` produces 58 cells and eight levels. These three records form two unique
non-dominated cost points. The other five recipes are dominated under these costs.
A 60-cell/eight-level budget selects `area_map`; a 90-cell/seven-level budget
selects `simple_map` and `balance_map`; 60 cells/seven levels admit no supplied
candidate. The example does not assert that these recipes exhaust all possible
implementations or identify a physical optimum.

## Reproduce

```text
python -m pip install .
python -m pip install -r benchmarks/priority_encoder_mapping/requirements.txt
python benchmarks/priority_encoder_mapping/run_synthesis.py --out mapping-replay
python -m radpareto compare mapping-replay/records.json --limit cell_count=60 --limit logic_depth=8 --output mapping-review.json
```

Use a fresh output directory. The pinned YoWASP tool reports Yosys 0.71,
git `b4c586fd3`; the full version string is retained. Each of the eight outputs is
checked against Yosys `stat` and `ltp`, then SAT-proved equivalent to the original
source function. SAT equivalence establishes fault-free Boolean functionality,
not timing or radiation behavior. Sixteen tool executions are retained (eight
mapping and eight equivalence runs). `results/` contains source, mapping scripts,
netlists, metric summaries, tool logs, SAT transcripts, decisions and manifest.

The eight recipes were retained after an exploratory sweep at widths 16 and 32;
this is an illustrative reproducible application, not a preregistered algorithm
ranking. `default` means the pinned Yosys default, not an unspecified moving tool
configuration. Common conditions appear in each record; distinct tool versions,
gate bases or functions must be separated rather than pooled.

MIT source notices must accompany redistributed copies. All new application
scripts follow the repository's MIT license. No manuscript, publication artwork,
private review or copied article is part of these public reproduction materials.
