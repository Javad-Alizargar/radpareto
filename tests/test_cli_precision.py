"""Regressions for exact integer CLI constraints and numeric syntax."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from radpareto.cli import main
from radpareto.compare import compare


class LimitPrecisionTests(unittest.TestCase):
    def test_large_integer_constraint_matches_python_api(self):
        data = json.loads((Path(__file__).resolve().parents[1]/"examples/rounded_costs.json").read_text())
        data["records"] = [deepcopy(data["records"][0])]
        value = 9007199254740993
        data["records"][0]["metrics"]["area_ratio"].update(
            value=value, lower=value, upper=value, uncertainty_kind="exact")
        expected = compare(data["records"], limits={"area_ratio": value})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"evidence.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["compare", str(path), "--limit", f"area_ratio={value}"])
            actual = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertIsInstance(actual["limits"]["area_ratio"], int)
        self.assertEqual(actual["limits"], expected["limits"])
        self.assertEqual(actual["feasibility"], expected["feasibility"])

    def test_cli_limits_reject_non_numeric_json(self):
        path = Path(__file__).resolve().parents[1]/"examples/rounded_costs.json"
        for value in ("true", "null", '"3"', "[]", "NaN", "Infinity"):
            with self.subTest(value=value), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["compare", str(path), "--limit", f"area_ratio={value}"]), 2)

    def test_json_exponent_limit_remains_supported(self):
        path = Path(__file__).resolve().parents[1]/"examples/rounded_costs.json"
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["compare", str(path), "--limit", "area_ratio=2.5e1"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["limits"]["area_ratio"], 25.0)


if __name__ == "__main__":
    unittest.main()
