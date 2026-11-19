"""Independent documented-contract reference and an explicitly weaker ablation.

Written from INTERFACE.md and docs/semantics.md, without reading/importing the
RadPareto implementation or evaluation answer key. All numerical objectives
are minimized. No timing, reliability or researcher-productivity inference.
"""
import math
from numbers import Real
import re

import pandas as pd

CONTEXT = {
    "baseline_id", "device", "toolchain", "tool_version", "implementation",
    "constraints_id", "timing_corner", "workload_id", "source_kind",
}
KINDS = {"published_table", "synthesis", "simulation", "measurement",
         "analytical", "synthetic_example"}
UNCERTAINTY = {"exact", "rounding", "bounded", "statistical"}
# Explicit local policy, not a synonym learner. Longer meaningful labels are
# preserved. Normalization does not turn a matching declaration into proof.
MISSING = {"unknown", "notreported", "notavailable", "nottested", "notassessed",
           "notverified", "unverified", "unspecified", "missing", "na", "none",
           "null", "notapplicable", "unreported", "unavailable"}


class ContractError(ValueError):
    pass


def _keys(value, expected, location):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ContractError(f"{location}: required fields differ")


def _text(value, location):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{location}: nonempty text required")


def _number(value, location):
    try:
        valid = isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
    except (OverflowError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ContractError(f"{location}: finite nonnegative number required")


def _known(value):
    return re.sub(r"[\s_./-]+", "", value.casefold()) not in MISSING


def validate_structure(document):
    """Validate Python-decoded JSON. Duplicate raw JSON keys are out of scope."""
    _keys(document, {"schema_version", "records"}, "document")
    if document["schema_version"] != "1.0":
        raise ContractError("document: unsupported schema version")
    records = document["records"]
    if not isinstance(records, list) or not records:
        raise ContractError("records: nonempty array required")
    seen = set()
    for position, record in enumerate(records):
        loc = f"records[{position}]"
        _keys(record, {"id", "design", "method", "context", "metrics", "provenance", "protection"}, loc)
        for name in ("id", "design", "method"):
            _text(record[name], f"{loc}.{name}")
        if record["id"] in seen:
            raise ContractError("records: duplicate id")
        seen.add(record["id"])
        _keys(record["context"], CONTEXT, loc + ".context")
        for name, value in record["context"].items():
            _text(value, f"{loc}.context.{name}")
        if record["context"]["source_kind"] not in KINDS:
            raise ContractError(loc + ": unknown source kind")
        metrics = record["metrics"]
        if not isinstance(metrics, dict) or not metrics:
            raise ContractError(loc + ": nonempty metrics mapping required")
        for name, metric in metrics.items():
            _text(name, loc + ".metrics key")
            _keys(metric, {"value", "lower", "upper", "unit", "denominator", "uncertainty_kind"}, loc + ".metrics." + name)
            for field in ("value", "lower", "upper"):
                _number(metric[field], loc + ".metrics." + name + "." + field)
            for field in ("unit", "denominator", "uncertainty_kind"):
                _text(metric[field], loc + ".metrics." + name + "." + field)
            if metric["uncertainty_kind"] not in UNCERTAINTY:
                raise ContractError(loc + ": unknown uncertainty kind")
            if not metric["lower"] <= metric["value"] <= metric["upper"]:
                raise ContractError(loc + ": central value outside bounds")
            if metric["uncertainty_kind"] == "exact" and metric["lower"] != metric["upper"]:
                raise ContractError(loc + ": exact metric has nonzero width")
        _keys(record["provenance"], {"source_uri", "source_sha256", "locator", "extraction"}, loc + ".provenance")
        for name, value in record["provenance"].items():
            _text(value, f"{loc}.provenance.{name}")
        if not re.fullmatch(r"[0-9a-f]{64}", record["provenance"]["source_sha256"]):
            raise ContractError(loc + ": invalid source hash")
        protection = record["protection"]
        _keys(protection, {"status", "fault_model", "scope", "evidence_uri"}, loc + ".protection")
        for name, value in protection.items():
            _text(value, f"{loc}.protection.{name}")
        if protection["status"] not in {"unverified", "verified_within_model"}:
            raise ContractError(loc + ": invalid protection status")
    return records


def _same_objectives(records):
    names = list(records[0]["metrics"])
    if any(set(record["metrics"]) != set(names) for record in records[1:]):
        raise ContractError("comparison: objective names differ")
    return names


def _options(limits, names, require_verified_protection):
    if not isinstance(require_verified_protection, bool):
        raise ContractError("options: protection flag must be boolean")
    if limits is None:
        return {}
    if not isinstance(limits, dict):
        raise ContractError("options: limits must be an objective/value mapping")
    for key, value in limits.items():
        if key not in names:
            raise ContractError("options: limit objective absent")
        _number(value, "limit " + key)
    return limits


def _compatibility(records, require_verified_protection):
    first = records[0]
    for record in records:
        if any(not _known(value) for value in record["context"].values()):
            raise ContractError("comparison: required context is unknown")
        if record["context"] != first["context"] or record["design"] != first["design"]:
            raise ContractError("comparison: context or design differs")
        for name in first["metrics"]:
            for field in ("unit", "denominator", "uncertainty_kind"):
                if record["metrics"][name][field] != first["metrics"][name][field]:
                    raise ContractError("comparison: objective semantics differ")
        if require_verified_protection:
            p = record["protection"]
            if p["status"] != "verified_within_model" or any(not _known(p[key]) for key in ("fault_model", "scope", "evidence_uri")):
                raise ContractError("comparison: protection evidence is unverified or missing")
            if p != first["protection"]:
                raise ContractError("comparison: protection model, scope or evidence differs")


def _tables(records, names):
    """Construct labelled object tables to avoid coercing exact large integers."""
    return {field: pd.DataFrame(
        [[record["metrics"][name][field] for name in names] for record in records],
        index=[record["id"] for record in records], columns=names, dtype=object)
        for field in ("value", "lower", "upper")}


def _front(challenger, target):
    kept = []
    for row_id in target.index:
        weak = challenger.le(target.loc[row_id], axis="columns").all(axis="columns")
        strict = challenger.lt(target.loc[row_id], axis="columns").any(axis="columns")
        other = challenger.index != row_id
        if not (weak & strict & other).any():
            kept.append(row_id)
    return kept


def _feasibility(tables, limits):
    if not limits:
        return {row_id: {"status": "definitely_feasible"} for row_id in tables["value"].index}
    names = list(limits)
    cap = pd.Series(limits)
    definite = tables["upper"][names].le(cap, axis="columns").all(axis="columns")
    impossible = tables["lower"][names].gt(cap, axis="columns").any(axis="columns")
    return {row_id: {"status": "definitely_infeasible" if impossible[row_id] else
                     "definitely_feasible" if definite[row_id] else "uncertain"}
            for row_id in tables["value"].index}


def _refused(error):
    return {"status": "refused", "reasons": [{"code": "REFERENCE_CONTRACT", "message": str(error)}]}


def compare_document(document, limits=None, require_verified_protection=False):
    """Full documented-contract reference, independent of the production engine."""
    try:
        records = validate_structure(document)
        names = _same_objectives(records)
        limits = _options(limits, names, require_verified_protection)
        _compatibility(records, require_verified_protection)
        tables = _tables(records, names)
        feasible = _feasibility(tables, limits)
        selected = [key for key, value in feasible.items() if value["status"] == "definitely_feasible"]
        constrained = tables["value"].loc[selected]
        return {"status": "accepted", "reasons": [],
                "nominal_front": _front(tables["value"], tables["value"]),
                "not_certainly_dominated": _front(tables["upper"], tables["lower"]),
                "feasibility": feasible,
                "definitely_feasible_nominal_front": _front(constrained, constrained),
                "warnings": ["Reference checks declarations; no source authentication or physical reliability inference.",
                             "With no limits, feasibility is vacuous and does not imply practical implementability."]}
    except ContractError as error:
        return _refused(error)


def nominal_only_document(document, limits=None, require_verified_protection=False):
    """Ablation: schema checked, but context/units/protection/bounds not compared.

    Not a full-feature rival and not a safe recommendation workflow. Interval
    conclusions are deliberately unavailable, not falsely marked certain.
    """
    try:
        records = validate_structure(document)
        names = _same_objectives(records)
        limits = _options(limits, names, require_verified_protection)
        values = _tables(records, names)["value"]
        point_feasible = (values[list(limits)].le(pd.Series(limits), axis="columns").all(axis="columns")
                          if limits else pd.Series(True, index=values.index))
        selected = values.loc[point_feasible]
        return {"status": "accepted", "reasons": [], "nominal_front": _front(values, values),
                "not_certainly_dominated": None, "feasibility": None,
                "definitely_feasible_nominal_front": None,
                "nominal_limit_compliance": {key: bool(value) for key, value in point_feasible.items()} if limits else {},
                "nominal_feasible_front": _front(selected, selected) if limits else [],
                "warnings": ["Ablation only: semantic comparability and protection ignored; interval decisions unavailable."]}
    except ContractError as error:
        return _refused(error)
