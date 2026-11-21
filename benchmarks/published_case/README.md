# Published ProASIC3 cost example

Original numerical transcription and adaptation of Tables 9 and 10 in Ma et al., *Quantitative Trade-Off Evaluation of Hardened DFFs in 130 nm ProASIC3 Flash-Based FPGAs Under Wide-LET Heavy-Ion Irradiation*, Electronics 2026, 15(22), 5390. DOI: https://doi.org/10.3390/electronics15225390. Source: https://www.mdpi.com/2079-9292/15/22/5390. Numerical source material retains **CC BY 4.0** attribution; analysis code is MIT. The new reciprocal-frequency conversion, budgets, candidate scopes and sensitivity model are adaptations, not source-author conclusions.

From the repository root after installing RadPareto:

```sh
python benchmarks/published_case/analyze_case.py --engine-src src --out published-replay
```

Use a fresh output directory. The script verifies frozen source hashes and resource arithmetic, then produces source-located records, comparisons, all 72 budget decisions and exact conditional stability boundaries. The original CSV and exact JSON retain 78 printed numeric values without inventing individual runs. Metadata identifies the shared device/tool/workload/corner and access limitations. Public metadata omits private audit paths; numeric CSV/JSON bytes remain unchanged from the original transcription.

The second minimized cost is **1000 / mean maximum frequency**, with reversed reciprocal min-max endpoints. It is neither mean period nor mean critical-path delay. Bounds represent three observed implementation runs, not confidence intervals or guaranteed future-run coverage. The resource cost excludes one-off project circuitry. The only source clock reference is 30 MHz; all resource caps and other clock requirements are analyst-selected what-if scenarios. Widening by t cells per bit and t ns is a declared sensitivity assumption.

At 40 cells/bit and 32 MHz, DF-TMR-DFF-5.12 passes the mean-only frequency screen while its observed range crosses the requirement. The all-six cost frontier is BL-DFF; that is **not** a protection recommendation. Protection-required comparison refuses unverified protection equivalence. Optional architecture subsets are explicitly named cost screens. Radiation cross-sections and zero-event upper limits do not enter this analysis. Exact source HDL, seeds, raw run frequencies and implementation reports were not obtained; this is computational replay of published numbers, not hardware reproduction.

Release 0.3.0 uses the same decimal-to-reciprocal conversion for source values
and clock requirements. This corrects two one-ULP equality decisions at
40.578 and 40.975 MHz without changing the original 72 scenario labels.
The new [decision atlas](decision_atlas/README.md) supplies source-defined
budget regions, design margins, explicit endpoint-rounding sensitivity and
six Table 11 frequencies in a separate merged-project context. Its portable
checker and all numerical outputs are public. See
[reproduction guidance](../../docs/reproduction.md) for fresh replay commands
and the distinction between current software tests and historical studies.
