import copy
import unittest

from codex_science.numerical_verification import run_numerical_verification
from codex_science.uncertainty_runtime import run_uncertainty_propagation
from codex_science.units_runtime import convert_value, dimension_dict, parse_unit, run_dimension_check


class NumericalUnitsUncertaintyTests(unittest.TestCase):
    def numerical_input(self) -> dict:
        return {
            "schema_version": 1,
            "verification_id": "V1",
            "claim_id": "C1",
            "method": "manufactured second-order fixture",
            "reference_value": 1.0,
            "thresholds": {
                "minimum_order": 1.8,
                "max_residual": 0.1,
                "max_invariant_deviation": 0.1,
                "max_cross_method_z": 3.0,
            },
            "solver": {
                "precision": "binary64",
                "relative_tolerance": 1e-10,
                "absolute_tolerance": 1e-12,
            },
            "refinements": [
                {"resolution": 0.4, "estimate": 1.08, "residual": 0.064, "invariants": {"mass": 0.016}},
                {"resolution": 0.2, "estimate": 1.02, "residual": 0.008, "invariants": {"mass": 0.004}},
                {"resolution": 0.1, "estimate": 1.005, "residual": 0.001, "invariants": {"mass": 0.001}},
                {"resolution": 0.05, "estimate": 1.00125, "residual": 0.000125, "invariants": {"mass": 0.00025}},
            ],
            "cross_method": [
                {"method": "A", "estimate": 1.0, "uncertainty": 0.001},
                {"method": "B", "estimate": 1.0005, "uncertainty": 0.001},
            ],
        }

    def test_numerical_verification_passes_second_order_fixture(self) -> None:
        result = run_numerical_verification(self.numerical_input())
        self.assertEqual("passed", result["status"])
        self.assertGreaterEqual(result["minimum_observed_order"], 1.99)
        self.assertLessEqual(result["maximum_residual"], 0.064)
        self.assertEqual([], result["findings"])

    def test_numerical_verification_detects_error_and_cross_method_failures(self) -> None:
        payload = self.numerical_input()
        payload["refinements"][2]["estimate"] = 1.04
        payload["cross_method"][1] = {"method": "B", "estimate": 1.1, "uncertainty": 0.001}
        result = run_numerical_verification(payload)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("nonmonotone-error", codes)
        self.assertIn("convergence-order-below-threshold", codes)
        self.assertIn("cross-method-disagreement", codes)
        self.assertEqual("findings", result["status"])

    def test_unit_conversion_and_dimensional_equations(self) -> None:
        self.assertAlmostEqual(1.0, convert_value(100.0, "cm", "m"))
        self.assertAlmostEqual(298.15, convert_value(25.0, "degC", "K"))
        force = parse_unit("kg*m/s^2")
        self.assertEqual(dimension_dict(parse_unit("N").dimension), dimension_dict(force.dimension))
        payload = {
            "schema_version": 1,
            "check_id": "units",
            "claim_id": "C-unit",
            "variables": {"m": "kg", "a": "m/s^2", "F": "N", "d": "m", "E": "J"},
            "equations": [
                {"id": "force", "left": "F", "right": "m*a"},
                {"id": "energy", "left": "E", "right": "F*d"},
            ],
            "conversions": [{"id": "length", "value": 100.0, "from": "cm", "to": "m"}],
        }
        result = run_dimension_check(payload)
        self.assertEqual("passed", result["status"])
        self.assertTrue(all(item["compatible"] for item in result["equations"]))

    def test_dimension_check_rejects_inconsistent_equation(self) -> None:
        result = run_dimension_check(
            {
                "schema_version": 1,
                "check_id": "bad-units",
                "claim_id": "C-bad",
                "variables": {"x": "m", "t": "s"},
                "equations": [{"id": "bad", "left": "x", "right": "t"}],
                "conversions": [],
            }
        )
        self.assertEqual("findings", result["status"])
        self.assertIn("dimension-mismatch", {item["code"] for item in result["findings"]})
        with self.assertRaises(ValueError):
            convert_value(1.0, "m", "s")

    def uncertainty_input(self) -> dict:
        return {
            "schema_version": 1,
            "propagation_id": "U1",
            "claim_id": "C-U",
            "expression": "x*y",
            "inputs": [
                {"name": "x", "mean": 2.0, "standard_uncertainty": 0.1, "unit": "m"},
                {"name": "y", "mean": 3.0, "standard_uncertainty": 0.2, "unit": "N"},
            ],
            "covariance": [],
            "method": "both",
            "confidence_level": 0.95,
            "seed": 12345,
            "samples": 5000,
            "nonlinearity_threshold": 0.25,
        }

    def test_uncertainty_propagation_is_deterministic_and_agrees_for_product(self) -> None:
        first = run_uncertainty_propagation(self.uncertainty_input())
        second = run_uncertainty_propagation(self.uncertainty_input())
        self.assertEqual(first, second)
        self.assertEqual("passed", first["status"])
        self.assertAlmostEqual(6.0, first["nominal_value"])
        self.assertAlmostEqual(0.5, first["linear"]["standard_uncertainty"], places=9)
        self.assertLess(first["nonlinearity"]["relative_uncertainty_discrepancy"], 0.05)
        self.assertEqual([], first["findings"])

    def test_uncertainty_requires_positive_semidefinite_covariance(self) -> None:
        payload = self.uncertainty_input()
        payload["covariance"] = [{"left": "x", "right": "y", "value": 1.0}]
        with self.assertRaises(ValueError):
            run_uncertainty_propagation(payload)

    def test_monte_carlo_seed_is_required(self) -> None:
        payload = self.uncertainty_input()
        payload.pop("seed")
        with self.assertRaises(ValueError):
            run_uncertainty_propagation(payload)


if __name__ == "__main__":
    unittest.main()
