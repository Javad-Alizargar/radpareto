# Evidence and comparison semantics

Each record names the design, mitigation method, baseline, implementation, device, tool/version, constraints, timing corner, workload and source kind. Provenance identifies a source URI, SHA-256 digest, location and extraction method. These fields make the inputs auditable; they do not prove the source is trustworthy.

Numerical objectives carry central values, lower/upper bounds, units, denominators and an uncertainty type. NaN, infinity, negative costs, booleans and reversed bounds are invalid. Exact values require equal bounds. Decimal rounding intervals describe limited representation precision, not experimental variability. The initial engine uses closed interval boxes and does not infer correlations, probability distributions or statistical significance.

For minimization, A nominally dominates B if A is no worse on every central objective and better on at least one. A certainly dominates B over the supplied boxes if A's upper bound is no greater than B's lower bound on every objective, with at least one strict inequality. This sufficient conservative rule can retain alternatives that more detailed joint uncertainty models would exclude. It makes no statement about probability of superiority.

An upper limit is definitely satisfied if the objective upper bound satisfies it. A record is definitely infeasible when at least one lower bound exceeds its limit. Otherwise a record may have uncertain feasibility. A frontier over all alternatives is a description, not an instruction to deploy an infeasible design; consult the separate feasibility information and constrained candidates.

Default comparisons reject incompatible contexts. Explicit batch analysis partitions records and reports groups separately; it does not build an overall cross-device ranking. Required unknown context fields do not establish comparability merely because both records say unknown. Baseline versions, stimuli, constraints and cell definitions should be represented by stable identifiers or hashes rather than informal labels when available.

Cost-only comparison is permitted when protection is unverified, with a warning. Requiring verified protection enforces matching supplied fault-model, scope and evidence fields. The software cannot inspect whether the underlying fault campaign actually proves equivalence. Physical SET filtering, common-mode faults, configuration upsets and total ionizing dose are distinct phenomena and must not be collapsed into one evidence label.

The generic synthesis adapter measures Boolean-cell count and combinational cell depth. It cannot convert those into device area, power, nanoseconds, maximum frequency, upset cross-section or mission error rate. A validated physical backend and matching evidence are needed for those claims.
