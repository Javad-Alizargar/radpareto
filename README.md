# RadPareto

RadPareto checks whether research evidence can be compared before computing resource trade-offs. It preserves source locations, units, denominators, implementation context and uncertainty bounds. Its Python library and command line interface return explanations when records are incompatible.

This is an **alpha research prototype**. It compares stated costs, not physical radiation hardness. The initial synthesis examples use generic logic cells and logic depth; depth is not propagation time or maximum clock frequency. There is no verified flash-device backend in this version.

## Install and try

Python 3.11 or later is required. The comparison engine has no runtime dependencies. From a copy of this repository:

```sh
python -m venv .venv
# Windows PowerShell
.venv/Scripts/python -m pip install .
.venv/Scripts/radpareto validate examples/rounded_costs.json
.venv/Scripts/radpareto compare examples/rounded_costs.json --limit area_ratio=3.5
# Linux/macOS: use .venv/bin/python and .venv/bin/radpareto
```

The original synthetic example deliberately contains rounded costs. Its nominal cost/time ranking differs from what can be guaranteed over the representation intervals. Bounds from decimal rounding are not confidence intervals.

```sh
radpareto compare examples/incompatible_units.json
radpareto compare examples/rounded_costs.json --require-verified-protection
```

These commands are expected to refuse comparisons: the first mixes units and the second lacks verified protection evidence. Nonzero exit status is intentional. A refusal is a useful result and includes reasons.

## Outputs and interpretation

- `nominal_front` contains designs not dominated at the supplied central values.
- `not_certainly_dominated` retains designs not provably dominated over the full input intervals. It is not a guarantee that every retained design is optimal.
- Feasibility distinguishes definite compliance, definite violation and uncertain compliance with upper cost limits.
- Source hashes are declared lineage identifiers. The engine validates their format, not the scientific accuracy or remote existence of sources. Verify local source hashes through the reproduction manifest.
- Matching context labels are necessary checks, not proof that a comparison is scientifically valid. A researcher must review the labels and physical assumptions.

All objectives are minimized. Different baselines, devices, toolchains, timing corners, source kinds, units or denominators are not silently merged. Protection-aware comparison requires compatible supplied evidence; no result establishes space qualification.

## Stability analysis

Version 0.2.0a1 adds exact rational transition certificates for a prescribed additive widening of each objective's bounds. Provide an explicit nonnegative scale for every objective. For example:

```sh
radpareto stability examples/stability.json --scale cost_0=1 --scale cost_1=1 --limit cost_0=25
```

The [stability guide](docs/stability.md) explains endpoint inclusion, rational JSON fields and the 128-record limit. This is conditional sensitivity analysis; scales do not estimate experimental uncertainty.

## Development and reproduction

```sh
python -m unittest discover -s tests -v
```

See [comparison semantics](docs/semantics.md), [validation scope](docs/validation.md) and the [original HDL benchmark instructions](docs/open_benchmarks.md) when reproducing the synthesis cases. A separate tool environment is needed for synthesis; the comparison engine itself stays dependency-free.

The [matched contract study](benchmarks/contracts/README.md) includes 60 original
scenarios and an independently implemented checked pandas reference. Both match
all expected decisions; this supports reproducible implementation of the stated
contract, not a claim of a new optimization algorithm or measured human benefit.

The expanded validation includes 720 metamorphic properties, 1,625 response-surface cells, 66,960 finite certificate/oracle comparisons and [four external HDL configurations](docs/external_benchmarks.md). These are dependent constructed checks, not independent research observations or measured laboratory benefit.

This repository contains original code, original demonstration fixtures and attributed MIT-licensed external HDL. Manuscripts, publication artwork, copied papers, credentials and private scientific review files are excluded. A future archived release will receive a verified DOI; none has been assigned to this alpha.
