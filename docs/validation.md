# Validation scope

The alpha's tests exercise data validation, compatible grouping, Pareto ties and trade-offs, interval dominance, constraints and explicit refusal. The benchmark adapter is tested against actual generic synthesis outputs and deliberate unsupported netlist cases. Numerical decisions are also checked by an independently expressed enumeration baseline.

Run `python scripts/evaluate_contract.py` after installing the package. Its 58
checks include 40 seeded interval cases evaluated by exhaustive endpoint-corner
enumeration. This is an alternative software oracle, not an external human
review or a complete proof for arbitrary inputs. The 46 unit/regression tests
are run with `python -m unittest discover -s tests -v`.

Original synthetic fixtures are software tests, not observed radiation data. Original HDL fixtures are new executable logic examples, not replicas of Smith's unpublished netlists. Generic synthesis validates an import workflow and logic metrics; it does not validate flash-device timing or physical radiation tolerance.

The independent validation still needed for publication includes external installation/use, domain review of comparison rules, a meaningful researcher workflow comparison and a verified flash implementation if a flash-specific claim is retained. Passing automated tests does not establish novelty or publication readiness.

This release contains original fixtures and makes no historical-table replication
claim. The public package can be exercised with entirely original examples.
