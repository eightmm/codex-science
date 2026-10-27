import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "dimensional-analysis-units" / "input.json"
QUALITY = ROOT / "authored-skills" / "dimensional-analysis-units" / "quality.json"
SCRIPT = ROOT / "scripts" / "check_dimensions.py"

SEEDED_FAILURE_TESTS = {
    "equation-dimension-mismatch": "test_seeded_failure_equation_dimension_mismatch",
    "unknown-unit": "test_seeded_failure_unknown_unit",
    "incompatible-conversion": "test_seeded_failure_incompatible_conversion",
    "dimensionful-exponential-argument": "test_seeded_failure_dimensionful_exponential_argument",
}


class DimensionalAnalysisUnitsAcceptanceTests(unittest.TestCase):
    def run_check(self, payload: dict) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "input.json"
            output_path = Path(temporary_directory) / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--require-clean",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            receipt = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
            return completed, receipt

    def fixture_payload(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_acceptance_fixture_passes_public_entry_point(self) -> None:
        completed, receipt = self.run_check(self.fixture_payload())
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("Success! Data written to:", completed.stdout)
        self.assertIsNotNone(receipt)
        self.assertEqual("passed", receipt["status"])
        self.assertEqual("mechanics-acceptance", receipt["check_id"])
        self.assertEqual("claim-newton-work", receipt["claim_id"])
        self.assertEqual([True, True], [item["compatible"] for item in receipt["equations"]])
        self.assertEqual([1.0, 298.15], [item["converted"] for item in receipt["conversions"]])
        self.assertEqual([], receipt["findings"])

    def test_seeded_failure_equation_dimension_mismatch(self) -> None:
        payload = self.fixture_payload()
        payload["equations"][0]["right"] = "mass*distance"
        completed, receipt = self.run_check(payload)
        self.assertEqual(1, completed.returncode)
        self.assertIsNotNone(receipt)
        self.assertEqual("findings", receipt["status"])
        self.assertIn("Equation newton-second-law is dimensionally inconsistent", receipt["findings"][0]["message"])

    def test_seeded_failure_unknown_unit(self) -> None:
        payload = self.fixture_payload()
        payload["variables"]["distance"] = "furlong"
        completed, _ = self.run_check(payload)
        self.assertEqual(1, completed.returncode)
        self.assertIn("unknown unit: furlong", completed.stderr)

    def test_seeded_failure_incompatible_conversion(self) -> None:
        payload = self.fixture_payload()
        payload["conversions"][0]["to"] = "s"
        completed, receipt = self.run_check(payload)
        self.assertEqual(1, completed.returncode)
        self.assertIsNotNone(receipt)
        self.assertEqual("findings", receipt["status"])
        self.assertIn("Conversion centimetres-to-metres failed", receipt["findings"][0]["message"])

    def test_seeded_failure_dimensionful_exponential_argument(self) -> None:
        payload = self.fixture_payload()
        payload["equations"][0]["right"] = "exp(distance)"
        completed, receipt = self.run_check(payload)
        self.assertEqual(1, completed.returncode)
        self.assertIsNotNone(receipt)
        self.assertEqual("findings", receipt["status"])
        self.assertIn("exp requires a dimensionless argument", receipt["findings"][0]["message"])

    def test_quality_seeded_failures_have_matching_tests(self) -> None:
        quality = json.loads(QUALITY.read_text(encoding="utf-8"))
        declared = set(quality["seeded_failures"])
        self.assertEqual(declared, set(SEEDED_FAILURE_TESTS))
        for failure, method_name in SEEDED_FAILURE_TESTS.items():
            with self.subTest(failure=failure):
                self.assertTrue(callable(getattr(self, method_name, None)), method_name)


if __name__ == "__main__":
    unittest.main()
