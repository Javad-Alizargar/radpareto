"""Structural validation for source-located cost evidence. No source is fetched."""
from copy import deepcopy
import math
import re

SCHEMA_VERSION = "1.0"
CONTEXT_FIELDS = frozenset({"baseline_id", "device", "toolchain", "tool_version", "implementation", "constraints_id", "timing_corner", "workload_id", "source_kind"})
SOURCE_KINDS = frozenset({"published_table", "synthesis", "simulation", "measurement", "analytical", "synthetic_example"})
UNCERTAINTY_KINDS = frozenset({"exact", "rounding", "bounded", "statistical"})
MAX_RECORDS = 2000
MAX_OBJECTIVES = 16
UNKNOWN_MARKERS = frozenset({
    "unknown", "unspecified", "undefined", "missing", "pending", "tbd", "tbc",
    "?", "none", "null", "n_a", "na", "unavailable", "unreported", "unresolved",
    "untested", "unmeasured", "unverified", "unvalidated", "unassessed",
    "not_reported", "not_available", "not_tested", "not_measured", "not_verified",
    "not_validated", "not_assessed", "not_evaluated", "not_provided", "not_supplied",
    "not_recorded", "not_known", "not_applicable", "not_demonstrated", "not_established",
    "no_data", "no_evidence", "insufficient_evidence", "no_support",
})


class EvidenceError(ValueError):
    """Machine-readable validation failure with a concise human explanation."""
    def __init__(self, code, path, message):
        self.code, self.path, self.message = code, path, message
        super().__init__(f"{code} at {path}: {message}")

    def as_dict(self):
        return {"code": self.code, "path": self.path, "message": self.message}


def _fields(obj, required, path):
    if not isinstance(obj, dict):
        raise EvidenceError("INVALID_TYPE", path, "Expected an object")
    missing, extra = required-set(obj), set(obj)-required
    if missing:
        raise EvidenceError("MISSING_FIELD", path, ", ".join(sorted(missing)))
    if extra:
        raise EvidenceError("UNSUPPORTED_FIELD", path, ", ".join(sorted(map(str, extra))))


def _text(value, path):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise EvidenceError("INVALID_STRING", path, "Expected a nonempty string without surrounding whitespace")
    if len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise EvidenceError("INVALID_STRING", path, "String is too long or contains control characters")


def _number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError("INVALID_NUMBER", path, "Expected a finite nonnegative real number, not a boolean")
    try:
        valid = math.isfinite(value) and value >= 0
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise EvidenceError("INVALID_NUMBER", path, "Expected a finite nonnegative real number")


def is_unknown(value):
    # Normalize complete placeholder tokens, not substrings of legitimate paths
    # or explanatory contexts such as not_applicable_logic_depth_surrogate.
    # This catches not_tested, NOT-TESTED and Not Tested equally. It cannot
    # authenticate a caller's affirmative evidence declaration.
    normalized = re.sub(r"[\s_/\-\u2010-\u2015]+", "_", value.casefold()).strip("_")
    return normalized in UNKNOWN_MARKERS


def validate_document(data):
    """Return a detached validated record list, or raise EvidenceError/ValueError.

    Validation establishes schema consistency, not source authenticity or
    scientific comparability. Unknown context is retained for explicit refusal
    by compare(), rather than silently treated as known matching evidence.
    """
    _fields(data, {"schema_version", "records"}, "document")
    if data["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("UNSUPPORTED_SCHEMA", "schema_version", "Expected 1.0")
    records = data["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
        raise EvidenceError("INVALID_RECORDS", "records", f"Expected 1 to {MAX_RECORDS} records")
    seen = set()
    for i, record in enumerate(records):
        path = f"records[{i}]"
        _fields(record, {"id", "design", "method", "context", "metrics", "provenance", "protection"}, path)
        for name in ("id", "design", "method"):
            _text(record[name], f"{path}.{name}")
        if record["id"] in seen:
            raise EvidenceError("DUPLICATE_ID", f"{path}.id", record["id"])
        seen.add(record["id"])
        _fields(record["context"], CONTEXT_FIELDS, f"{path}.context")
        for name, value in record["context"].items():
            _text(value, f"{path}.context.{name}")
        if record["context"]["source_kind"] not in SOURCE_KINDS:
            raise EvidenceError("INVALID_SOURCE_KIND", f"{path}.context.source_kind", "Unsupported evidence source kind")
        metrics = record["metrics"]
        if not isinstance(metrics, dict) or not 1 <= len(metrics) <= MAX_OBJECTIVES:
            raise EvidenceError("INVALID_METRICS", f"{path}.metrics", f"Expected 1 to {MAX_OBJECTIVES} objectives")
        for name, metric in metrics.items():
            _text(name, f"{path}.metrics objective name")
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
                raise EvidenceError("INVALID_METRIC_NAME", f"{path}.metrics", "Use lower-case ASCII identifiers")
            mp = f"{path}.metrics.{name}"
            _fields(metric, {"value", "lower", "upper", "unit", "denominator", "uncertainty_kind"}, mp)
            for key in ("value", "lower", "upper"):
                _number(metric[key], f"{mp}.{key}")
            if not metric["lower"] <= metric["value"] <= metric["upper"]:
                raise EvidenceError("INVALID_INTERVAL", mp, "Require lower <= value <= upper")
            for key in ("unit", "denominator", "uncertainty_kind"):
                _text(metric[key], f"{mp}.{key}")
            kind = metric["uncertainty_kind"]
            if kind not in UNCERTAINTY_KINDS:
                raise EvidenceError("INVALID_UNCERTAINTY_KIND", mp, "Unsupported uncertainty kind")
            if kind == "exact" and not metric["lower"] == metric["value"] == metric["upper"]:
                raise EvidenceError("NONEXACT_INTERVAL", mp, "Exact values require identical endpoints")
        prov = record["provenance"]
        _fields(prov, {"source_uri", "source_sha256", "locator", "extraction"}, f"{path}.provenance")
        for key, value in prov.items():
            _text(value, f"{path}.provenance.{key}")
        if not re.fullmatch(r"[0-9a-f]{64}", prov["source_sha256"]):
            raise EvidenceError("INVALID_SHA256", f"{path}.provenance.source_sha256", "Expected 64 lower-case hexadecimal characters")
        protection = record["protection"]
        _fields(protection, {"status", "fault_model", "scope", "evidence_uri"}, f"{path}.protection")
        for key, value in protection.items():
            _text(value, f"{path}.protection.{key}")
        if protection["status"] not in {"unverified", "verified_within_model"}:
            raise EvidenceError("INVALID_PROTECTION_STATUS", f"{path}.protection.status", "Unsupported protection evidence status")
    return deepcopy(records)
