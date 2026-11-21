# Published frequency decision atlas

This analysis uses exact printed decimals from Ma et al., *Electronics* 2026,
15(22), 5390, DOI [10.3390/electronics15225390](https://doi.org/10.3390/electronics15225390),
distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Attribution: Jinlong Ma, Weike Liu, Wenxun Wei, Xin Chen, Danfeng Qiu,
Zongguang Yu and Daiyin Zhu. This directory supplies original numerical
transcriptions and new calculations; it does not redistribute the article.

The parent data contain 78 numbers for six designs from Tables 9 and 10.
`merged_context.csv` adds the six printed domain frequencies from Table 11,
using the CLKA-CLKF structure mapping in its note. These are published
post-layout static timing summaries. They are not new physical measurements,
raw run observations, or independent replications of the source experiment.

Run from the public repository root, with a fresh output directory:

```text
python benchmarks/published_case/decision_atlas/analyze.py --engine-src src --out atlas-replay
python benchmarks/published_case/decision_atlas/verify_outputs.py --case-dir benchmarks/published_case --results atlas-replay --out atlas-check.json
python -m unittest discover -s tests -v
```

Only Python's standard library and RadPareto are required. Inputs are checked
against `source_manifest.json` before computing results. The manifest includes
the source CSV, exact decimal data, context metadata, new transcription and
the explicit analysis plan. `run_manifest.json` records the script, inputs,
engine files and generated result hashes.

`verify_outputs.py` imports neither the analyzer nor RadPareto. Its separate
Decimal implementation checks completeness and uniqueness of the 532-point
representative product, all 3,192 classifications, six metric rows, fifteen
context pair orders and the 24 changed precision rows across 516 reference
checks. Exact decimal fields use zero tolerance; percentage ratios use
1e-12 absolute percentage points. The checker records the input/output hashes
and its own source hash. It is a separate implementation within this project,
not blinded external or human validation. Retained results are in `results/`
and their checker receipt is `independent_check.json`.

The software partitions all nonnegative resource/clock budgets at source
breakpoints. Point faces preserve equality, and open faces use rational
midpoints; the final unbounded face uses a point above the largest breakpoint.
The exact printed-decimal reference classification cannot change within a
face because all source thresholds are included. There are 14 resource faces
and 38 frequency faces, hence 532 regions and 3,192 tested design/representative
decisions. The regions exhaust the exact reference problem for this finite
threshold set. Agreement at their representatives is a finite software check,
not a proof of engine agreement at every arbitrarily close decimal input and
not 3,192 independent observations.

The independent oracle compares the exact printed MHz values directly.
The engine compares reciprocal costs. `period_ns_from_mhz` evaluates the
decimal reciprocal as a rational and rounds once to binary64. Both source
frequencies and requirements follow that same path. The former mixed paths
differed by one ULP at the 40.578 and 40.975 MHz endpoints of DF-TMR-DFF-1.28,
changing two equality decisions. The original 72 round-number scenario
classifications are unchanged. Core comparison semantics are unchanged.
Binary64 remains the engine's representation: for example, 40.578 and
40.578000000000000000001 MHz convert to the same period even though the latter
is strictly greater as an exact decimal. The adapter removes inconsistent
conversion paths at the tested equalities; it does not preserve every
arbitrary-precision strict inequality. Positive subnormal periods are allowed;
overflow or rounding to zero is rejected, as are unsupported exponent strings.

The precision scenario assumes rounding to nearest 0.001 MHz and encloses
each printed endpoint by plus/minus 0.0005 MHz. It is a sensitivity assumption,
not a confidence interval, additional process variation, or a claim that
the source used a particular tie-breaking convention. The 72 original
scenario decisions remain unchanged under this enclosure. Continuous maps
retain the narrow boundary regions where labels change.
Displayed means are held fixed; robustness to rounding of the means is not
assessed. The 24 changed design/region rows enumerate point and open faces on
the refined reference partition. They carry no probability or area weighting
and must not be interpreted as a prevalence or error rate.

Table 10 standalone three-run means/ranges and Table 11 merged-project
worst-case summaries stay in separate contexts. Their ranking differs in
two of fifteen pair orders. This is descriptive comparison between different
implementations and summaries, not a paired effect, causal estimate or
statistical test. Standalone resource costs are never combined with merged
timing. A mixed comparison is refused and batch mode produces two groups
of six records. The exact label on a merged record describes its printed
summary value only; it is not an uncertainty claim about the underlying system.

Useful outputs:

- `design_metrics.csv`: observed spans, nominal/range disagreement widths,
  clock headroom, exact reciprocal fractions and precision-enclosed endpoints.
- `exact_atlas.csv`: source-defined decision regions, boundary inclusion,
  accepted counts and retained design identities.
- `conversion_boundary_audit.csv`: all 18 source frequency breakpoint conversions
  (12 range endpoints and six means) and
  the two former equality discrepancies.
- `precision_changed_regions.csv`: every source-defined sensitivity region
  that changes under the stated reporting-precision enclosure.
- `context_comparison.csv` and `context_pair_orders.csv`: six source-linked
  summaries and all fifteen pair orders.
- `context_records.json`, refusal and partition files: executable evidence
  of the context guard and separate comparisons.

No protection equivalence, radiation effectiveness, future-run coverage,
laboratory adoption or user-benefit estimate is established by these results.
