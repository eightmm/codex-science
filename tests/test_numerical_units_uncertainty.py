import copy
import unittest

from codex_science.numerical_verification import run_numerical_verification
from codex_science.uncertainty_runtime import run_uncertainty_propagation
from codex_science.safe_expression import canonical_sha256
from codex_science.units_runtime import (
    convert_value,
    dimension_dict,
    parse_unit,
    review_dimension_check,
    run_dimension_check,
    validate_dimension_check,
)


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


class UnitsRuntimeContractTests(unittest.TestCase):
    def check_payload(self, **overrides: object) -> dict:
        payload: dict = {
            "schema_version": 1,
            "check_id": "chk",
            "claim_id": "C1",
            "variables": {"x": "m", "t": "s"},
            "equations": [],
            "conversions": [],
        }
        payload.update(overrides)
        return payload

    def assertParseRefused(self, source: str, fragment: str) -> None:
        with self.assertRaises(ValueError) as caught:
            parse_unit(source)
        self.assertIn(fragment, str(caught.exception))

    def test_parse_unit_fraction_exponents(self) -> None:
        self.assertEqual({"length": "1/2"}, dimension_dict(parse_unit("m^(1/2)").dimension))
        self.assertEqual({"length": "-2"}, dimension_dict(parse_unit("m^-2").dimension))
        self.assertEqual({"length": "64"}, dimension_dict(parse_unit("m^64").dimension))

    def test_parse_unit_refuses_bad_exponents(self) -> None:
        self.assertParseRefused("m^(1/0)", "denominator cannot be zero")
        self.assertParseRefused("m^0.5", "integer or rational")
        self.assertParseRefused("m^s", "integer or rational")
        self.assertParseRefused("m^65", "exceeds configured limits")
        self.assertParseRefused("m^(1/17)", "exceeds configured limits")

    def test_unit_power_overflow_is_value_error(self) -> None:
        self.assertParseRefused("(km^64)^64", "non-finite scale")
        self.assertParseRefused("((nm^64)^64)^-1", "zero scale")
        self.assertParseRefused("(nm^64)^64", "zero scale")
        self.assertEqual({"length": "64"}, dimension_dict(parse_unit("km^64").dimension))

    def test_parse_unit_refuses_affine_arithmetic(self) -> None:
        for source in ("degC*m", "m/degC", "degC^2"):
            self.assertParseRefused(source, "affine")
        self.assertEqual(273.15, parse_unit("degC^1").offset)

    def test_parse_unit_refuses_malformed_expressions(self) -> None:
        self.assertParseRefused("", "required")
        self.assertParseRefused("   ", "required")
        self.assertParseRefused("m" * 257, "256 characters")
        self.assertParseRefused("m*", "invalid unit expression")
        self.assertParseRefused("furlong", "unknown unit: furlong")
        self.assertParseRefused("2", "unsupported unit expression element")
        self.assertParseRefused("m+s", "unsupported unit expression element")
        self.assertParseRefused("*".join(["m"] * 71), "too complex")

    def test_parse_unit_accepts_unicode_aliases_and_one(self) -> None:
        self.assertEqual(parse_unit("um").scale, parse_unit("µm").scale)
        self.assertEqual(parse_unit("angstrom").scale, parse_unit("Å").scale)
        self.assertEqual({}, dimension_dict(parse_unit("1").dimension))

    def test_convert_value_refusals(self) -> None:
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(ValueError) as caught:
                convert_value(bad, "m", "cm")
            self.assertIn("must be finite", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            convert_value(1e308, "km", "nm")
        self.assertIn("non-finite", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            convert_value(1.0, "m", "s")
        self.assertIn("incompatible dimensions: m and s", str(caught.exception))

    def test_convert_value_affine_round_trip(self) -> None:
        self.assertAlmostEqual(0.0, convert_value(273.15, "K", "degC"))
        self.assertAlmostEqual(-273.15, convert_value(0.0, "K", "degC"))
        self.assertEqual(0.0, convert_value(0.0, "m", "km"))

    def assertEquationError(self, left: str, right: str, fragment: str, variables: dict | None = None) -> dict:
        payload = self.check_payload(equations=[{"id": "eq", "left": left, "right": right}])
        if variables is not None:
            payload["variables"] = variables
        result = run_dimension_check(payload)
        equation = result["equations"][0]
        self.assertFalse(equation["compatible"])
        self.assertIn(fragment, equation["error"])
        self.assertEqual("findings", result["status"])
        finding = result["findings"][0]
        self.assertEqual(("dimension-mismatch", "critical"), (finding["code"], finding["severity"]))
        self.assertIn(fragment, finding["message"])
        return result

    def test_equation_errors_are_recorded_not_raised(self) -> None:
        self.assertEquationError("x + t", "x", "incompatible dimensions")
        self.assertEquationError("y", "x", "unknown dimensional variable: y")
        self.assertEquationError("'a'", "x", "only numeric constants")
        self.assertEquationError("True", "x", "only numeric constants")
        self.assertEquationError("x < x", "x", "unsupported dimensional expression element")
        self.assertEquationError("x**0.5", "x", "integer or rational")
        self.assertEquationError("exp(x)", "x", "exp requires a dimensionless argument")
        self.assertEquationError("foo(x)", "x", "unsupported dimensional function: foo")
        self.assertEquationError("sqrt(x, x)", "x", "exactly one positional argument")
        self.assertEquationError("sqrt(x=x)", "x", "exactly one positional argument")
        self.assertEquationError("x +", "x", "invalid dimensional expression")
        self.assertEquationError("x" + " + x" * 200, "x", "too complex")
        self.assertEquationError("x" * 4097, "x", "empty or too long", variables={"x": "m"})

    def test_equation_dimension_success_paths(self) -> None:
        payload = self.check_payload(
            variables={"x": "m", "t": "s", "A": "m^2"},
            equations=[
                {"id": "sqrt", "left": "sqrt(A)", "right": "x"},
                {"id": "abs", "left": "abs(-x)", "right": "+x"},
                {"id": "log", "left": "log(x/x) * x", "right": "2.5 * x"},
                {"id": "pow", "left": "x**2", "right": "A"},
                {"id": "ratio", "left": "x/t", "right": "x*t^-1"},
            ],
        )
        result = run_dimension_check(payload)
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["findings"])
        self.assertTrue(all(item["compatible"] and item["error"] is None for item in result["equations"]))
        self.assertEqual({"length": "1", "time": "-1"}, result["equations"][4]["left_dimension"])

    def test_equation_mismatch_without_error_message(self) -> None:
        result = run_dimension_check(self.check_payload(equations=[{"id": "bad", "left": "x", "right": "t"}]))
        self.assertIsNone(result["equations"][0]["error"])
        self.assertEqual("Equation bad is dimensionally inconsistent.", result["findings"][0]["message"])

    def test_equation_default_ids(self) -> None:
        result = run_dimension_check(self.check_payload(equations=[{"left": "x", "right": "x"}], conversions=[{"value": 1, "from": "m", "to": "cm"}]))
        self.assertEqual("equation-0", result["equations"][0]["id"])
        self.assertEqual("conversion-0", result["conversions"][0]["id"])
        self.assertAlmostEqual(100.0, result["conversions"][0]["converted"])

    def test_failed_conversion_becomes_major_finding(self) -> None:
        result = run_dimension_check(self.check_payload(conversions=[{"id": "c", "value": 1, "from": "m", "to": "s"}]))
        self.assertEqual("findings", result["status"])
        conversion = result["conversions"][0]
        self.assertIsNone(conversion["converted"])
        self.assertIn("incompatible dimensions", conversion["error"])
        finding = result["findings"][0]
        self.assertEqual(("unit-conversion-failed", "major"), (finding["code"], finding["severity"]))
        self.assertIn("Conversion c failed", finding["message"])

    def test_run_dimension_check_input_validation(self) -> None:
        cases = [
            (self.check_payload(schema_version=2), "unsupported dimension-check input schema"),
            (self.check_payload(check_id=" "), "check_id and claim_id are required"),
            (self.check_payload(claim_id=""), "check_id and claim_id are required"),
            (self.check_payload(variables={}), "variables must map"),
            (self.check_payload(variables=["m"]), "variables must map"),
            (self.check_payload(variables={"1x": "m"}), "invalid variable name: 1x"),
            (self.check_payload(variables={"x": "furlong"}), "unknown unit: furlong"),
            (self.check_payload(equations={}), "equations must be a list of objects"),
            (self.check_payload(equations=["x"]), "equations must be a list of objects"),
            (self.check_payload(conversions="m"), "conversions must be a list of objects"),
            (self.check_payload(equations=[{"id": "e", "left": "x", "right": " "}]), "equation e requires left and right"),
        ]
        for payload, fragment in cases:
            before = copy.deepcopy(payload)
            with self.subTest(fragment=fragment, payload=payload):
                with self.assertRaises(ValueError) as caught:
                    run_dimension_check(payload)
                self.assertIn(fragment, str(caught.exception))
                self.assertEqual(before, payload)

    def test_result_is_receipt_that_validates_and_is_fingerprinted(self) -> None:
        payload = self.check_payload(equations=[{"id": "ok", "left": "x", "right": "x"}])
        first = run_dimension_check(payload)
        self.assertEqual(first, run_dimension_check(copy.deepcopy(payload)))
        self.assertEqual(64, len(first["fingerprint"]))
        self.assertEqual({"unit": "m", "scale": 1.0, "dimension": {"length": "1"}}, first["variables"]["x"])
        validate_dimension_check(first)
        self.assertEqual([], review_dimension_check(first))

    def test_validate_dimension_check_refusals(self) -> None:
        good = run_dimension_check(self.check_payload())
        cases = []
        for mutate, fragment in (
            (lambda p: p.update(schema_version=2), "unsupported dimension-check receipt schema"),
            (lambda p: p.update(check_id=""), "check_id is required"),
            (lambda p: p.pop("claim_id"), "claim_id is required"),
            (lambda p: p.update(status="bogus"), "invalid dimension-check status"),
            (lambda p: p.update(equations={}), "equations and findings must be lists"),
            (lambda p: p.update(findings=None), "equations and findings must be lists"),
            (lambda p: p.update(fingerprint="abc"), "fingerprint mismatch"),
            (lambda p: p.pop("fingerprint"), "fingerprint mismatch"),
            (lambda p: p.update(limitations=[]), "fingerprint mismatch"),
        ):
            payload = copy.deepcopy(good)
            mutate(payload)
            cases.append((payload, fragment))
        for payload, fragment in cases:
            with self.subTest(fragment=fragment):
                with self.assertRaises(ValueError) as caught:
                    validate_dimension_check(payload)
                self.assertIn(fragment, str(caught.exception))
                review = review_dimension_check(payload)
                self.assertEqual(1, len(review))
                self.assertEqual(("invalid-dimension-check", "critical"), (review[0]["code"], review[0]["severity"]))
                self.assertIn(fragment, review[0]["message"])

    def test_fingerprint_accepts_uppercase_hex(self) -> None:
        good = run_dimension_check(self.check_payload())
        good["fingerprint"] = good["fingerprint"].upper()
        validate_dimension_check(good)

    def test_review_reports_findings_and_unsafe_pass(self) -> None:
        failing = run_dimension_check(self.check_payload(equations=[{"id": "bad", "left": "x", "right": "t"}]))
        review = review_dimension_check(failing)
        self.assertEqual(["dimension-mismatch"], [item["code"] for item in review])
        forged = copy.deepcopy(failing)
        forged["status"] = "passed"
        forged.pop("fingerprint")
        forged["fingerprint"] = canonical_sha256(forged)
        codes = [item["code"] for item in review_dimension_check(forged)]
        self.assertEqual(["dimension-mismatch", "unsafe-dimension-pass"], codes)


if __name__ == "__main__":
    unittest.main()
