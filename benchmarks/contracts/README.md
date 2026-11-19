# Matched comparison-contract scenarios

These 60 original constructed scenarios test a declared software contract.
There are 27 valid controls and 33 expected refusals. Expected frontiers and
constraint classifications were specified by a separate AI agent that
read the interface/semantics but did not inspect or execute the engine. A second
agent implemented the checked pandas reference without seeing the engine or
expected answers. The controller coordinated the work and had seen the engine;
this is not full blinding or independent human review.

The case file was frozen before evaluation with SHA-256
`781d2a45282a53be1e2115744e89ecc3b60d46e6e93ea20756f50170f78380b4`.
Source fixtures live in `source_records.json`. Intentional invalid provenance
and schema examples are tests; they do not describe actual experiments.

## Reproduce

From the repository root, with Python 3.11 or 3.12:

```sh
python -m pip install . -r benchmarks/contracts/requirements-reference.txt
python -m unittest discover -s benchmarks/contracts -p test_reference.py -v
python scripts/run_contract_study.py --cases benchmarks/contracts/cases.json --baseline benchmarks/contracts/tabular_reference.py --engine-root . --output study-output --performance
```

The output directory must be new: the runner never overwrites an earlier study.
Omit `--performance` for correctness-only checks. Compare expected sets without
regard to order. Refusal cases are scored on eligibility; valid cases also
require matching nominal/interval sets, feasibility and constrained candidates.

## Retained results and interpretation

RadPareto and the fully checked reference each matched all 60 complete expected
decisions. Neither incorrectly refused a valid control or accepted a refusal
case. The nominal-only ablation accepted all 27 valid controls and matched their
nominal frontiers, but accepted 19 of the 33 cases requiring refusal: its status
agreement was 41/60. It deliberately omits compatibility/protection and interval
rules. It is not a fair stand-in for competent pandas use or a careful analyst.

The runner retains a mechanical full-output count for the ablation, but its
missing interval/feasibility outputs are deliberately unavailable. Do not treat
that count as comparable full-feature accuracy. Use status decisions and the
documented capability omissions instead. These are purposive related cases,
not a random population: no population accuracy, confidence interval, human
time-saving or radiation-performance claim follows.

The original reference 1.0.0 and its initial outcomes are retained. After its
first freeze and the controller's initial evaluation, the reference agent
independently found that pandas could coerce a mixed integer/float limit Series,
losing a large integer boundary above 2**53. Reference 1.0.1 explicitly retains
object dtype and adds a regression test. The agent had not inspected challenge
answers/results when making that correction. Both versions matched the same
60 cases; the correction is an additional regression, not a new held-out win.

Local timing used synthetic all-trade-off sets of 8, 32 and 128 alternatives,
two warm-ups and seven repetitions with alternating method order. It includes
in-process validation and comparison, excluding imports, startup and JSON file
loading. Raw times, medians/ranges, environment and hashes are retained. This
compares two particular implementations, not all pandas implementations; it
measures elapsed wall-clock time for the in-process calls, not human workflow efficiency. Timing is
environment-dependent and should not be expected to match byte for byte.

The reference's optional pandas dependencies do not become engine dependencies.
See the main README for the dependency-free core and its physical-scope limits.
