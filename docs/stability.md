# Conditional stability certificates

`radpareto.stability(records, scales, limits=None, require_verified_protection=False)` first applies the comparison contract. Every objective must have an explicit finite nonnegative scale, shared by the compared records. At dilation `t >= 0`, bounds become `[max(0, lower - t*scale), upper + t*scale]`; central values do not change.

Only initially certain dominance pairs receive certificates. Widening cannot create new certain dominance. `transition_t` contains decimal-string `numerator` and `denominator` fields; `null` means no finite transition. `initial_relation_includes_boundary` is essential: touching in one objective can preserve dominance if another is still strictly separated. Per-limit certificates similarly retain the initial class through an inclusive feasible boundary or strictly before an infeasible boundary. Initially uncertain classes remain uncertain.

Arithmetic uses Python `Fraction`: integers remain exact, while floats are treated as their actual represented binary values. This is not exact decimal arithmetic. Inputs must satisfy the inherited finite-number validator; integers outside its finite binary64 range are refused. CLI JSON integer tokens above 2**53 are preserved; decimal and exponent tokens use binary floating point.

Stability is limited to 128 records. A dominance chain can produce n(n-1)/2 pair certificates, and serialized output can become large. All objectives are minimized. The model does not estimate probability, covariance, confidence, fault coverage or an appropriate uncertainty scale.

From the repository root after installation:

```sh
python scripts/evaluate_properties.py --cases benchmarks/properties/cases.json --engine-root . --output property-replay
python scripts/evaluate_certificates.py --oracle benchmarks/certificates --engine-root . --output certificate-replay --performance
```

Use fresh output directories. The retained results and frozen oracle generators are in those benchmark directories. The oracle directly calculates rational endpoints on a finite grid; it does not reuse the implementation's transition formula. The controller wrote the oracle before implementing the candidate. A separate AI agent reviewed the candidate and added focused edge tests; neither role is independent human peer review.
