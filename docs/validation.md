# Validation scope

The alpha's tests exercise data validation, compatible grouping, Pareto ties and trade-offs, interval dominance, constraints and explicit refusal. The benchmark adapter is tested against actual generic synthesis outputs and deliberate unsupported netlist cases. Numerical decisions are also checked by an independently expressed enumeration baseline.

Run `python scripts/evaluate_contract.py` after installing the package. Its 58
contract checks include 40 seeded interval cases evaluated by exhaustive
endpoint-corner enumeration. This is an alternative software oracle, not an
external human review or a complete proof for arbitrary inputs. Separately,
release 0.4.0 has 79 unit/regression test methods, run with
`python -m unittest discover -s tests -v`. The earlier 0.2.1a1 release had 58
unit/regression methods; those historical and current counts are not pooled.

The [version and module-identity table](validation_versions.md) makes the
current-versus-historical scope explicit. The existing full core suite
already detects the M01 tie defect that survived the four selected historical
families. A separate post-study regression probe records this current
coverage without changing the original 11/12 detection result.

## Published-summary calculations in 0.3.0

The six-design example retains 78 attributed numbers from Tables 9 and 10;
the context diagnostic adds six Table 11 frequencies. Individual raw runs
were not obtained or reconstructed. The atlas partitions the exact
printed-decimal reference problem into 14 resource faces and 38 frequency
faces. All 3,192 design/representative decisions over their 532 products
match the direct-MHz reference. Equality and +/-0.000001 MHz regression
neighbors for the 18 source frequency breakpoints (12 range endpoints and
six means) cover 54 cases, including two equalities where the previous
mixed conversion paths differed by one binary64 step. All 72 original
budget scenarios retain their classifications.

Distinct exact decimal requirements can round to the same binary64 period.
The finite representative agreement is not a continuum-wide engine proof.
The conversion helper rejects unsupported, nonpositive or nonfinite values,
reciprocal overflow and reciprocal rounding to zero. Positive subnormal
periods are allowed and do not imply physical precision.

The endpoint-only sensitivity analysis assumes nearest-0.001-MHz rounding,
uses a conservative +/-0.0005-MHz enclosure and holds displayed means fixed.
Its 86 refined frequency faces and six designs give 516 checked decisions.
The 24 changed design/region rows have no probability or area weighting;
they are not a prevalence or an error rate. The six merged-project
worst-case summaries are kept separate from standalone means and ranges.
Two of 15 pair orders reverse descriptively; this is not a paired or causal
effect estimate.

`benchmarks/published_case/decision_atlas/verify_outputs.py` independently
reconstructs the complete representative product and all changed precision
rows with Decimal arithmetic. It imports neither the analyzer nor RadPareto.
Exact decimal fields use zero tolerance; reported percentage ratios use
1e-12 absolute percentage points. This is a separate implementation within
the same research project, not blinded external validation. Commands and
retained result locations are in [reproduction guidance](reproduction.md).

## Retained historical validation

The 60-scenario matched contract, 720 metamorphic properties, 1,625 synthetic
response-surface cells, 66,960 finite certificate case/probe decisions and
local timing outputs retain their 0.2.1a1 study provenance. The seeded
semantic-defect experiment replays its frozen 0.2.0a1 sources: 11 of 12
purposively selected mutants were detected by four specified families;
M01 survived. These dependent constructed cases are not additional hardware
observations or population-accuracy estimates. Current replays do not
retroactively turn historical timings into 0.3.0 latency measurements.

Original synthetic fixtures are software tests, not observed radiation data. Original HDL fixtures are new executable logic examples, not replications of Smith's designs. Generic synthesis validates an import workflow and logic metrics; it does not validate flash-device timing or physical radiation tolerance.

Independent installation/use and domain review could strengthen evidence of practical utility. They are not asserted here as blanket journal requirements. A verified mapped flash implementation would be needed for any flash-specific performance claim. Passing automated tests does not establish novelty or publication readiness.

This release contains original fixtures and an attributed published-summary
reanalysis under `benchmarks/published_case/`. The latter reproduces the stated
table-to-decision calculations, not the source hardware runs or irradiation.
The package can also be exercised with entirely original examples.
