# Validation lineage and scope

Use the exact release commit for execution. A version string is not sufficient:
retain `git rev-parse HEAD`, the dirty-worktree state, command, Python/dependency
versions and source hashes. `python scripts/validation_lineage.py --output
lineage.json` records the available commit and module identities; it does not
claim that tests have run. For a source archive without Git metadata it reports
that the checkout commit is unavailable, rather than inventing one.

| Validation family | Production or historical execution | Exact historical source/release | Interpretation |
|---|---|---|---|
| 79 unit/regression methods; 58 contract checks | Run against the installed/current 0.4.0 checkout | Previous 0.3.0 release: `4953ab6aa46794f41b0eb069ee8eade5014eb5ae` | Includes core, CLI, web, reciprocal-conversion and importer regressions; inspect actual run results |
| Six-design source analysis and direct-decimal atlas | Re-run with `--engine-src src` against current production modules | 0.3.0: `4953ab6aa46794f41b0eb069ee8eade5014eb5ae` | 72 budget scenarios; 3,192 design/region representative checks; 516 precision checks. Finite conformance, not continuum or hardware validation |
| 60-scenario checked contract; 720 properties; 1,625 response-surface cells; 66,960 certificate probes | Retained historical results; commands can execute fresh current-engine replays | 0.2.1a1: `5485414a9ba3728ffe8526e42b4f27761452871f` | Module hashes justify only bounded semantic continuity; a replay manifest must identify which engine actually ran |
| Twelve-mutant study, four fixed diagnostic families | Always executes its frozen copied sources, even when launched from 0.4.0 | Frozen 0.2.0a1 baseline: `e2df9989c25ad85084adb7d0e50a2cb388f4b881`; study packaged at `5485414a9ba3728ffe8526e42b4f27761452871f` | Original 11/12 detection and M01 survivor remain unchanged; errors, mismatches and unassessed probes remain distinct |
| Existing tie regressions applied to retained M01/M02 | Additional post-study execution of current test methods | Current test source hash and frozen variant hashes recorded by `check_tie_regression.py` | Shows current coverage; not an additional original mutation-study family or revised score |
| Historical local runtime/output-size measurements | Historical only unless explicitly remeasured | 0.2.1a1: `5485414a9ba3728ffe8526e42b4f27761452871f` | Neither source identity nor a successful replay transfers old latency to a new release/machine |
| Original/external generic HDL checks | Fresh synthesis when commands run; retained netlists can also be reimported | Original retained artifacts packaged in the stated historical releases | Structural metrics and fault-free checks; not mapped-device timing or radiation validation |

The comparison and stability algorithms are byte-identical across the frozen
0.2.0a1 control, the 0.2.1a1 study and 0.3.0; the 0.4.0 development retains those
semantics. The executable lineage report checks these identities and records
other current modules separately. The reciprocal-frequency adapter added in
0.3.0 is a distinct component; historical comparison-module identity does not
retroactively validate an earlier mixed frequency-conversion workflow.

The current CLI-version assertion was updated for the version bump. No mutation
operator, frozen input, expected decision or historical scored family was changed.

## Current regression coverage of the historical survivor

M01 changes the strict-improvement requirement from `any(v < w)` to
`any(v <= w)`, so fully equal points incorrectly dominate each other. The
existing `ComparisonTests.test_known_tradeoff_dominance_and_equal_points`
asserts that duplicate equal points both remain on the front and detects M01.
The existing `test_rounding_tie_changes_certainty_not_nominal` verifies that
equality on one objective plus strict improvement on another is nominal
dominance; it detects M02, which incorrectly requires every coordinate to
improve strictly.

```sh
python scripts/check_tie_regression.py --output tie-regression.json
```

This command verifies the frozen source hashes and executes these two existing
test methods in isolated subprocesses against current, M01 and M02 packages.
The two expected mutant assertion failures are evidence that the regressions
detect those defects, not production test failures. Runtime errors would be a
different outcome and cause this check to fail. Neither test was one of the
four originally scored families, so the historical M01 survivor remains a
valid limitation of that experiment.
