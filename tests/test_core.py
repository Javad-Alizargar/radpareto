"""Independent hand-computed decision cases; fixtures are synthetic software tests."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from radpareto import batch_compare, compare, validate_document, EvidenceError


def record(name="a", area=1., delay=2., radius=0., kind="exact"):
    return {"id": name, "design": "synthetic_software_test", "method": name,
        "context": {"baseline_id": "fixture_v1", "device": "abstract_logic",
            "toolchain": "hand_computed_fixture", "tool_version": "1",
            "implementation": "abstract_costs", "constraints_id": "fixture_v1",
            "timing_corner": "not_applicable_abstract", "workload_id": "fixture_v1",
            "source_kind": "synthetic_example"},
        "metrics": {n: {"value": v, "lower": v-radius, "upper": v+radius,
                "unit": unit, "denominator": "absolute", "uncertainty_kind": kind}
                    for n, v, unit in (("area", area, "abstract_area"), ("delay", delay, "abstract_time"))},
        "provenance": {"source_uri": "test_core.py", "source_sha256": hashlib.sha256(b"hand-computed synthetic fixture v1").hexdigest(),
            "locator": "record()", "extraction": "original synthetic software test"},
        "protection": {"status": "unverified", "fault_model": "unknown", "scope": "unknown", "evidence_uri": "unknown"}}


def document(*records):
    return {"schema_version": "1.0", "records": list(records)}


class ValidationTests(unittest.TestCase):
    def test_returns_detached_records(self):
        d = document(record())
        r = validate_document(d)
        r[0]["metrics"]["area"]["value"] = 500
        self.assertEqual(d["records"][0]["metrics"]["area"]["value"], 1)

    def test_rejects_nonreal_and_nonfinite(self):
        for bad in (True, False, None, "1", float("nan"), float("inf"), -1., 10**400):
            with self.subTest(bad=str(bad)):
                r = record(); r["metrics"]["area"]["value"] = bad
                with self.assertRaises(EvidenceError) as caught:
                    validate_document(document(r))
                self.assertEqual(caught.exception.code, "INVALID_NUMBER")

    def test_interval_and_exact_semantics(self):
        r = record(); r["metrics"]["area"]["lower"] = 2
        self.assertEqual(compare([r])["reasons"][0]["code"], "INVALID_INTERVAL")
        r = record(); r["metrics"]["area"]["upper"] = 2
        self.assertEqual(compare([r])["reasons"][0]["code"], "NONEXACT_INTERVAL")

    def test_duplicate_id_and_missing_context(self):
        self.assertEqual(compare([record(), record()])["reasons"][0]["code"], "DUPLICATE_ID")
        r = record(); del r["context"]["baseline_id"]
        self.assertEqual(compare([r])["reasons"][0]["code"], "MISSING_FIELD")

    def test_unknown_fields_not_ignored(self):
        r = record(); r["metrics"]["area"]["directon"] = "maximize"
        self.assertEqual(compare([r])["reasons"][0]["code"], "UNSUPPORTED_FIELD")

    def test_sha_and_schema(self):
        r = record(); r["provenance"]["source_sha256"] = "fake"
        self.assertEqual(compare([r])["reasons"][0]["code"], "INVALID_SHA256")
        d = document(record()); d["schema_version"] = "2.0"
        with self.assertRaises(EvidenceError) as caught:
            validate_document(d)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_SCHEMA")


class ComparisonTests(unittest.TestCase):
    def test_known_tradeoff_dominance_and_equal_points(self):
        r = compare([record("a", 1, 3), record("b", 3, 1), record("c", 4, 4), record("d", 1, 3)])
        self.assertEqual(r["status"], "accepted")
        self.assertEqual(r["nominal_front"], ["a", "b", "d"])
        self.assertEqual(r["not_certainly_dominated"], ["a", "b", "d"])
        self.assertEqual(r["comparison_context"]["design"], "synthetic_software_test")
        self.assertEqual(r["record_evidence"]["a"]["provenance"]["locator"], "record()")

    def test_rounding_tie_changes_certainty_not_nominal(self):
        a, b = record("a", 3.43, 1.07, .005, "rounding"), record("b", 3.43, 1.31, .005, "rounding")
        r = compare([a, b])
        self.assertEqual(r["nominal_front"], ["a"])
        self.assertEqual(r["not_certainly_dominated"], ["a", "b"])

    def test_disjoint_intervals_and_strictness(self):
        a, b = record("a", 1, 1, .1, "bounded"), record("b", 2, 2, .1, "bounded")
        self.assertEqual(compare([a, b])["not_certainly_dominated"], ["a"])
        a, b = record("a", 1, 1), record("b", 1, 1)
        self.assertEqual(compare([a, b])["nominal_front"], ["a", "b"])

    def test_reject_all_required_context_mismatches(self):
        for key in record()["context"]:
            with self.subTest(field=key):
                a, b = record("a"), record("b")
                b["context"][key] = "analytical" if key == "source_kind" else "different"
                r = compare([a, b])
                self.assertEqual(r["status"], "refused")
                self.assertTrue(any(x["code"] == "CONTEXT_MISMATCH" for x in r["reasons"]))
                self.assertEqual(r["nominal_front"], [])

    def test_unknown_context_refuses_even_when_both_match(self):
        for value in ("unknown", "not_reported", "not reported", "not-reported", "TBD", "?",
                      "not_available", "Not Available", "NOT-AVAILABLE", "not_tested", "not_applicable"):
            a, b = record("a"), record("b")
            a["context"]["device"] = b["context"]["device"] = value
            validate_document(document(a, b))
            self.assertEqual(compare([a,b])["status"], "refused")

    def test_metrics_and_design_mismatch(self):
        for key, value in (("unit", "ns"), ("denominator", "different_baseline"), ("uncertainty_kind", "bounded")):
            a, b = record("a"), record("b")
            b["metrics"]["area"][key] = value
            self.assertEqual(compare([a,b])["status"], "refused")
        a, b = record("a"), record("b")
        b["metrics"]["new_metric"] = b["metrics"].pop("area")
        self.assertEqual(compare([a,b])["reasons"][0]["code"], "METRIC_SET_MISMATCH")
        b = record("b"); b["design"] = "different"
        self.assertEqual(compare([a,b])["reasons"][0]["code"], "DESIGN_MISMATCH")

    def test_constraint_feasible_uncertain_infeasible(self):
        r = compare([record("f", 1, 1, .1, "bounded"), record("u", 2, 2, .1, "bounded"), record("i", 3, 3, .1, "bounded")], limits={"area": 2})
        self.assertEqual([r["feasibility"][k]["status"] for k in ("f","u","i")], ["definitely_feasible","uncertain","definitely_infeasible"])
        self.assertEqual(r["definitely_feasible_nominal_front"], ["f"])

    def test_constraints_do_not_silently_filter_all_input_front(self):
        r = compare([record("fast", 5, 1), record("small", 1, 5)], limits={"area": 2})
        self.assertEqual(r["nominal_front"], ["fast", "small"])
        self.assertEqual(r["definitely_feasible_nominal_front"], ["small"])
        self.assertEqual(r["feasibility"]["fast"]["status"], "definitely_infeasible")

    def test_bad_limits_refuse(self):
        for limits in ({"absent": 3}, {"area": True}, {"area": float("nan")}, [], {"area": -1}):
            self.assertEqual(compare([record()], limits=limits)["status"], "refused")

    def test_protection_mode_requires_evidence_and_common_scope(self):
        a, b = record("a"), record("b")
        self.assertEqual(compare([a,b], require_verified_protection=True)["status"], "refused")
        for r in (a,b):
            r["protection"] = {"status": "verified_within_model", "fault_model": "single_synchronous_flip", "scope": "modeled_registers", "evidence_uri": "campaign-v1.json"}
        self.assertEqual(compare([a,b], require_verified_protection=True)["status"], "accepted")
        b["protection"]["scope"] = "all_common_mode_faults"
        self.assertEqual(compare([a,b], require_verified_protection=True)["status"], "refused")
        # Cost-only workflow never interprets differing declared coverage as equivalent.
        r = compare([a,b])
        self.assertEqual(r["status"], "accepted")
        self.assertTrue(any("not assessed" in x for x in r["warnings"]))

    def test_verified_flag_cannot_override_placeholder_protection(self):
        placeholders = ("not_tested", "not_available", "not_measured", "not_verified",
                        "not_validated", "not_assessed", "not_evaluated", "not_provided",
                        "not_recorded", "not_known", "not_applicable", "no_evidence",
                        "unverified", "unavailable", "Not Tested", "NOT-AVAILABLE",
                        "not__measured", "N / A", "not\u2013verified")
        for field in ("fault_model", "scope", "evidence_uri"):
            for placeholder in placeholders:
                with self.subTest(field=field, placeholder=placeholder):
                    a, b = record("a"), record("b")
                    for r in (a, b):
                        r["protection"] = {"status": "verified_within_model",
                            "fault_model": "single_synchronous_flip", "scope": "modeled_registers",
                            "evidence_uri": "campaign-v1.json"}
                        r["protection"][field] = placeholder
                    result = compare([a, b], require_verified_protection=True)
                    self.assertEqual(result["status"], "refused")
                    self.assertTrue(any(x["code"] == "PROTECTION_UNVERIFIED" for x in result["reasons"]))

    def test_adapter_nonphysical_context_is_explicit_not_placeholder(self):
        a, b = record("a"), record("b")
        for r in (a, b):
            r["context"]["device"] = "abstract_generic_logic"
            r["context"]["timing_corner"] = "not_applicable_logic_depth_surrogate"
            r["protection"].update(fault_model="not_tested", evidence_uri="not_available")
        self.assertEqual(compare([a, b])["status"], "accepted")
        self.assertEqual(compare([a, b], require_verified_protection=True)["status"], "refused")
        for r in (a, b):
            r["protection"]["status"] = "verified_within_model"
        self.assertEqual(compare([a, b], require_verified_protection=True)["status"], "refused")

    def test_batch_stratifies_and_unknown_group_refuses(self):
        a,b,c = record("a"),record("b"),record("c")
        b["context"]["device"] = "other_device"
        r = batch_compare([a,b,c])
        self.assertEqual([g["record_ids"] for g in r["groups"]], [["a","c"],["b"]])
        b["context"]["device"] = "unknown"
        r = batch_compare([a,b])
        self.assertEqual(r["status"], "refused")
        self.assertEqual(r["groups"][1]["result"]["status"], "refused")

    def test_statistical_bound_warning(self):
        r = compare([record(kind="statistical")])
        self.assertTrue(any("simultaneous" in x for x in r["warnings"]))


class CLITests(unittest.TestCase):
    def invoke(self, *args):
        env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, "-m", "radpareto", *map(str,args)], capture_output=True, text=True, env=env)

    def test_cli_output_refusal_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            inp, out = Path(folder)/"input.json", Path(folder)/"result.json"
            inp.write_text(json.dumps(document(record("a"), record("b",2,3))), encoding="utf-8")
            p = self.invoke("compare", inp, "--output", out)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(out.read_text())["nominal_front"], ["a"])
            replay = json.loads(out.read_text())["replay"]
            self.assertEqual(replay["input_sha256"], hashlib.sha256(inp.read_bytes()).hexdigest())
            self.assertEqual(replay["software_version"], "0.4.0")
            self.assertEqual(replay["command"], "compare")
            first_result = out.read_bytes()
            p = self.invoke("compare", inp, "--output", out)
            self.assertEqual(first_result, out.read_bytes())
            p = self.invoke("compare", inp, "--require-verified-protection")
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)["status"], "refused")
            original = inp.read_bytes()
            p = self.invoke("compare", inp, "--output", inp)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(inp.read_bytes(), original)

    def test_duplicate_json_keys_and_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            inp = Path(folder)/"input.json"
            for payload in ('{"records":[], "records":[], "schema_version":"1.0"}', '{"schema_version":"1.0", "records":NaN}'):
                inp.write_text(payload, encoding="utf-8")
                p = self.invoke("validate", inp)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(json.loads(p.stdout)["reasons"][0]["code"], "INVALID_INPUT")

    def test_missing_file_and_oversize(self):
        with tempfile.TemporaryDirectory() as folder:
            inp = Path(folder)/"input.json"
            self.assertEqual(self.invoke("validate", inp).returncode, 3)
            inp.write_bytes(b" "*(10*1024*1024+1))
            p = self.invoke("validate", inp)
            self.assertEqual(p.returncode, 2)
            self.assertIn("10 MiB", p.stdout)

    def test_cli_validate_batch_and_bad_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            inp = Path(folder)/"input.json"
            inp.write_text(json.dumps(document(record())), encoding="utf-8")
            p = self.invoke("validate", inp)
            self.assertEqual(json.loads(p.stdout)["validation"], "structural_only")
            self.assertEqual(self.invoke("batch", inp).returncode, 0)
            for args in (("--limit","area=1","--limit","area=2"), ("--limit","area=NaN"), ("--limit","unknown=2")):
                p = self.invoke("compare", inp, *args)
                self.assertEqual(p.returncode, 2, p.stdout)


if __name__ == "__main__":
    unittest.main()
