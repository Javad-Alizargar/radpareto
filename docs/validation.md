# Validation scope

The alpha's tests exercise data validation, compatible grouping, Pareto ties and trade-offs, interval dominance, constraints and explicit refusal. The benchmark adapter is tested against actual generic synthesis outputs and deliberate unsupported netlist cases. Numerical decisions are also checked by an independently expressed enumeration baseline.

Run `python scripts/evaluate_contract.py` after installing the package. Its 58
checks include 40 seeded interval cases evaluated by exhaustive endpoint-corner
enumeration. This is an alternative software oracle, not an external human
review or a complete proof for arbitrary inputs. The 46 unit/regression tests
are run with `python -m unittest discover -s tests -v`.

Original synthetic fixtures are software tests, not observed radiation data. Original HDL fixtures are new executable logic examples, not replications of Smith's designs. Generic synthesis validates an import workflow and logic metrics; it does not validate flash-device timing or physical radiation tolerance.

Independent installation/use and domain review could strengthen evidence of practical utility. They are not asserted here as blanket journal requirements. A verified mapped flash implementation would be needed for any flash-specific performance claim. Passing automated tests does not establish novelty or publication readiness.

This release contains original fixtures and makes no historical-table replication
claim. The public package can be exercised with entirely original examples.
