# Exact endpoint oracle for stability certificates

The original cases and direct expected endpoint decisions were frozen before evaluating the new stability implementation. The oracle uses direct inequalities at prescribed rational values, rather than reproducing the analytical breakpoint formula.

There are360 two-record cases, spanning one/two/three objectives, separated/tied/overlapping/mixed integer boxes, scales0to3 and upper limits0to20. Fixed rational endpoints k/d for k=0,...,24 and d=1,...,6 are augmented with adjacent midpoints and a trailing t=25. Deduplication gives186 probes per case, or66,960 case/probe decisions. The selected integer domain's possible finite breakpoints are covered; this finite workload is not a proof for arbitrary real-valued inputs.

`cases.json`, `expected.json`, `generator_frozen.py` and `freeze.json` are original validation artifacts. Rational numbers use numerator/denominator fields and are evaluated using exact arithmetic. The cases and nearby probes are dependent and are not a population-accuracy sample. An expected-class count must not be interpreted as an empirical probability of scientific error or physical failure.

The constructor and implementation were assigned to separate AI-assisted roles with a shared specification. The local freeze and source hashes document artifacts and order, not independent public preregistration, source authenticity or external human review. Only the fixed original inputs/expected decisions and software evaluator are public; private manuscript reviews and publication artwork are excluded.
