# External HDL structural checks

Four parameter configurations use two related modules from `alexforencich/verilog-axis`, pinned at commit `48ff7a7e2ef782cf778d47910cf85835c64b1bce`: priority encoders of width 4 and 8, and arbiters with 4 and 8 ports. The upstream project is deprecated/superseded; these small MIT-licensed files are selected for reproducible structural checks, not recommendations about current IP.

Original HDL, `COPYING`, `AUTHORS`, embedded notices and source hashes are retained in `benchmarks/external_hdl/vendor`. Original adaptation wrappers connect all valid, encoded and unencoded/grant output bits, preserving even invalid-input output behavior. Arbiters use fixed-priority, nonblocking settings explicitly retained in the execution records. Common unused wrapper input bits do not add functionality.

Resource runs preserve three TMR core instances and bitwise voters. Yosys `synth -noabc`, `dffunmap`, `techmap`, `opt_clean` produce supported generic primitives. The importer checks cell totals against `stat` and depth against flattened `ltp -noff`. Separate fault-free proof flows check all Boolean inputs for encoders and 12 steps from zero initialization for arbiters. They do not establish injected-fault tolerance or arbitrary-state sequential equivalence.

Install `requirements-benchmarks.txt` in a separate environment, then run:

```sh
python scripts/run_external_benchmarks.py --output benchmarks/external_hdl/replay-generated
```

The output directory must be fresh and inside the repository. Existing results are preserved. Source downloads occur only if pinned files are missing, and verified hashes are checked before use. The retained run used Yosys 0.71 (b4c586fd3). Four configurations are related convenience examples from one upstream project, not four independent designs. Generic cell count and logic depth are not mapped device area, physical timing, radiation cross-section or a physical protection measurement.
