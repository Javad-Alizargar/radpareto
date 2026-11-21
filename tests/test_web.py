"""Engine-backed web behavior and request-boundary checks."""
import io
import json
import unittest

from web.app import RECORDS, analyze, application
from radpareto import compare


def call(path, method="GET", payload=None, **extra):
    raw = b"" if payload is None else json.dumps(payload).encode()
    env = {"PATH_INFO": path, "REQUEST_METHOD": method, "HTTP_HOST": "localhost:8766",
           "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), **extra}
    capture = {}
    def start(status, headers):
        capture.update(status=status, headers=dict(headers))
    capture["body"] = b"".join(application(env, start))
    return capture


class WebTests(unittest.TestCase):
    def test_published_example_has_observed_mean_range_reversal(self):
        data = analyze({"cells_cap": 40, "frequency_mhz": 32})
        states = [x["status"] for x in data["comparison"]["feasibility"].values()]
        self.assertEqual(states.count("definitely_feasible"), 5)
        self.assertEqual(states.count("uncertain"), 1)
        self.assertEqual(data["comparison"]["feasibility"]["DF-TMR-DFF-5.12"]["status"], "uncertain")

    def test_web_result_is_actual_engine_result(self):
        for cap, clock in [(20, 30), (30, 40), (40, 32), (0, 70)]:
            with self.subTest(cap=cap, clock=clock):
                data = analyze({"cells_cap": cap, "frequency_mhz": clock})
                self.assertEqual(data["comparison"], compare(RECORDS, limits={"cells": cap, "period_ns": 1000 / clock}))

    def test_protection_requirement_refuses_unverified_example(self):
        data = analyze({"require_protection": True})
        self.assertEqual(data["comparison"]["status"], "refused")
        self.assertIn("PROTECTION_UNVERIFIED", {r["code"] for r in data["comparison"]["reasons"]})

    def test_subset_and_stability(self):
        data = analyze({"scope": "set_suppression_architectures_four", "include_stability": True})
        self.assertEqual(len(data["records"]), 4)
        self.assertEqual(data["stability"]["status"], "accepted")

    def test_custom_records_preserve_engine_refusal(self):
        records = json.loads(json.dumps(RECORDS))
        records[1]["context"]["device"] = "incompatible_device"
        data = analyze({"records": records, "limits": {"cells": 40}})
        self.assertEqual(data["comparison"], compare(records, limits={"cells": 40}))
        self.assertEqual(data["comparison"]["status"], "refused")

    def test_custom_record_limit_and_option_types(self):
        for payload in ({"records": RECORDS * 22}, {"frequency_mhz": True}, {"frequency_mhz": 0},
                        {"frequency_mhz": float("nan")}, {"cells_cap": -1}, {"scope": "missing"},
                        {"include_stability": "yes"}, {"records": RECORDS, "scope": "all_six"}):
            with self.subTest(payload=str(payload)[:50]):
                with self.assertRaises(ValueError):
                    analyze(payload)

    def test_source_and_static_allowlist(self):
        for path in ("/Smith/", "/Smith/app.js", "/Smith/styles.css", "/Smith/api/source.csv", "/Smith/health"):
            self.assertEqual(call(path)["status"], "200 OK")
        for path in ("/Smith/../../AGENTS.md", "/Smith/.git/config", "/Smith/web/app.py", "/Smith/manuscript.pdf"):
            self.assertEqual(call(path)["status"], "404 Not Found")

    def test_headers_and_canonical_redirect(self):
        response = call("/Smith/")
        self.assertEqual(response["headers"]["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response["headers"]["Content-Security-Policy"])
        self.assertEqual(call("/Smith")["headers"]["Location"], "/Smith/")
        self.assertEqual(call("/Smith/health", "HEAD")["body"], b"")

    def test_origin_content_type_and_body_limits(self):
        self.assertEqual(call("/Smith/api/analyze", "POST", {}, HTTP_ORIGIN="https://other.example")["status"], "403 Forbidden")
        self.assertEqual(call("/Smith/api/analyze", "POST", {}, CONTENT_TYPE="text/plain")["status"], "415 Unsupported Media Type")
        self.assertEqual(call("/Smith/api/analyze", "POST", {}, CONTENT_LENGTH="524289")["status"], "413 Content Too Large")

    def test_bad_json_and_nonfinite_constants(self):
        for body in (b"{bad", b'{"cells_cap":NaN}', b"[]", b"\xff"):
            self.assertEqual(call("/Smith/api/analyze", "POST", {}, CONTENT_LENGTH=str(len(body)), **{"wsgi.input": io.BytesIO(body)})["status"], "400 Bad Request")


if __name__ == "__main__":
    unittest.main()
