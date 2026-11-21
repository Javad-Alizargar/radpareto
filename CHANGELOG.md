# Changes

## 0.3.0

- Use one decimal-frequency conversion path for published source values and requirements, correcting two one-ULP equality decisions at 40.578 and 40.975 MHz. The original 72 scenario classifications remain unchanged.
- Add the exact-reference decision atlas (532 regions, 3,192 checked design/representative decisions), source-summary margins and an explicit endpoint-only rounding sensitivity analysis. Binary64 limitations remain documented.
- Add six attributed Table 11 timing values in a separate implementation context. Preserve different summary statistics and refuse a combined comparison.
- Publish a portable independent Decimal checker, numerical outputs, input/output hashes and replay commands. Run atlas reproduction and checking in the Python 3.11/3.12 Linux/Windows CI matrix.
- Expand the current unit/regression suite to 79 test methods, including conversion, comparison and web request-boundary regressions. Historical 0.2.1a1 timing and validation results and the frozen 0.2.0a1 mutation study retain their original scope and versions.

## Documentation correction (21 November 2026)

- Correct the validation guide's unit/regression-test count to 58 and distinguish the published-summary reanalysis from hardware reproduction.
- Software remains 0.2.1a1; no source, test, input or numerical-result file changes.

## 0.2.1a1

- Add a source-attributed six-design ProASIC3 cost example, all 72 budget decisions, architecture-subset screens and exact conditional boundaries.
- Preserve a frozen twelve-mutant semantic-defect study: eleven detected by four selected existing families, one non-equivalent survivor, with runtime errors and unassessed probes distinguished.
- Retain refreshed comparison, property, certificate and output-volume results with source hashes and replay commands.
- Keep comparison and stability semantics unchanged from 0.2.0a1; add reproducibility inputs and documentation.

## 0.2.0a1

- Add explicit-scale stability API/CLI with exact rational transitions, boundary inclusion and a 128-record limit.
- Preserve JSON integer CLI limits above 2**53 instead of converting them to floating point.
- Add frozen finite endpoint oracle, metamorphic properties and full response surface with retained evaluators/results.
- Add four attributed external HDL configurations and executable structural/fault-free checks.
- Preserve the original matched reference and challenge; both checked methods still match all 60 decisions.

## 0.1.0a1

Initial evidence contract, closed-box comparison, restricted Yosys importer, original synthesis fixtures and checked-reference study.
