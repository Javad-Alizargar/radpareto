"""Small, stateless WSGI interface to RadPareto's actual comparison engine.

Local preview: python web/app.py --port 8766
Production: gunicorn --bind 127.0.0.1:8766 --workers 2 web.app:application
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from radpareto import __version__, compare, stability

PREFIX = "/Smith"
STATIC = Path(__file__).resolve().parent / "static"
CASE = ROOT / "benchmarks" / "published_case"
MAX_BODY = 524288
MAX_RECORDS = 128
SOURCE_REVISION = os.environ.get("RADPARETO_SOURCE_REVISION", "unreleased-local")
SCOPES = {"all_six": None, "tmr_based_five": 1, "set_suppression_architectures_four": 2}


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_case():
    """Refuse startup with changed source inputs or inconsistent derived records."""
    freeze = _read_json(CASE / "source_freeze.json")
    for name, entry in freeze["files"].items():
        if hashlib.sha256((CASE / name).read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Published-case input hash mismatch")
    records = _read_json(CASE / "results" / "records.json")["records"]
    exact = _read_json(CASE / "source_exact.json")["records"]
    if len(records) != 6 or [r["id"] for r in records] != [r["structure"] for r in exact]:
        raise RuntimeError("Published-case record identities do not match")
    for record, row in zip(records, exact):
        metrics = record["metrics"]
        if metrics["cells"]["value"] != int(row["versatiles_per_bit"]):
            raise RuntimeError("Published-case resource mismatch")
        for field, source in (("value", "fmax_mean_mhz"), ("lower", "fmax_max_mhz"), ("upper", "fmax_min_mhz")):
            if not math.isclose(metrics["period_ns"][field], 1000 / float(row[source]), rel_tol=1e-15):
                raise RuntimeError("Published-case reciprocal-frequency mismatch")
    return records, exact


RECORDS, EXACT = _load_case()


def _number(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


def analyze(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object")
    allowed = {"cells_cap", "frequency_mhz", "scope", "require_protection", "include_stability", "records", "limits"}
    if set(payload) - allowed:
        raise ValueError("Unsupported request field")
    protect = payload.get("require_protection", False)
    include_stability = payload.get("include_stability", False)
    if not isinstance(protect, bool) or not isinstance(include_stability, bool):
        raise ValueError("Protection and stability options must be boolean")
    custom = "records" in payload
    if custom:
        if set(payload) & {"cells_cap", "frequency_mhz", "scope"}:
            raise ValueError("Custom records use objective limits rather than published-case controls")
        records = payload["records"]
        if not isinstance(records, list) or not 1 <= len(records) <= MAX_RECORDS:
            raise ValueError(f"Supply between 1 and {MAX_RECORDS} records")
        if include_stability:
            raise ValueError("Web stability analysis is available for the published example; use the CLI for custom scales")
        limits = payload.get("limits", {})
        rows = []
        scope = "custom_records"
    else:
        if "limits" in payload:
            raise ValueError("Published-case controls use cells_cap and frequency_mhz")
        cells = _number(payload.get("cells_cap", 40), "Resource cap", 0, 1000000)
        frequency = _number(payload.get("frequency_mhz", 32), "Frequency requirement", 0.001, 1000000)
        scope = payload.get("scope", "all_six")
        if scope not in SCOPES:
            raise ValueError("Unknown candidate scope")
        start = SCOPES[scope] or 0
        records = copy.deepcopy(RECORDS[start:])
        rows = copy.deepcopy(EXACT[start:])
        limits = {"cells": cells, "period_ns": 1000 / frequency}
    result = compare(records, limits=limits, require_verified_protection=protect)
    output = {
        "software": "RadPareto", "version": __version__, "source_revision": SOURCE_REVISION,
        "scope": scope, "request": payload, "records": records, "source_rows": rows,
        "comparison": result,
        "source": None if custom else {
            "doi": "10.3390/electronics15225390", "tables": "9 and 10",
            "url": "https://www.mdpi.com/2079-9292/15/22/5390", "license": "CC BY 4.0",
            "numeric_sha256": hashlib.sha256((CASE / "source_tables.csv").read_bytes()).hexdigest(),
            "interpretation": "Published numerical summaries of three implementation runs; individual runs and source HDL were not obtained. Ranges are observed extrema, not confidence intervals or future-run guarantees. Budgets are analyst-selected what-if inputs. Cost screening does not establish radiation protection."
        },
        "data_handling": "The application computes in memory and does not save submitted records. Standard server access logs may retain request metadata, but not JSON bodies."
    }
    if include_stability and result["status"] == "accepted":
        output["stability"] = stability(records, scales={"cells": 1, "period_ns": 1}, limits=limits,
            require_verified_protection=protect)
        output["stability_assumption"] = "Each dimension widens by t times its declared scale: 1 VersaTile per bit and 1 ns. These scales are sensitivity assumptions, not measured error."
    return output


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "")
    headers = [("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "strict-origin-when-cross-origin"),
               ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
               ("Cache-Control", "no-store")]

    def respond(status, body, content_type="application/json; charset=utf-8", extra=()):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        start_response(status, headers + [("Content-Type", content_type), ("Content-Length", str(len(body)))] + list(extra))
        return [] if method == "HEAD" else [body]

    if path == PREFIX and method in ("GET", "HEAD"):
        return respond("308 Permanent Redirect", b"", extra=[("Location", PREFIX + "/")])
    assets = {PREFIX + "/": ("index.html", "text/html; charset=utf-8"),
              PREFIX + "/app.js": ("app.js", "text/javascript; charset=utf-8"),
              PREFIX + "/styles.css": ("styles.css", "text/css; charset=utf-8")}
    if path in assets and method in ("GET", "HEAD"):
        file, mime = assets[path]
        return respond("200 OK", (STATIC / file).read_bytes(), mime)
    if path == PREFIX + "/health" and method in ("GET", "HEAD"):
        return respond("200 OK", {"status": "ok", "software": "RadPareto", "version": __version__, "source_revision": SOURCE_REVISION})
    if path == PREFIX + "/api/source.csv" and method in ("GET", "HEAD"):
        return respond("200 OK", (CASE / "source_tables.csv").read_bytes(), "text/csv; charset=utf-8",
                       [("Content-Disposition", 'attachment; filename="Ma2026_source_tables_9_10.csv"')])
    if path == PREFIX + "/api/example" and method in ("GET", "HEAD"):
        return respond("200 OK", analyze({"cells_cap": 40, "frequency_mhz": 32, "scope": "all_six"}))
    if path == PREFIX + "/api/analyze" and method == "POST":
        origin = environ.get("HTTP_ORIGIN")
        if origin and urlsplit(origin).netloc != environ.get("HTTP_HOST"):
            return respond("403 Forbidden", {"error": "Cross-origin requests are not permitted"})
        if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
            return respond("415 Unsupported Media Type", {"error": "Use application/json"})
        try:
            length = int(environ.get("CONTENT_LENGTH", "0"))
            if length <= 0 or length > MAX_BODY:
                return respond("413 Content Too Large", {"error": "JSON body must be between 1 and 524288 bytes"})
            raw = environ["wsgi.input"].read(length)
            payload = json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))
            return respond("200 OK", analyze(payload))
        except (ValueError, TypeError, UnicodeDecodeError, OverflowError) as exc:
            return respond("400 Bad Request", {"error": str(exc)})
    if path.startswith(PREFIX + "/api/") and method not in ("GET", "HEAD", "POST"):
        return respond("405 Method Not Allowed", {"error": "Method not allowed"})
    return respond("404 Not Found", {"error": "Not found"})


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"Local development preview at http://127.0.0.1:{args.port}{PREFIX}/", flush=True)
    with make_server("127.0.0.1", args.port, application) as server:
        server.serve_forever()
