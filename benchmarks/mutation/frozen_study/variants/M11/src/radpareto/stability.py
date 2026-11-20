"""Exact boundaries for a declared additive interval-widening model.

Thresholds are conditional on supplied evidence and scales, not probabilities.
Fraction(float) preserves the represented binary value rather than interpreting
its printed decimal as an exact measured number. Rational JSON components are
decimal strings so a consumer need not round large integers through binary64.
"""
from fractions import Fraction
from radpareto.compare import compare
from radpareto.validation import EvidenceError, _number

MAX_STABILITY_RECORDS = 128


def _rational(value):
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _refused(code, message, **details):
    return {"status": "refused", "reasons": [{"code": code, "message": message, **details}],
            "dominance_certificates": [], "constraint_certificates": []}


def stability(records, scales, limits=None, require_verified_protection=False):
    """Certify when initially certain decisions survive common widening t>=0.

    Every objective must have an explicit nonnegative scale, applied to all
    records. Bounds become [max(0, lower-t*scale), upper+t*scale]. Only initially
    certainly dominant ordered pairs are reported: widening cannot create them.
    Per-limit certificates describe the initial definite class until it changes
    to uncertain. An initially uncertain class stays uncertain. None denotes no
    finite transition; equality inclusion is explicit for every finite boundary.
    Cost-only eligibility and protection declarations follow compare().
    """
    if isinstance(records, list) and len(records) > MAX_STABILITY_RECORDS:
        return _refused("STABILITY_RECORD_LIMIT", "Stability analysis is limited to 128 records",
                        records=len(records), maximum=MAX_STABILITY_RECORDS)
    base = compare(records, limits=limits, require_verified_protection=require_verified_protection)
    if base["status"] != "accepted":
        return {"status": "refused", "reasons": base["reasons"], "comparison": base,
                "dominance_certificates": [], "constraint_certificates": []}
    names = sorted(records[0]["metrics"])
    if not isinstance(scales, dict) or set(scales) != set(names):
        return _refused("INVALID_STABILITY_SCALES", "Supply exactly one nonnegative scale for every objective",
                        expected_objectives=names)
    try:
        for name in names:
            _number(scales[name], f"scales.{name}")
    except EvidenceError as exc:
        return {"status": "refused", "reasons": [exc.as_dict()],
                "dominance_certificates": [], "constraint_certificates": []}
    scale = {n: Fraction(scales[n]) for n in names}
    lower = {r["id"]: {n: Fraction(r["metrics"][n]["lower"]) for n in names} for r in records}
    upper = {r["id"]: {n: Fraction(r["metrics"][n]["upper"]) for n in names} for r in records}
    pairs = []
    for a in records:
        for b in records:
            aid, bid = a["id"], b["id"]
            if aid == bid:
                continue
            gaps = {n: lower[bid][n]-upper[aid][n] for n in names}
            if not all(v >= 0 for v in gaps.values()) or not any(v > 0 for v in gaps.values()):
                continue
            candidates = {n: gaps[n]/(2*scale[n]) for n in names if scale[n] > 0}
            threshold = min(candidates.values()) if candidates else None
            included = (any(gaps[n]-2*scale[n]*threshold > 0 for n in names)
                        if threshold is not None else None)
            pairs.append({"dominant_id": aid, "dominated_id": bid,
                          "transition_t": _rational(threshold) if threshold is not None else None,
                          "initial_relation_includes_boundary": included,
                          "limiting_objectives": [n for n in names if n in candidates and candidates[n] == threshold],
                          "initial_separations": {n: _rational(gaps[n]) for n in names},
                          "interpretation": "Initially certain dominance holds before the transition and at it only when inclusion is true; null means no finite transition."})
    constraints = []
    for r in records:
        rid = r["id"]
        for name, value in sorted(base["limits"].items()):
            limit = Fraction(value)
            initial = base["feasibility"][rid]["per_limit"][name]
            threshold, included = None, None
            if scale[name] > 0 and initial == "definitely_feasible":
                threshold, included = (limit-upper[rid][name])/scale[name], True
            elif scale[name] > 0 and initial == "definitely_infeasible":
                threshold, included = (upper[rid][name]-limit)/scale[name], False
            constraints.append({"record_id": rid, "objective": name, "initial_status": initial,
                                "transition_t": _rational(threshold) if threshold is not None else None,
                                "initial_status_includes_boundary": included,
                                "status_after_transition": "uncertain" if threshold is not None else initial})
    return {"status": "accepted", "reasons": [], "comparison": base,
            "model": {"parameter": "t >= 0", "lower": "max(0, lower - t*scale)", "upper": "upper + t*scale",
                      "scales": {n: _rational(scale[n]) for n in names},
                      "arithmetic": "Exact rational arithmetic on represented Python integers/binary floats; rational JSON components are decimal strings",
                      "record_limit": MAX_STABILITY_RECORDS,
                      "assumption": "Scales are explicit user assumptions, not measured uncertainty or confidence levels"},
            "dominance_certificates": pairs, "constraint_certificates": constraints,
            "warnings": ["Certificates apply only to the declared common per-objective additive widening model.",
                         "No correlation, statistical probability, physical protection or optimum guarantee is inferred.",
                         "Null transition means no finite transition for the initial relation/class; pair omission means no initial certain dominance.",
                         "Decode rational numerator/denominator strings with exact integer arithmetic; decimal renderings are not authoritative thresholds."]}
