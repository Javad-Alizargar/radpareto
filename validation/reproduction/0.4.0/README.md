# AI-assisted reproduction receipt for RadPareto 0.4.0

This is a sanitized record of an automated reproduction exercise conducted on
27 November 2026 using public documentation and inputs. The tested executable
commit is [`eed14559444b9fc3e493ec59d1cc5e37f289f436`](https://github.com/Javad-Alizargar/radpareto/tree/eed14559444b9fc3e493ec59d1cc5e37f289f436).
This receipt was added later as documentation; it does not change that release.

The evaluator was an AI agent in a fresh task context for the initial candidate
exercise. The same evaluator subsequently repeated the tasks against a new
remote clone of the exact release commit. It used the public README, quickstart,
reproduction and semantics documentation, public inputs and CLI help. It did not
consult private manuscript material, other review conclusions or implementation
internals to resolve the tasks. The exact historical AI model/build identifier
was not recorded. This is not an unfamiliar-human study; no human task time,
usability score, adoption or improvement in decision quality was measured.

## Environment and results

The observed environment was Windows 10 build 19045, PowerShell 7.6.9,
Python 3.12.10, pip 25.0.1 and setuptools 84.2.1. A new virtual environment
installed RadPareto 0.4.0 successfully. The package declares no runtime
dependencies. All eight installed module hashes match the tested source
commit; the source checkout was clean after execution.

| Task | Observed result |
|---|---|
| Install the exact commit in a new environment | Environment creation and package installation exited 0. |
| Compare the six published records at 40 cells/bit and 32 MHz | Exit 0; BL-DFF is the nominal and interval-screen frontier. Five designs are definitely feasible; DF-TMR-DFF-5.12 is uncertain on period. |
| Interpret uncertainty using the source row | Independent Decimal arithmetic confirms that the reciprocal observed range crosses 31.25 ns, although the reciprocal mean passes. These are observed ranges, not confidence intervals or future-run guarantees. |
| Regenerate the published records and repeat the comparison | Source analyzer exited 0 with `complete_with_limitations`, 72 budget rows and 12 dominance certificates. Regenerated records and the repeated selected comparison match the bundled-input versions byte for byte. |
| Import two new, explicitly synthetic records | Validation and comparison exited 0. At a cell limit of 12, `fresh_alpha` is definitely feasible and `fresh_beta` is uncertain. This exercises the JSON schema, not automatic CSV conversion or new hardware data. |
| Diagnose an injected context mismatch | Exit 2; `CONTEXT_MISMATCH` names `timing_corner`, `fresh_beta` and reference `fresh_alpha`. |
| Separate the incompatible records using batch mode | Exit 0; two singleton groups, with no cross-group ranking. Batch does not accept budget limits; budget screening requires separate justified comparisons. |
| Require verified protection | Exit 2; six `PROTECTION_UNVERIFIED` reasons. Expected refusals are diagnostic outcomes, not crashes. |

The recorded CLI/API invocations, exit codes, source identifiers and exact
environment are in [receipt.json](receipt.json). Unchanged selected outputs,
the synthetic inputs and the separate Decimal calculation are included here.
[artifact_sha256.csv](artifact_sha256.csv) identifies these public file bytes.
The installed-module check is [checks/installed_source_match.csv](checks/installed_source_match.csv).

## Commands and interpretation

`receipt.json` records the executable invocations with their original relative
working directories. Its `exercise` directory denotes `final_commit/` below
`exercise_parent`, containing
`source/` (the pinned checkout), `.venv/`, `inputs/` and `outputs/`. Logging and
stopwatch wrappers are omitted. To repeat the commands, create a new exercise
directory, clone the pinned commit into `source/`, copy the three bundled
`inputs/` files into its `inputs/`, and create `outputs/`. Select the documented
Python version explicitly. Do not overwrite this receipt's retained outputs.

The inputs preserve their original relative source URI
`inputs/additional_source.csv` and its actual SHA-256. Their intervals and
context-mismatch injection are intentionally synthetic. They demonstrate the
complete documented schema and preserve explicit provenance and protection
fields. An `uncertain` result means the supplied range crosses the requirement;
it calls for better justified bounds or further measurements before making a
stronger claim. A context refusal calls for checking the source declaration,
correcting a genuine transcription error, or keeping different contexts
separate. Do not change a protection flag simply to force acceptance.

## Assistance, corrections and limits

- The machine's bare `python` initially selected Python 2.7.11. The evaluator
  selected `py -3.12` before installation. The release README and quickstart now
  show that Windows launcher explicitly. This was interpreter selection, not a
  package installation failure.
- An initial staging-path typo was inspected and corrected by moving the unused
  copy intact; an attempted cleanup was blocked before execution. The initial
  installation used pip's default external cache. The exact-commit repetition
  used a new remote clone, local temporary/cache directories and `--no-cache-dir`.
- A source-row display initially used column name `design`; inspecting the
  public CSV header corrected it to `structure`. This was an operator query
  correction, not a package/schema failure.
- Batch syntax was obtained through `--help`. The evaluator learned that batch
  has no `--limit` option and does not replace budget comparisons within groups.
- Native subprocess output was not always captured by PowerShell transcription.
  Explicit JSON outputs, run manifests and exit-code receipts retained the
  substantive results. Raw transcripts and private discussions are not published.

The exact-commit repetition retained the earlier candidate evidence and matched
21 comparable output files byte for byte. This is bounded evidence that the
selected public workflow executed and its refusals could be diagnosed. It is
not hardware or irradiation reproduction, protection equivalence, authentication
of publisher data, an exhaustive test, a time-saving claim, or independent human
evidence. Synthesis and CI were not part of this particular exercise.
