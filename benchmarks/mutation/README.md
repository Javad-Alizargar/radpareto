# Bounded semantic mutation study

This package replays twelve purposively selected source defects against four existing diagnostic families. Eleven defects were detected; M01, which changes tie handling, survived these selected families. The unmodified control passed. All twelve mutants have separate predeclared activation examples showing non-equivalence; those examples are excluded from the detection scores. No equivalent mutant was excluded.

From the repository root, with Python 3.11 or later and a fresh output directory:

```sh
python benchmarks/mutation/replay.py --output mutation-replay
```

Only the standard library is needed. The replay verifies and copies all 116 frozen source/input files, executes the unchanged frozen harness in isolated subprocesses, and compares the complete diagnostic matrix with the retained result. It never modifies the installed production package. Deliberately incorrect variants are research fixtures, not replacement implementations.

## Fixed scope

The study was locally frozen on 20 November 2026 at 16:05:20 UTC, before mutant execution. Selection was informed by production source and existing tests; this is not external preregistration or random defect sampling. `frozen_study/freeze.json` binds exact operators, protocol, copied baseline modules, unchanged evaluators, cases, expected decisions and activation examples. The baseline package is 0.2.0a1; its comparison and stability modules are byte-identical to release 0.2.1a1.

The scored families are 720 metamorphic properties, 1,625 quarter-grid cells, 66,960 certificate case/probe decisions and nine existing stability unittest methods. Comparison-only families cannot execute stability-module mutations; those cells are not assessed. Runtime errors are separate from mismatched decisions. The zero-scale mutant produces 47 certificate-construction errors, leaving 8,742 probes unassessed, and three focused-test errors. The remaining 58,218 certificate probes for that mutant match. Family totals and denominators differ and are not comparable accuracy estimates.

`retained/` contains the original compact matrix, summary, variant overview and per-variant family summaries. Full error traces and fresh outputs are regenerated locally by replay. One survivor indicates a blind spot in these four selected families; it does not claim that the complete project core/adversarial suite misses tie handling. Results do not establish general correctness, unknown real-fault detection, physical reliability or radiation effectiveness.

All code and original constructed fixtures in this directory are MIT-licensed. No manuscripts, publication figures, literature copies or private review material are included.
