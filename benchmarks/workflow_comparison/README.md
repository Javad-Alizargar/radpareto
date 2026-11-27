# Same-information workflow comparison

This example compares the reusable RadPareto package with an explicit conventional
implementation built from pandas 2.2.2, NumPy 2.3.2 and paretoset 1.2.5. Both receive
identical source-linked records, supplied ranges and decision requirements.
`conventional.py` imports no RadPareto implementation. Its eligibility checks,
interval logic, diagnostics, provenance export and CLI are custom application code;
paretoset supplies the ordinary frontier. It uses `distinct=False` to retain ties
and `use_numba=False` for the declared execution path. Its documented native `diff`
grouping is explicitly demonstrated rather than described as absent.

## Run from the public repository root

```text
python -m pip install .
python -m pip install -r benchmarks/workflow_comparison/requirements.txt
python benchmarks/workflow_comparison/run_comparison.py --out workflow-replay
python benchmarks/workflow_comparison/check_baseline_scope.py --output baseline-scope-replay.json
```

The workflow command needs the committed published records and priority-encoder
mapping records. It reruns decisions, checks and two scale scenarios in a fresh
directory; it does not resynthesize HDL. See `../priority_encoder_mapping/README.md`
to reproduce that upstream step. Existing output directories are refused.

## Direct accepted comparison

```text
python -m radpareto compare benchmarks/workflow_comparison/results/inputs/set_subset_ambiguous.json --limit cells=40 --limit period_ns=24.57002457002457 --output accepted-review.json
python benchmarks/workflow_comparison/conventional.py benchmarks/workflow_comparison/results/inputs/set_subset_ambiguous.json --limit cells=40 --limit period_ns=24.57002457002457 --output conventional-review.json
```

The period cap is the represented reciprocal of 40.7 MHz. Four source-defined
SET-suppression architectures are in this investigation scope: DF-TMR-DFF-1.28,
DF-TMR-DFF-2.56, DF-TMR-DFF-5.12 and DCLR-TMR-DFF. The architecture restriction is an
analyst's legitimate design-family question, **not** a verified equivalence of
radiation protection. Their cost-only frontier has DF1.28 and DCLR. At these caps,
DF1.28 is `uncertain` and DCLR is `definitely_feasible`; the feasible-only nominal
frontier contains DCLR. At 35 VersaTiles/bit and 40 MHz, DF1.28 is the feasible-only
frontier member; at 40 VersaTiles/bit and 42 MHz it is DCLR.

An uncertain result means the supplied interval crosses a requirement. The user
should inspect the limiting objective and source locator, check units, rounding
and common implementation conditions, and obtain justified tighter bounds or new
implementation observations if stronger acceptance is required. Observed extrema
from three runs do not establish a confidence bound or guarantee a future run.
Protection-aware selection additionally needs appropriate fault-model, scope and
supporting experimental/model evidence; architecture membership is insufficient.

## Informative refusal

```text
python -m radpareto compare benchmarks/workflow_comparison/results/inputs/context_mismatch.json --output refusal-review.json
```

This controlled diagnostic fixture changes the last record's device declaration.
Expected status: `refused`, reason code `CONTEXT_MISMATCH`, field `device`, record
`DCLR-TMR-DFF`. Recover the correct metadata from its source or partition genuinely
different contexts; do not simply relabel records to force acceptance. Requiring
verified protection for the unmodified published records separately yields
`PROTECTION_UNVERIFIED`. The baseline also reports the same refusal categories
using explicit custom rules. Its CLI exits 0 when it successfully writes a refusal
payload; RadPareto's CLI additionally returns exit 2 for a refusal. The retained
commands record this interface convention without scoring it as a decision error.

## What is evaluated

The 23 cases comprise two full six-design comparisons, four architectural-subset
decisions, four equality/adjacent-representable-value probes, one protection refusal,
seven controlled identity/context/semantics/interval/tie diagnostics, four
synthesis-mapping decisions and one synthesis context mismatch. Artificial probes
are tagged in `specifications.json`; they are not additional engineering observations.
Results cover agreement on status and reason-code sets, nominal/certain screening
frontiers, per-limit and overall interval feasibility, feasible-only frontiers,
input hashes and accepted source-evidence payloads. Exact diagnostic wording/order,
all possible malformed inputs, arbitrary-precision arithmetic, runtime, user time
and human usability are outside this benchmark. The custom baseline explicitly
refuses integers above 2**53 to avoid hidden float coercion.

All 23 current cases agree; 15 comparisons are accepted and eight refused. All 15
accepted source-evidence payloads agree. Two accepted/refused CLI tasks are run
through both implementations (four command executions). These checks demonstrate
that the same contract can be implemented conventionally. RadPareto's practical
contribution is packaging the domain workflow and its certificates for reuse, not
new Pareto mathematics, an exclusive capability, or measured time saving. This is
a developer-run functional exercise, not independent human reproduction.

The separate numeric-scope script has nine artificial adapter checks, including
positive and negative 401-digit integers, the supported integer boundary,
nonfinite numbers and booleans. These guard against accidental exceptions during
integer-to-float validation; they do not change the 23-case comparison denominator
or add engineering observations. Conditional certificates are not implemented in
the baseline: the following scale analysis exercises RadPareto only, and adding
equivalent certificates to a conventional workflow would require more custom code.

## Conditional scales

At 35 VersaTiles/bit and 40 MHz, scenario A widens bounds by 1 cell/bit and 0.1 ns per
unit t. Scenario B fixes resource counts and widens period by 0.5 ns per unit t.
They are labelled analyst-selected stress scenarios, not estimates from the paper.
DF1.28's timing feasibility boundary changes from t=3.561042929666307 to
t=0.7122085859332614; equality remains included. DCLR's resource-infeasible class
changes to uncertain at t=2 in A, but remains resource-infeasible for all t in B.
The scenario choice therefore changes both a numerical threshold and whether a
transition exists. Choose scales from the decision's permitted accounting changes
or externally justified perturbation bounds, record their units and rationale,
and never compare t across studies with different scales as intrinsic robustness.

Exact numerator/denominator strings in the JSON certificates are authoritative
for represented Python inputs. Decimal values in `scale_sensitivity.csv` are
display approximations. This is distinct from exact printed-source decimal
reference calculations and finite engine evaluations.

`results/` retains inputs, all outputs, case specifications, comparator results,
source-evidence checks, CLI receipts, the native grouping probe, two scale
certificates and dependency versions. No publication manuscript or figure is here.
