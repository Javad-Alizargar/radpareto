"""Targeted read-only review tests; direct endpoint oracle, not new implementation."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from radpareto.cli import _assignments
from radpareto.stability import stability


def record(rid, points):
    return {
        "id": rid, "design": "review-fixture", "method": rid,
        "context": {"baseline_id": "fixture", "device": "abstract", "toolchain": "direct-endpoints",
                    "tool_version": "1", "implementation": "synthetic-costs", "constraints_id": "fixture",
                    "timing_corner": "abstract-costs", "workload_id": "fixture", "source_kind": "synthetic_example"},
        "metrics": {n: {"lower": v[0], "value": v[0], "upper": v[1], "unit": "cost",
                        "denominator": "absolute", "uncertainty_kind": "bounded"} for n, v in points.items()},
        "provenance": {"source_uri": "test_candidate_review.py", "source_sha256": "0" * 64,
                       "locator": rid, "extraction": "Original synthetic review fixture"},
        "protection": {"status": "unverified", "fault_model": "unknown", "scope": "unknown", "evidence_uri": "unknown"}}


def point(rid, *values):
    return record(rid, {f"cost_{j}": (v, v) for j, v in enumerate(values)})


def q(obj):
    return Fraction(int(obj["numerator"]), int(obj["denominator"]))


def applies(certificate, t, key):
    if certificate["transition_t"] is None:
        return True
    threshold = q(certificate["transition_t"])
    return t < threshold or (t == threshold and certificate[key])


class CandidateReview(unittest.TestCase):
    def assert_endpoints(self, records, scales, limits=None):
        limits = limits or {}
        original = deepcopy(records)
        result = stability(records, scales, limits)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(records, original)
        json.dumps(result, allow_nan=False)
        probes = {Fraction(0), Fraction(1), Fraction(10**6)}
        for c in result["dominance_certificates"] + result["constraint_certificates"]:
            if c["transition_t"] is not None:
                t = q(c["transition_t"])
                delta = min(Fraction(1, 10**6), t / 2) if t else Fraction(1, 10**6)
                probes.update({t, t + delta})
                if t:
                    probes.add(t - delta)
        for t in probes:
            lower = {r["id"]: {n: max(Fraction(0), Fraction(m["lower"]) - t * Fraction(scales[n]))
                                for n, m in r["metrics"].items()} for r in records}
            upper = {r["id"]: {n: Fraction(m["upper"]) + t * Fraction(scales[n])
                                for n, m in r["metrics"].items()} for r in records}
            actual = {(a["id"], b["id"]) for a in records for b in records if a["id"] != b["id"]
                      and all(upper[a["id"]][n] <= lower[b["id"]][n] for n in scales)
                      and any(upper[a["id"]][n] < lower[b["id"]][n] for n in scales)}
            predicted = {(c["dominant_id"], c["dominated_id"]) for c in result["dominance_certificates"]
                         if applies(c, t, "initial_relation_includes_boundary")}
            self.assertEqual(actual, predicted, (t, scales))
            self.assertEqual(len(result["constraint_certificates"]), len(records) * len(limits))
            for c in result["constraint_certificates"]:
                rid, n = c["record_id"], c["objective"]
                direct = ("definitely_infeasible" if lower[rid][n] > Fraction(limits[n]) else
                          "definitely_feasible" if upper[rid][n] <= Fraction(limits[n]) else "uncertain")
                predicted = c["initial_status"] if applies(c, t, "initial_status_includes_boundary") else c["status_after_transition"]
                self.assertEqual(direct, predicted, (rid, n, t))
        return result

    def test_canonical_inclusive_transition(self):
        result = self.assert_endpoints([point("A", 20, 40), point("B", 22, 50), point("C", 30, 30)],
                                       {"cost_0": 1, "cost_1": 1}, {"cost_0": 25})
        self.assertEqual(len(result["dominance_certificates"]), 1)
        c = result["dominance_certificates"][0]
        self.assertEqual(q(c["transition_t"]), 1)
        self.assertTrue(c["initial_relation_includes_boundary"])
        self.assertEqual(c["limiting_objectives"], ["cost_0"])

    def test_simultaneous_equalities_exclude_endpoint(self):
        c = self.assert_endpoints([point("A", 2, 4), point("B", 4, 6)],
                                 {"cost_0": 1, "cost_1": 1})["dominance_certificates"][0]
        self.assertFalse(c["initial_relation_includes_boundary"])
        self.assertEqual(c["limiting_objectives"], ["cost_0", "cost_1"])

    def test_zero_scales_zero_time_and_ties(self):
        for scales in ({"cost_0": 0, "cost_1": 0}, {"cost_0": 1, "cost_1": 0}):
            result = self.assert_endpoints([point("A", 0, 0), point("B", 0, 3), point("T", 0, 0)], scales)
            self.assertEqual(len(result["dominance_certificates"]), 2)
            for c in result["dominance_certificates"]:
                if scales["cost_0"]:
                    self.assertEqual(q(c["transition_t"]), 0)
                    self.assertTrue(c["initial_relation_includes_boundary"])
                else:
                    self.assertIsNone(c["transition_t"])

    def test_constraint_boundaries_and_clipping(self):
        for scale in (0, 1):
            result = self.assert_endpoints([point("F", 0), point("I", 3), record("U", {"cost_0": (0, 3)})],
                                           {"cost_0": scale}, {"cost_0": 0})
            if scale:
                by_id = {c["record_id"]: c for c in result["constraint_certificates"]}
                self.assertTrue(by_id["F"]["initial_status_includes_boundary"])
                self.assertFalse(by_id["I"]["initial_status_includes_boundary"])
                self.assertIsNone(by_id["U"]["transition_t"])

    def test_represented_binary_floats_and_subnormal(self):
        for values, scale in (((0.1, 0.3), 0.1), ((0.0, 5e-324), 5e-324)):
            result = self.assert_endpoints([point("A", values[0]), point("B", values[1])],
                                           {"cost_0": scale}, {"cost_0": values[1]})
            if scale == 0.1:
                self.assertNotEqual(q(result["dominance_certificates"][0]["transition_t"]), 1)
                self.assertEqual(q(result["model"]["scales"]["cost_0"]), Fraction(0.1))

    def test_exact_large_integer_and_json_strings(self):
        for n in (2**53 + 1, 10**308):
            result = self.assert_endpoints([point("A", n), point("B", n + 2)], {"cost_0": 1}, {"cost_0": n + 1})
            self.assertEqual(q(result["dominance_certificates"][0]["transition_t"]), 1)
            self.assertIsInstance(result["dominance_certificates"][0]["transition_t"]["numerator"], str)
        self.assertEqual(stability([point("A", 10**400)], {"cost_0": 1})["status"], "refused")

    def test_invalid_scales_options_limits_and_context(self):
        rows = [point("A", 1)]
        for scales in ({}, {"wrong": 1}, None, [], {"cost_0": True}, {"cost_0": -1},
                       {"cost_0": float("nan")}, {"cost_0": float("inf")}, {"cost_0": "1"}):
            self.assertEqual(stability(rows, scales)["status"], "refused")
        for kwargs in ({"limits": []}, {"limits": {"wrong": 1}}, {"limits": {"cost_0": True}},
                       {"require_verified_protection": 1}, {"require_verified_protection": True}):
            self.assertEqual(stability(rows, {"cost_0": 1}, **kwargs)["status"], "refused")
        bad = deepcopy(rows)
        bad[0]["context"]["device"] = "unknown"
        self.assertEqual(stability(bad, {"cost_0": 1})["status"], "refused")
        mismatch = [point("A", 1), point("B", 2)]
        mismatch[1]["context"]["device"] = "different"
        self.assertEqual(stability(mismatch, {"cost_0": 1})["status"], "refused")
        for rows in ([], {}, None):
            self.assertEqual(stability(rows, {"cost_0": 1})["status"], "refused")

    def test_record_and_objective_caps(self):
        rows = [point(str(i), 1) for i in range(129)]
        self.assertEqual(stability(rows[:128], {"cost_0": 0})["status"], "accepted")
        self.assertEqual(stability(rows, {"cost_0": 0})["reasons"][0]["code"], "STABILITY_RECORD_LIMIT")
        self.assert_endpoints([point("A", *range(16)), point("B", *range(2, 18))],
                              {f"cost_{i}": i % 3 for i in range(16)})
        self.assertEqual(stability([point("A", *range(17))], {f"cost_{i}": 1 for i in range(17)})["status"], "refused")

    def test_cli_assignment_precision_and_invalid_tokens(self):
        self.assertEqual(_assignments(["cost_0=9007199254740993"], "--scale")["cost_0"], 2**53 + 1)
        self.assertIsInstance(_assignments(["cost_0=9007199254740993"], "--limit")["cost_0"], int)
        for args in (["cost_0=NaN"], ["cost_0=1", "cost_0=2"], ["cost_0"]):
            with self.assertRaises(ValueError):
                _assignments(args, "--scale")


if __name__ == "__main__":
    unittest.main(verbosity=2)
