"""Explicit decimal MHz-to-ns conversion for published frequency inputs.

The comparison engine still operates on represented Python numbers. This
adapter gives a frequency value and an equal requirement the same conversion
path; it does not make binary64 output exact or add measurement precision.
"""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import math
import re


def period_ns_from_mhz(value):
    """Convert positive finite decimal MHz to a binary64 period in ns.

    Strings preserve source decimal spelling. Integers and floats use their
    ordinary decimal string representation, not the exact binary float ratio.
    The decimal reciprocal is evaluated as a rational and rounded once.
    Booleans, nonnumeric spellings, nonpositive values and unrepresentable
    reciprocals are rejected. A bounded input length/exponent avoids treating
    this domain adapter as an arbitrary-size symbolic calculator.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("frequency must be a positive finite decimal string or number")
    token = str(value).strip()
    if len(token) > 128 or not re.fullmatch(r"[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
        raise ValueError("frequency must be a positive finite decimal string or number")
    try:
        decimal = Decimal(token)
    except InvalidOperation as exc:
        raise ValueError("frequency exponent is outside the supported decimal range") from exc
    if not decimal.is_finite() or decimal <= 0 or not -400 <= decimal.adjusted() <= 400:
        raise ValueError("frequency is outside the supported positive finite range")
    try:
        result = float(Fraction(1000) / Fraction(decimal))
    except OverflowError as exc:
        raise ValueError("reciprocal period is outside the finite binary64 range") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError("reciprocal period is outside the positive binary64 range")
    return result
