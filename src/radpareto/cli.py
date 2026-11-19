"""Local JSON CLI. Exit 0 success, 2 refusal/schema/input error, 3 I/O error."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from .compare import batch_compare, compare
from .validation import EvidenceError, validate_document
from . import __version__

MAX_INPUT_BYTES = 10 * 1024 * 1024


def _no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _read_document_with_hash(path):
    with Path(path).open("rb") as f:
        raw = f.read(MAX_INPUT_BYTES+1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Input exceeds 10 MiB")
    parsed = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_no_duplicates,
                        parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON number: {v}")))
    return parsed, hashlib.sha256(raw).hexdigest()


def read_document(path):
    return _read_document_with_hash(path)[0]


def _emit(result, output):
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+"\n"
    if output is None:
        print(payload, end="")
        return
    path = Path(output)
    # Replace atomically only once the complete serializable result is available.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".radpareto-", suffix=".tmp", delete=False) as f:
            temp_name = f.name
            f.write(payload)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="radpareto", description="Compare source-located cost evidence; no radiation qualification.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "compare", "batch"):
        p = sub.add_parser(command)
        p.add_argument("input", help="UTF-8 evidence JSON")
        p.add_argument("--output", help="Write JSON result to this file")
        if command == "compare":
            p.add_argument("--limit", action="append", default=[], metavar="OBJECTIVE=MAX")
            p.add_argument("--require-verified-protection", action="store_true")
    args = parser.parse_args(argv)
    input_sha256 = None
    input_schema_version = None
    try:
        if args.output and Path(args.output).resolve() == Path(args.input).resolve():
            raise ValueError("Output must not overwrite the input evidence file")
        document, input_sha256 = _read_document_with_hash(args.input)
        input_schema_version = document.get("schema_version") if isinstance(document, dict) else None
        records = validate_document(document)
        if args.command == "validate":
            result = {"status": "accepted", "validation": "structural_only", "records": len(records),
                      "warnings": ["Schema validation does not authenticate sources or establish scientific comparability."]}
        elif args.command == "batch":
            result = batch_compare(records)
        else:
            limits = {}
            for spec in args.limit:
                name, sep, value = spec.partition("=")
                if not sep or not name or name in limits:
                    raise ValueError("Each --limit must name a unique objective as OBJECTIVE=MAX")
                limits[name] = float(value)
            result = compare(records, limits=limits, require_verified_protection=args.require_verified_protection)
        code = 0 if result["status"] == "accepted" else 2
    except EvidenceError as exc:
        result, code = {"status": "refused", "reasons": [exc.as_dict()]}, 2
    except (ValueError, UnicodeError, RecursionError) as exc:
        result, code = {"status": "refused", "reasons": [{"code": "INVALID_INPUT", "message": str(exc)}]}, 2
    except OSError as exc:
        result, code = {"status": "refused", "reasons": [{"code": "INPUT_IO_ERROR", "message": str(exc)}]}, 3
    result["replay"] = {"software": "radpareto", "software_version": __version__,
                        "result_schema_version": "1.0", "input_schema_version": input_schema_version,
                        "input_sha256": input_sha256, "command": args.command,
                        "options": {"limits": getattr(args, "limit", []),
                                    "require_verified_protection": getattr(args, "require_verified_protection", False)}}
    try:
        # Never overwrite input even with an error report.
        out = args.output
        if out and Path(out).resolve() == Path(args.input).resolve():
            out = None
        _emit(result, out)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "refused", "reasons": [{"code": "OUTPUT_IO_ERROR", "message": str(exc)}]}))
        return 3
    return code
