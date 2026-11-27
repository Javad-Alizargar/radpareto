# A complete local comparison

Use Python 3.11 or later and start in the root of the pinned RadPareto source
checkout. The core has no runtime dependencies. These commands create an
isolated environment and install the package; they do not require Yosys.

Windows PowerShell (the `python` command may still name an older interpreter):

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install .
.venv/Scripts/python -m radpareto compare benchmarks/published_case/results/records.json --limit cells=40 --limit period_ns=31.25 --output accepted.json
```

Linux/macOS:

```sh
python3 --version  # Must report Python 3.11 or later
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m radpareto compare benchmarks/published_case/results/records.json --limit cells=40 --limit period_ns=31.25 --output accepted.json
```

For the remaining examples, Linux/macOS users replace `.venv/Scripts/python`
with `.venv/bin/python`. Select a suitable installed interpreter before creating
the environment; do not rely on an unqualified `python` command's version.

The bundled input contains six designs from one published study, not six
independent studies. Its cells are VersaTiles per logic bit. Its period cost
is the reciprocal of reported maximum-frequency summaries; 31.25 ns is the
32 MHz requirement. The observed timing range is from three reported runs,
not a confidence interval or a guarantee about future runs. This example
screens costs across all six records; it does not make every architecture
admissible for a particular engineering project.

Selected output fields are:

```json
{
  "status": "accepted",
  "nominal_front": ["BL-DFF"],
  "front_scope": "all_input_records_before_limits",
  "feasibility": {
    "DF-TMR-DFF-5.12": {
      "status": "uncertain",
      "per_limit": {"cells": "definitely_feasible", "period_ns": "uncertain"}
    }
  }
}
```

This is a selected excerpt, not the complete result. The other five records
are definitely feasible under the supplied bounds. The result also contains
all records' provenance, metric semantics, context, warnings, and a `replay`
envelope with the installed version, input SHA-256 and options. Preserve the
complete output rather than only the displayed frontier. Acceptance means
the declared comparison premises passed software checks; it is not source
authentication, proof of protection equivalence, or hardware validation.

## What an uncertain result means

`uncertain` means a supplied interval straddles a stated budget. Inspect the
specific `per_limit` field and source locator first. A defensible next step
is to retain a definitely feasible candidate within the independently
justified admissible set, or obtain evidence that resolves the crossing.
For published three-run summaries, that may mean the individual runs and
their conditions, a corrected source transcription, or additional matched
implementation/measurement evidence. Additional runs do not automatically
turn extrema into confidence or future-run bounds. If statistical coverage
is required, specify and justify an appropriate statistical design outside
this box-screening calculation. Change a budget only when the engineering
requirement itself justifies the change; do not relabel uncertain as a pass.

The full-set BL cost frontier does not assert protection equivalence. A
restricted candidate set must have an external engineering justification.
Architecture membership by itself is insufficient evidence of equivalent
radiation response.

## An informative refusal

```sh
.venv/Scripts/python -m radpareto compare benchmarks/published_case/results/records.json --limit cells=40 --limit period_ns=31.25 --require-verified-protection --output refused.json
```

The expected exit status is 2. The result has `status: refused` and reason
code `PROTECTION_UNVERIFIED` for each supplied unverified declaration. This
refusal is expected behavior. Inspect the explanations rather than treating
nonzero exit status as a crash. Do not change a protection flag merely to
obtain acceptance: the required model, scope and evidence must be justified.
To compare costs alone, explicitly omit the protection requirement and keep
the output's cost-only warning.

`examples/incompatible_units.json` provides a second refusal example. Its
metric semantics differ; normalize only when the source supports the
conversion and denominator, then keep that transformation in provenance.
For genuinely different implementation contexts, use `radpareto batch`
to obtain separate groups rather than a combined ranking.

## Minimal complete input and API

`examples/minimal_bounded.json` is a complete one-record, one-objective
synthetic schema example, linked to the original fixture in
`examples/minimal_bounded_source.csv`. It is a software example, not an
FPGA observation. Its essential numeric fields are:

```json
"metrics": {
  "cells": {
    "value": 10, "lower": 9, "upper": 11,
    "unit": "abstract_cells", "denominator": "absolute",
    "uncertainty_kind": "bounded"
  }
}
```

The complete bundled file also supplies required identity, context,
provenance and protection fields. Omitting those fields is invalid. Run:

```sh
.venv/Scripts/python -m radpareto compare examples/minimal_bounded.json --limit cells=10
```

Its expected classification is `uncertain`. This minimal Python call uses
the same engine on the actual published example:

```python
import json
from pathlib import Path
from radpareto import compare, validate_document
from radpareto.units import period_ns_from_mhz

path = Path("benchmarks/published_case/results/records.json")
records = validate_document(json.loads(path.read_text(encoding="utf-8")))
result = compare(records, limits={"cells": 40,
                                  "period_ns": period_ns_from_mhz("32")})
print(result["feasibility"]["DF-TMR-DFF-5.12"])
```

The CLI additionally captures the file hash and invocation in its replay
envelope. API users should retain input-file hashes, code version and options
in their own execution record. Prefer the shared reciprocal helper for
non-exact frequency conversions; it gives consistent represented inputs,
not arbitrary-precision decimal ordering.

## Source and representation review

The schema distinguishes structural validity from comparison eligibility.
Required context includes baseline, device, tool/version, implementation,
constraints, timing corner, workload and source kind. Metric names, units,
denominators and uncertainty labels must agree. A valid source SHA-256 format
does not prove that its locator or physical interpretation is correct.
Compare the recorded hash with the actual source file and review the source.

For exactness, distinguish the printed-decimal reference analysis, ordinary
binary64 engine values, and rational stability certificates for the values
actually represented. A widening scale is a user-declared scenario in units
of its objective per unit of widening. Thresholds cannot be compared across
different scale definitions as if they were intrinsic device properties.
See [stability](stability.md) and [reproduction](reproduction.md).
