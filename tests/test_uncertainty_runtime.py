"""Scale and validity regressions for uncertainty propagation."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science.uncertainty_runtime import (
    _variance,
    review_uncertainty_propagation,
    run_uncertainty_propagation,
    validate_uncertainty_propagation,
)
from codex_science.safe_expression import canonical_sha256


class UncertaintyValidityTests(unittest.TestCase):
    def propagate(self, expression, inputs, **overrides):
        payload = {
            "schema_version": 1,
            "propagation_id": "u",
            "claim_id": "c",
            "expression": expression,
            "inputs": [
                {"name": name, "mean": mean, "standard_uncertainty": uncertainty}
                for name, mean, uncertainty in inputs
            ],
            "method": "both",
            "seed": 1,
            "samples": 10000,
        }
        payload.update(overrides)
        before = copy.deepcopy(payload)
        try:
            return run_uncertainty_propagation(payload)
        finally:
            self.assertEqual(before, payload)

    def test_overflowing_sample_statistics_are_recovered_or_refused(self):
        for value in (0.0, 1e308, -1e308, sys.float_info.max):
            with self.subTest(value=value):
                result = self.propagate(str(value), [("x", 0, 0)], method="monte-carlo", samples=1000)
                self.assertEqual(value, result["monte_carlo"]["mean"])
                self.assertEqual(0.0, result["monte_carlo"]["standard_uncertainty"])
                self.assertEqual("passed", result["status"])
                validate_uncertainty_propagation(result)
        # A representable standard deviation can have an overflowing variance.
        draws = [-1.0, 1.0] * 500
        with patch("codex_science.uncertainty_runtime.random.Random.gauss", side_effect=draws):
            result = self.propagate("1e200 if x > 0.5 else -1e200", [("x", 0, 1)], method="monte-carlo", samples=1000)
        self.assertEqual(0.0, result["monte_carlo"]["mean"])
        self.assertAlmostEqual(math.sqrt(1000 / 999), result["monte_carlo"]["standard_uncertainty"] / 1e200)
        with patch("codex_science.uncertainty_runtime.random.Random.gauss", side_effect=draws):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.propagate(
                    f"{sys.float_info.max} if x > 0.5 else -{sys.float_info.max}",
                    [("x", 0, 1)], method="monte-carlo", samples=1000,
                )
        with patch("codex_science.uncertainty_runtime._quantile", return_value=math.inf):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.propagate("1", [("x", 0, 0)], method="monte-carlo", samples=1000)
        result = self.propagate("1", [("x", 0, 0)], method="monte-carlo", samples=1000)
        for value in (math.inf, -math.inf, math.nan):
            for section, field in (("monte_carlo", "mean"), ("linear", "variance"), ("nonlinearity", "mean_shift_in_uncertainty_units")):
                forged = copy.deepcopy(result)
                forged[section][field] = value
                forged.pop("fingerprint")
                forged["fingerprint"] = canonical_sha256(forged)
                with self.subTest(section=section, field=field, value=value), self.assertRaisesRegex(ValueError, "finite"):
                    validate_uncertainty_propagation(forged)

    def test_diagonal_conflicts_are_relative_and_derived_value_is_retained(self):
        for uncertainty in (0.0, 1e-8, 1.0):
            derived = uncertainty ** 2
            boundary = math.nextafter(math.nextafter(derived * (1 + 1e-9), derived), derived)
            for value in (derived, derived * (1 + 0.5e-9), boundary):
                with self.subTest(uncertainty=uncertainty, value=value):
                    result = self.propagate(
                        "x", [("x", 0, uncertainty)], method="linear",
                        covariance=[{"left": "x", "right": "x", "value": value}],
                    )
                    self.assertEqual(derived, result["covariance"][0][0])
            conflicts = (1e-30,) if uncertainty == 0 else (0, derived * (1 + 2e-9))
            for value in conflicts:
                with self.subTest(uncertainty=uncertainty, conflict=value):
                    with self.assertRaisesRegex(ValueError, "diagonal covariance conflicts"):
                        self.propagate(
                            "x", [("x", 0, uncertainty)], method="linear",
                            covariance=[{"left": "x", "right": "x", "value": value}],
                        )

    def test_small_indefinite_covariance_is_refused(self):
        for scale in (1e-7, 1.0):
            for correlation in (-2.0, 2.0, 1 + 2e-12):
                with self.subTest(scale=scale, correlation=correlation):
                    with self.assertRaisesRegex(ValueError, "not positive semidefinite"):
                        self.propagate(
                            "x-y", [("x", 0, scale), ("y", 0, scale)], method="linear",
                            covariance=[{"left": "x", "right": "y", "value": correlation * scale ** 2}],
                        )
        with self.assertRaisesRegex(ValueError, "not positive semidefinite"):
            self.propagate(
                "x+y+z", [("x", 0, 1e-7), ("y", 0, 1e-7), ("z", 0, 1e-7)], method="linear",
                covariance=[
                    {"left": "x", "right": "y", "value": 9e-15},
                    {"left": "x", "right": "z", "value": 9e-15},
                    {"left": "y", "right": "z", "value": -9e-15},
                ],
            )

    def test_perfect_correlation_survives_disparate_scales(self):
        for correlation in (1.0, -1.0):
            with self.subTest(correlation=correlation):
                result = self.propagate(
                    f"x/1e-13-({correlation})*y", [("x", 0, 1e-13), ("y", 0, 1)],
                    method="monte-carlo",
                    covariance=[{"left": "x", "right": "y", "value": correlation * 1e-13}],
                )
                self.assertLess(result["monte_carlo"]["standard_uncertainty"], 1e-12)
                self.assertEqual([], result["findings"])
        for correlation in (0.0, 1.0, 1 + 0.25e-12):
            result = self.propagate(
                "x-y", [("x", 0, 1e-7), ("y", 0, 1e-7)], method="linear",
                covariance=[{"left": "x", "right": "y", "value": correlation * 1e-14}],
            )
            self.assertGreaterEqual(result["linear"]["variance"], 0)

    def test_zero_uncertainty_cannot_hide_nonzero_covariance(self):
        for value in (0.0, 1e-30):
            options = {"method": "linear", "covariance": [{"left": "x", "right": "y", "value": value}]}
            if value:
                with self.assertRaisesRegex(ValueError, "singular and inconsistent"):
                    self.propagate("x+y", [("x", 0, 0), ("y", 0, 1)], **options)
            else:
                result = self.propagate("x+y", [("x", 0, 0), ("y", 0, 1)], **options)
                self.assertEqual(1.0, result["linear"]["variance"])
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.propagate(
                "x", [("x", 0, 1e-8)],
                covariance=[{"left": "x", "right": "x", "value": "bad"}],
            )

    def test_negative_variance_refusal_uses_cancellation_scale(self):
        for scale in (1e-14, 1.0):
            with self.subTest(scale=scale):
                with self.assertRaisesRegex(ValueError, "linear propagation produced negative variance"):
                    _variance([1, 1], [[scale, -2 * scale], [-2 * scale, scale]])
                self.assertEqual(0.0, _variance([1, 1], [[scale, -scale], [-scale, scale]]))
                rounded = -scale * (1 + 1e-14)
                self.assertEqual(0.0, _variance([1, 1], [[scale, rounded], [rounded, scale]]))
        self.assertEqual(0.0, _variance([], []))

    def test_step_unstable_derivative_is_a_linear_review_finding(self):
        for method in ("linear", "both"):
            with self.subTest(method=method):
                result = self.propagate("sin(1000000*x)", [("x", 1, 1e-9)], method=method, samples=1000)
                finding = next(item for item in result["findings"] if item["code"] == "linearization-derivative-unstable")
                self.assertEqual("major", finding["severity"])
                self.assertIn("x", finding["message"])
                self.assertEqual("findings", result["status"])
                self.assertEqual(result["findings"], review_uncertainty_propagation(result))
        stable = self.propagate("sin(1000*x)", [("x", 1, 1e-9)], method="linear")
        self.assertEqual([], stable["findings"])
        self.assertAlmostEqual(1000 * math.cos(1000), stable["linear"]["gradient"][0], delta=0.001)
        zero = self.propagate("x*x", [("x", 0, 1e-9)], method="linear", covariance=[])
        self.assertEqual([0.0], zero["linear"]["gradient"])
        with self.assertRaises(ValueError):
            self.propagate("", [("x", 0, 1)])

    def test_stationary_cubic_completes_for_all_methods(self):
        for expression in ("x**3", "2*x**3"):
            for uncertainty in (1, 2, 1e-3, 1e3):
                for method in ("linear", "monte-carlo", "both"):
                    with self.subTest(expression=expression, uncertainty=uncertainty, method=method):
                        result = self.propagate(expression, [("x", 0, uncertainty)], method=method, samples=1000)
                        expected = (2 if expression == "2*x**3" else 1) * (uncertainty * 1e-3) ** 2
                        self.assertAlmostEqual(expected, result["linear"]["gradient"][0], delta=expected * 1e-14)
                        self.assertNotIn("linearization-derivative-unstable", {item["code"] for item in result["findings"]})
                        if method != "linear":
                            self.assertEqual(1000, result["monte_carlo"]["accepted_samples"])
                        if method == "both":
                            self.assertIn("nonlinear-propagation-disagreement", {item["code"] for item in result["findings"]})

    def test_monte_carlo_does_not_require_stable_linear_derivatives(self):
        for expression, inputs in (
            ("sin(1000000*x)", [("x", 1, 1e-9)]),
            ("log(abs(x))", [("x", 0.0005, 1)]),
        ):
            with self.subTest(expression=expression):
                result = self.propagate(expression, inputs, method="monte-carlo", samples=1000)
                self.assertEqual(1000, result["monte_carlo"]["accepted_samples"])
                self.assertEqual([], result["findings"])

    def test_failed_refinement_is_a_linear_review_finding(self):
        for method in ("linear", "both"):
            with self.subTest(method=method):
                result = self.propagate("log(abs(x))", [("x", 0.0005, 1)], method=method, samples=1000)
                finding = next(item for item in result["findings"] if item["code"] == "linearization-derivative-unstable")
                self.assertEqual("major", finding["severity"])
                self.assertIn("x", finding["message"])
                self.assertIn("failed", finding["message"])
                self.assertEqual("findings", result["status"])
                self.assertAlmostEqual(math.log(3) / 0.002, result["linear"]["gradient"][0])
                self.assertEqual(result["findings"], review_uncertainty_propagation(result))
                if method == "both":
                    self.assertEqual(1000, result["monte_carlo"]["accepted_samples"])
        for method in ("linear", "monte-carlo", "both"):
            with self.subTest(base_failure=method), self.assertRaisesRegex(ValueError, "function log failed"):
                self.propagate("log(abs(x))", [("x", 0.001, 1)], method=method, samples=1000)
        for error in (ValueError("domain"), OverflowError("overflow"), ZeroDivisionError("zero"), None):
            with self.subTest(refinement_error=error):
                values = [1.0, 1.002, 0.998, error if error is not None else float("inf"), 1.0]
                with patch("codex_science.uncertainty_runtime.evaluate_expression", side_effect=values):
                    result = self.propagate("x", [("x", 1, 0)], method="linear")
                self.assertEqual("linearization-derivative-unstable", result["findings"][0]["code"])
                self.assertEqual(0.0, result["linear"]["standard_uncertainty"])

    def test_derivative_stability_relative_limit(self):
        width = 2.0 ** -20
        for change in (0, 0.5, 1, 1.01):
            for uncertainty in (0.0, 1e-9):
                with self.subTest(change=change, uncertainty=uncertainty):
                    # A binary step makes the 1% equality case exact.
                    values = [0.0, 100 * 2 * width, 0.0, (100 - change) * width, 0.0]
                    with patch("codex_science.uncertainty_runtime.evaluate_expression", side_effect=values):
                        result = self.propagate("x", [("x", width / 1e-6, uncertainty)], method="linear")
                    self.assertEqual(change > 1 and uncertainty > 0, bool(result["findings"]))

    def test_derivative_stability_uses_total_linear_uncertainty(self):
        width = 2.0 ** -20
        values = [0.0, 100 * 2 * width, 0.0, 98 * width, 0.0,
                  1000 * 2 * width, 0.0, 1000 * width, 0.0]
        with patch("codex_science.uncertainty_runtime.evaluate_expression", side_effect=values):
            result = self.propagate("x+y", [("x", width / 1e-6, 1e-9), ("y", width / 1e-6, 1e-9)], method="linear")
        self.assertEqual([], result["findings"])

    def test_derivative_stability_absolute_floor_boundary(self):
        width = 2.0 ** -20
        floor = 16 * math.ulp(1.0) / width
        for factor in (0, 0.5, 1, 2):
            with self.subTest(factor=factor):
                derivative = factor * floor
                values = [1.0, 1.0 + 2 * width * derivative, 1.0, 1.0, 1.0,
                          1.0 + 2 * width, 1.0, 1.0 + width, 1.0]
                with patch("codex_science.uncertainty_runtime.evaluate_expression", side_effect=values):
                    result = self.propagate("x+y", [("x", width / 1e-6, 1e-9), ("y", width / 1e-6, 0)], method="linear")
                self.assertEqual(factor > 1, bool(result["findings"]))

    def test_domain_filtering_counterexample_is_a_major_review_finding(self):
        result = self.propagate("log(x)", [("x", 2, 1)], method="monte-carlo")
        self.assertEqual(205, result["monte_carlo"]["failed_samples"])
        self.assertEqual("findings", result["status"])
        finding = result["findings"][0]
        self.assertEqual("monte-carlo-domain-filtering", finding["code"])
        self.assertEqual("major", finding["severity"])
        self.assertIn("conditional on the accepted samples", finding["message"])
        self.assertEqual(result["findings"], review_uncertainty_propagation(result))

    def test_domain_filtering_severity_and_refusal_boundaries(self):
        for failed in (0, 1, 9, 10, 100, 101):
            with self.subTest(failed=failed):
                draws = [-3.0] * failed + [0.0] * (1000 - failed)
                with patch("codex_science.uncertainty_runtime.random.Random.gauss", side_effect=draws):
                    if failed > 100:
                        with self.assertRaisesRegex(ValueError, "too many Monte Carlo samples failed"):
                            self.propagate("log(x)", [("x", 2, 1)], method="monte-carlo", samples=1000)
                        continue
                    result = self.propagate("log(x)", [("x", 2, 1)], method="monte-carlo", samples=1000)
                self.assertEqual(failed, result["monte_carlo"]["failed_samples"])
                if failed:
                    self.assertEqual(1, len(result["findings"]))
                    self.assertEqual("major" if failed >= 10 else "minor", result["findings"][0]["severity"])
                    self.assertEqual("findings" if failed >= 10 else "passed", result["status"])
                else:
                    self.assertEqual([], result["findings"])

    def test_public_command_refuses_invalid_clean_results(self):
        root = Path(__file__).resolve().parents[1]
        cases = (
            ("x", [("x", 0, 1e-8)], [{"left": "x", "right": "x", "value": 0}],
             "linear", "diagonal covariance conflicts"),
            ("x-y", [("x", 0, 1e-7), ("y", 0, 1e-7)], [{"left": "x", "right": "y", "value": 2e-14}],
             "linear", "not positive semidefinite"),
            ("sin(1000000*x)", [("x", 1, 1e-9)], [], "linear", None),
            ("log(abs(x))", [("x", 0.0005, 1)], [], "linear", None),
            ("log(abs(x))", [("x", 0.0005, 1)], [], "both", None),
            ("log(x)", [("x", 2, 1)], [], "monte-carlo", None),
        )
        for expression, inputs, covariance, method, error in cases:
            with self.subTest(expression=expression), tempfile.TemporaryDirectory() as directory:
                payload = {
                    "schema_version": 1, "propagation_id": "u", "claim_id": "c",
                    "expression": expression, "covariance": covariance, "method": method,
                    "inputs": [
                        {"name": name, "mean": mean, "standard_uncertainty": uncertainty}
                        for name, mean, uncertainty in inputs
                    ],
                    "seed": 1, "samples": 10000,
                }
                source = Path(directory) / "input.json"
                output = Path(directory) / "output.json"
                source.write_text(json.dumps(payload), encoding="utf-8")
                process = subprocess.run(
                    [sys.executable, str(root / "scripts/propagate_uncertainty.py"), str(source),
                     "--output", str(output), "--require-clean"],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(1, process.returncode, process.stderr)
                if error:
                    self.assertIn(error, process.stderr)
                    self.assertFalse(output.exists())
                else:
                    receipt = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual("findings", receipt["status"])
                    expected = "monte-carlo-domain-filtering" if method == "monte-carlo" else "linearization-derivative-unstable"
                    self.assertEqual(expected, receipt["findings"][0]["code"])


if __name__ == "__main__":
    unittest.main()
