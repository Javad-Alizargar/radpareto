# Constructed transformation checks

These original fixtures test explicit properties of the comparison API. They are not observed FPGA measurements, human tasks or representative error samples.

There are 120 base cases: four layouts (mixed, ordered chain, trade-off and ties), three record counts (3,8,16), two objective counts (2,3) and five fixed seeds. Six changes test record order, positive objective rescaling, common objective translation, interval widening, upper-limit relaxation and one-record device mismatch. Expected outcomes are invariant sets/classes, monotone changes or context refusal as appropriate. The evaluator also verifies that its 840 base/transformed calls do not mutate the caller's records. Cases and generator hashes were frozen before first execution; local chronology is not independent public preregistration.

The separate response-surface fixture uses coordinates (20,40),(22,50),(30,30). Prescribed endpoint widening t=0,...,6 and first-objective limits19,...,35 use quarter-unit steps. Direct integer-quarter calculations provide an alternative oracle for all 1625 cells. These bounds are a what-if model, not confidence intervals or experimental uncertainty.

From the repository root, with the package installed:

```sh
python scripts/evaluate_properties.py --cases benchmarks/properties/cases.json --engine-root . --output property-output-new
```

An existing output directory is refused. Results include all projected decisions, property outcomes, input-nonmutation checks, surface cells, failures and hashes. A nonzero exit means at least one check failed. No successful output count certifies correctness for arbitrary inputs.

`generator_frozen.py` preserves the exact pre-execution generator source identified in `freeze.json`. Running it from its saved location creates a new `frozen/` subdirectory; it never overwrites an existing one. Its cases/source bytes are deterministic, while the freeze timestamp and generator filename location are operational metadata. `response_surface_source.json` was separately frozen before the first evaluation, as recorded by its own hash in retained results.

The cases and evaluation were AI-assisted engineering work. Separate construction and later review do not imply blinded human validation. No proprietary or manuscript material is required to execute these tests.
