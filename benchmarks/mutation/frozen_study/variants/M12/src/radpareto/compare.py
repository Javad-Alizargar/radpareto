"""Conservative comparison of compatible, explicitly minimized cost metrics."""
import json
from .validation import EvidenceError, _number, is_unknown, validate_document


def _reason(code, message, **details):
    return {"code": code, "message": message, **details}


def _empty(reasons):
    return {"status": "refused", "reasons": reasons, "nominal_front": [],
            "not_certainly_dominated": [], "feasibility": {},
            "definitely_feasible_nominal_front": [], "warnings": []}


def comparison_key(record):
    """Explicit context and cost semantics used to partition a batch."""
    return json.dumps({"design": record["design"], "context": record["context"],
        "metric_semantics": {k: {f: v[f] for f in ("unit", "denominator", "uncertainty_kind")}
                             for k, v in record["metrics"].items()}}, sort_keys=True)


def _dominates(a, b, names, box=False):
    x = [a["metrics"][n]["upper" if box else "value"] for n in names]
    y = [b["metrics"][n]["lower" if box else "value"] for n in names]
    return all(v <= w for v, w in zip(x, y)) and any(v < w for v, w in zip(x, y))


def _front(records, names, box=False):
    return [r["id"] for r in records if not any(
        a["id"] != r["id"] and _dominates(a, r, names, box) for a in records)]


def compare(records, limits=None, require_verified_protection=False):
    """Compare minimized costs, refusing unknown or incompatible evidence.

    Interval dominance is conditional on supplied bounds, not a guarantee
    about physical outcomes. The unconstrained front always uses all records.
    Feasible-only decisions are separately and explicitly identified.
    """
    try:
        records = validate_document({"schema_version": "1.0", "records": records})
    except EvidenceError as exc:
        return _empty([exc.as_dict()])
    if not isinstance(require_verified_protection, bool):
        return _empty([_reason("INVALID_OPTION", "require_verified_protection must be boolean")])
    reasons = []
    ref = records[0]
    names = sorted(ref["metrics"])
    for r in records:
        for key, value in r["context"].items():
            if is_unknown(value):
                reasons.append(_reason("UNKNOWN_CONTEXT", "Required context is unknown", record=r["id"], field=key))
        for key in ("design", "method"):
            if is_unknown(r[key]):
                reasons.append(_reason("UNKNOWN_IDENTITY", "Design/method identity is unknown", record=r["id"], field=key))
        for name, m in r["metrics"].items():
            for key in ("unit", "denominator"):
                if is_unknown(m[key]):
                    reasons.append(_reason("UNKNOWN_METRIC_SEMANTICS", "Metric interpretation is unknown", record=r["id"], metric=name, field=key))
        for key in ("source_uri", "locator", "extraction"):
            if is_unknown(r["provenance"][key]):
                reasons.append(_reason("UNKNOWN_PROVENANCE", "Source location or extraction is unknown", record=r["id"], field=key))
        if r["design"] != ref["design"]:
            reasons.append(_reason("DESIGN_MISMATCH", "Different designs cannot share a cost frontier", record=r["id"], reference=ref["id"]))
        for key in ref["context"]:
            if r["context"][key] != ref["context"][key]:
                reasons.append(_reason("CONTEXT_MISMATCH", "Comparison context differs", record=r["id"], reference=ref["id"], field=key))
        if set(r["metrics"]) != set(names):
            reasons.append(_reason("METRIC_SET_MISMATCH", "Objective names differ", record=r["id"]))
        else:
            for n in names:
                for key in ("unit", "denominator", "uncertainty_kind"):
                    if r["metrics"][n][key] != ref["metrics"][n][key]:
                        reasons.append(_reason("METRIC_SEMANTICS_MISMATCH", "Metric semantics differ", record=r["id"], metric=n, field=key))
        if require_verified_protection:
            p = r["protection"]
            if p["status"] != "verified_within_model" or any(is_unknown(p[k]) for k in ("fault_model", "scope", "evidence_uri")):
                reasons.append(_reason("PROTECTION_UNVERIFIED", "Protection-aware comparison requires explicit model evidence", record=r["id"]))
            for key in ("fault_model", "scope", "evidence_uri"):
                if p[key] != ref["protection"][key]:
                    reasons.append(_reason("PROTECTION_CONTEXT_MISMATCH", "Protection evidence conditions differ", record=r["id"], field=key))
    if limits is None:
        limits = {}
    if not isinstance(limits, dict):
        reasons.append(_reason("INVALID_LIMITS", "Limits must be an objective-to-number object"))
    else:
        for key, value in limits.items():
            if key not in names:
                reasons.append(_reason("UNKNOWN_LIMIT_METRIC", "Limit refers to an absent objective", metric=str(key)))
            try:
                _number(value, f"limits.{key}")
            except EvidenceError as exc:
                reasons.append(exc.as_dict())
    if reasons:
        return _empty(reasons)
    feasible = {}
    for r in records:
        states = {n: ("definitely_infeasible" if r["metrics"][n]["lower"] > bound else
                      "definitely_feasible" if r["metrics"][n]["upper"] <= bound else "uncertain")
                  for n, bound in limits.items()}
        status = ("definitely_infeasible" if "definitely_infeasible" in states.values() else
                  "uncertain" if "uncertain" in states.values() else "definitely_feasible")
        feasible[r["id"]] = {"status": status, "per_limit": states}
    warnings = [
        "All objectives are minimized; maximize-type metrics must be explicitly transformed before import.",
        "Source URI and SHA-256 are declared provenance; this engine does not retrieve or authenticate source files.",
        "Cost/time frontiers do not establish radiation superiority, physical reliability, or mission qualification.",
        "Interval results are conditional on the supplied closed bounds; they are not statistical guarantees.",
    ]
    if not require_verified_protection:
        warnings.append("Cost-only comparison: protection equivalence is not assessed, including when records declare verification.")
    else:
        warnings.append("Protection comparability uses declared model evidence only; correctness of that evidence requires separate review.")
    if not limits:
        warnings.append("No limits supplied: feasibility is unconstrained and does not assert practical implementability.")
    if any(m["uncertainty_kind"] == "statistical" for r in records for m in r["metrics"].values()):
        warnings.append("Statistical intervals are not guaranteed simultaneous bounds; not_certainly_dominated is only a box-based screening set.")
    admissible = [r for r in records if feasible[r["id"]]["status"] == "definitely_feasible"]
    return {"status": "accepted", "reasons": [], "objective_direction": "minimize",
            "comparison_context": json.loads(comparison_key(ref)),
            "record_evidence": {r["id"]: {k: r[k] for k in ("method", "metrics", "provenance", "protection")} for r in records},
            "nominal_front": _front(records, names),
            "not_certainly_dominated": _front(records, names, box=True),
            "front_scope": "all_input_records_before_limits",
            "feasibility": feasible,
            "definitely_feasible_nominal_front": _front(admissible, names),
            "limits": limits, "warnings": warnings}


def batch_compare(records):
    """Partition explicitly by known metadata, then separately compare each group."""
    try:
        records = validate_document({"schema_version": "1.0", "records": records})
    except EvidenceError as exc:
        return {"status": "refused", "reasons": [exc.as_dict()], "groups": []}
    groups = {}
    for r in records:
        groups.setdefault(comparison_key(r), []).append(r)
    output = [{"record_ids": [r["id"] for r in rs], "result": compare(rs)} for rs in groups.values()]
    return {"status": "accepted" if all(g["result"]["status"] == "accepted" for g in output) else "refused",
            "reasons": [], "groups": output,
            "warnings": ["Each group has its own frontier. No cross-group ranking or protection comparison is performed."]}
