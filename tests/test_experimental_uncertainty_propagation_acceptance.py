"""Executable acceptance and seeded-failure tests for uncertainty propagation."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/experimental-uncertainty-propagation/input.json"
QUALITY = ROOT / "authored-skills/experimental-uncertainty-propagation/quality.json"
ENTRY_POINT = ROOT / "scripts/propagate_uncertainty.py"

SEEDED_FAILURE_TESTS = {
    "non-positive-semidefinite-covariance": "test_non_positive_semidefinite_covariance_is_refused",
    "missing-monte-carlo-seed": "test_missing_monte_carlo_seed_is_refused",
    "nonlinear-propagation-disagreement": "test_nonlinear_disagreement_fails_clean_verdict",
    "non-finite-standard-uncertainty": "test_non_finite_standard_uncertainty_is_refused",
}


class ExperimentalUncertaintyPropagationAcceptanceTests(unittest.TestCase):
    def run_input(self, payload: dict[str, Any]) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            input_path = temporary / "input.json"
            output_path = temporary / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(ENTRY_POINT), str(input_path), "--output", str(output_path), "--require-clean"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            output = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
            return process, output

    def fixture(self) -> dict[str, Any]:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_acceptance_fixture_runs_through_public_entry_point(self) -> None:
        process, output = self.run_input(self.fixture())
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIsNotNone(output)
        assert output is not None
        self.assertEqual("passed", output["status"])
        self.assertEqual("uncertainty-product-acceptance", output["propagation_id"])
        self.assertAlmostEqual(6.0, output["nominal_value"])
        self.assertAlmostEqual(0.5567764362834194, output["linear"]["standard_uncertainty"], places=9)
        self.assertEqual(20260722, output["monte_carlo"]["seed"])
        self.assertEqual(5000, output["monte_carlo"]["requested_samples"])
        self.assertEqual([], output["findings"])

    def test_non_positive_semidefinite_covariance_is_refused(self) -> None:
        payload = self.fixture()
        payload["covariance"] = [{"left": "x", "right": "y", "value": 1.0}]
        process, output = self.run_input(payload)
        self.assertEqual(1, process.returncode)
        self.assertIn("covariance matrix is not positive semidefinite", process.stderr)
        self.assertIsNone(output)

    def test_missing_monte_carlo_seed_is_refused(self) -> None:
        payload = self.fixture()
        payload.pop("seed")
        process, output = self.run_input(payload)
        self.assertEqual(1, process.returncode)
        self.assertIn("Monte Carlo propagation requires an explicit integer seed", process.stderr)
        self.assertIsNone(output)

    def test_nonlinear_disagreement_fails_clean_verdict(self) -> None:
        payload = self.fixture()
        payload["expression"] = "exp(x)"
        payload["inputs"] = [{"name": "x", "mean": 0.0, "standard_uncertainty": 1.0}]
        payload["covariance"] = []
        process, output = self.run_input(payload)
        self.assertEqual(1, process.returncode)
        self.assertIsNotNone(output)
        assert output is not None
        self.assertEqual("findings", output["status"])
        self.assertIn("nonlinear-propagation-disagreement", [item["code"] for item in output["findings"]])
        self.assertIn("disagree materially", output["findings"][0]["message"])

    def test_non_finite_standard_uncertainty_is_refused(self) -> None:
        payload = self.fixture()
        payload["inputs"][0]["standard_uncertainty"] = float("inf")
        process, output = self.run_input(payload)
        self.assertEqual(1, process.returncode)
        self.assertIn("inputs[0].standard_uncertainty must be finite", process.stderr)
        self.assertIsNone(output)

    def test_quality_seeded_failures_have_matching_tests(self) -> None:
        quality = json.loads(QUALITY.read_text(encoding="utf-8"))
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        for failure_name, method_name in SEEDED_FAILURE_TESTS.items():
            with self.subTest(failure=failure_name):
                self.assertTrue(hasattr(self, method_name), method_name)


if __name__ == "__main__":
    unittest.main()
