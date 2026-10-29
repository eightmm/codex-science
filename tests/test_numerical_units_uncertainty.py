import copy
import unittest

from codex_science.numerical_verification import run_numerical_verification
from codex_science.uncertainty_runtime import (
    review_uncertainty_propagation,
    run_uncertainty_propagation,
    validate_uncertainty_propagation,
)
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

    def test_affine_temperature_arithmetic_fails_in_equations(self) -> None:
        for expression, right, operation in (
            ("temperature*2", "temperature", "multiplied"),
            ("temperature*0", "temperature*0", "multiplied"),
            ("2*temperature", "temperature", "multiplied"),
            ("temperature/2", "temperature", "divided"),
            ("temperature**2", "temperature**2", "exponentiated"),
            ("temperature**0", "temperature**0", "exponentiated"),
            ("sqrt(temperature)", "sqrt(temperature)", "exponentiated"),
        ):
            with self.subTest(expression=expression):
                result = run_dimension_check(self.check_payload(
                    variables={"temperature": "degC"},
                    equations=[{"id": "affine-product", "left": expression, "right": right}],
                ))
                self.assertEqual("findings", result["status"])
                equation = result["equations"][0]
                self.assertFalse(equation["compatible"])
                refusal = f"affine variable temperature cannot be {operation}"
                hint = "declare a temperature difference as a separate variable in K"
                self.assertIn(refusal, equation["error"])
                self.assertIn(hint, equation["error"])
                self.assertIn("affine-product", result["findings"][0]["message"])
                self.assertIn(refusal, result["findings"][0]["message"])
                self.assertIn(hint, result["findings"][0]["message"])

        preserved = run_dimension_check(self.check_payload(
            variables={"temperature": "degC"},
            equations=[{"id": "absolute", "left": "temperature**1", "right": "temperature"}],
        ))
        self.assertEqual("passed", preserved["status"])
        kelvin = run_dimension_check(self.check_payload(
            variables={"temperature": "K"},
            equations=[{"id": "kelvin", "left": "temperature*2", "right": "temperature"}],
        ))
        self.assertEqual("passed", kelvin["status"])

    def test_affine_function_names_are_distinct_from_variable_uses(self) -> None:
        for expression, right in (
            ("abs(x)*2", "x"),
            ("abs(x)*0", "x"),
            ("abs(x)/2", "x"),
            ("abs(x)**1", "x"),
            ("abs(x)**2", "x**2"),
            ("sqrt(abs(x))", "sqrt(x)"),
        ):
            with self.subTest(expression=expression):
                result = run_dimension_check(self.check_payload(
                    variables={"abs": "degC", "sqrt": "degC", "x": "m"},
                    equations=[{"id": "collision", "left": expression, "right": right}],
                ))
                self.assertEqual("passed", result["status"], msg=f"{expression} should pass")
                self.assertEqual([], result["findings"])
                self.assertTrue(all(item["compatible"] and item["error"] is None for item in result["equations"]))

        for expression in ("abs*2", "abs(abs)*2", "abs(abs)/2", "abs(abs)**2", "sqrt(abs)"):
            with self.subTest(expression=expression):
                self.assertEquationError(
                    expression, "abs", "affine variable abs cannot be",
                    variables={"abs": "degC"},
                )

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


class UncertaintyRuntimeContractTests(unittest.TestCase):
    def payload(self, **overrides: object) -> dict:
        payload = NumericalUnitsUncertaintyTests().uncertainty_input()
        payload.update(overrides)
        return payload

    def assertRefusedWithoutMutation(self, payload: dict, message: str) -> None:
        before = copy.deepcopy(payload)
        with self.assertRaises(ValueError) as caught:
            run_uncertainty_propagation(payload)
        self.assertIn(message, str(caught.exception))
        self.assertEqual(before, payload)

    def test_propagation_input_refusals_name_detected_problem(self) -> None:
        cases = [
            (self.payload(schema_version=2), "unsupported uncertainty-propagation input schema"),
            (self.payload(propagation_id=" "), "propagation_id, claim_id, and expression are required"),
            (self.payload(inputs=[]), "inputs must contain 1 to 64 records"),
            (
                self.payload(inputs=[{"name": f"x{i}", "mean": 1, "standard_uncertainty": 1} for i in range(65)]),
                "inputs must contain 1 to 64 records",
            ),
            (self.payload(inputs=[{"name": "x", "mean": True, "standard_uncertainty": 1}]), "inputs[0].mean must be numeric"),
            (self.payload(inputs=[{"name": "x", "mean": float("inf"), "standard_uncertainty": 1}]), "inputs[0].mean must be finite"),
            (self.payload(inputs=[{"name": "bad-name", "mean": 1, "standard_uncertainty": 1}]), "name must be an identifier"),
            (
                self.payload(inputs=[
                    {"name": "x", "mean": 1, "standard_uncertainty": 1},
                    {"name": "x", "mean": 2, "standard_uncertainty": 1},
                ]),
                "duplicate uncertainty input: x",
            ),
            (self.payload(covariance="bad"), "covariance must be a list of objects"),
            (self.payload(covariance=[{"left": "x", "right": "unknown", "value": 0}]), "references an unknown input"),
            (self.payload(covariance=[{"left": "x", "right": "x", "value": 2}]), "diagonal covariance conflicts"),
            (self.payload(covariance=[{"left": "x", "right": "y", "value": 1}]), "not positive semidefinite"),
            (
                self.payload(
                    inputs=[
                        {"name": "x", "mean": 1, "standard_uncertainty": 0},
                        {"name": "y", "mean": 1, "standard_uncertainty": 1},
                    ],
                    expression="x+y",
                    covariance=[{"left": "x", "right": "y", "value": 0.1}],
                ),
                "singular and inconsistent",
            ),
            (self.payload(method="approximate"), "method must be linear, monte-carlo, or both"),
            (self.payload(confidence_level=0.5), "confidence_level must be between 0.5 and 1"),
            (self.payload(seed=True), "explicit integer seed"),
            (self.payload(samples=99), "samples must be between 100 and 1000000"),
            (self.payload(samples=1_000_001), "samples must be between 100 and 1000000"),
            (self.payload(samples="many"), "invalid literal"),
        ]
        for candidate, message in cases:
            with self.subTest(message=message):
                self.assertRefusedWithoutMutation(candidate, message)

    def test_linear_only_boundary_and_report_fields(self) -> None:
        payload = self.payload(method="linear", covariance=[])
        result = run_uncertainty_propagation(payload)
        self.assertEqual("passed", result["status"])
        self.assertEqual("linear", result["method"])
        self.assertAlmostEqual(6.0, result["nominal_value"])
        self.assertIsNone(result["monte_carlo"])
        self.assertIsNone(result["nonlinearity"]["relative_uncertainty_discrepancy"])
        self.assertEqual(["x", "y"], [item["name"] for item in result["linear"]["sensitivities"]])
        self.assertEqual(payload, self.payload(method="linear", covariance=[]))

    def test_maximum_input_count_is_accepted(self) -> None:
        inputs = [{"name": f"x{i}", "mean": float(i), "standard_uncertainty": 0.1} for i in range(64)]
        result = run_uncertainty_propagation(self.payload(inputs=inputs, expression="x0", method="linear"))
        self.assertEqual(64, len(result["inputs"]))
        self.assertAlmostEqual(0.1, result["linear"]["standard_uncertainty"])

    def test_monte_carlo_minimum_sample_boundary_is_reported(self) -> None:
        result = run_uncertainty_propagation(self.payload(samples=100))
        self.assertEqual(100, result["monte_carlo"]["requested_samples"])
        self.assertGreaterEqual(result["monte_carlo"]["accepted_samples"], 100)
        self.assertEqual(["low-monte-carlo-samples"], [item["code"] for item in result["findings"]])
        self.assertEqual("passed", result["status"])

    def test_nonlinear_disagreement_is_a_major_finding(self) -> None:
        result = run_uncertainty_propagation(
            self.payload(
                expression="exp(x)",
                inputs=[{"name": "x", "mean": 0.0, "standard_uncertainty": 1.0}],
                samples=5000,
                nonlinearity_threshold=0.1,
            )
        )
        self.assertEqual("findings", result["status"])
        self.assertIn("nonlinear-propagation-disagreement", [item["code"] for item in result["findings"]])

    def test_monte_carlo_rejects_when_expression_fails_too_often(self) -> None:
        self.assertRefusedWithoutMutation(
            self.payload(
                expression="log(x)",
                inputs=[{"name": "x", "mean": 0.01, "standard_uncertainty": 1.0}],
                samples=100,
            ),
            "too many Monte Carlo samples failed expression evaluation",
        )

    def test_uncertainty_receipt_validation_and_review(self) -> None:
        receipt = run_uncertainty_propagation(self.payload())
        validate_uncertainty_propagation(receipt)
        self.assertEqual([], review_uncertainty_propagation(receipt))

        corrupted = copy.deepcopy(receipt)
        corrupted["nominal_value"] += 1
        review = review_uncertainty_propagation(corrupted)
        self.assertEqual("invalid-uncertainty-propagation", review[0]["code"])
        self.assertEqual("critical", review[0]["severity"])
        self.assertIn("fingerprint mismatch", review[0]["message"])

        unsafe = copy.deepcopy(receipt)
        unsafe["status"] = "passed"
        unsafe["findings"] = [{"code": "bad", "severity": "major", "message": "blocking"}]
        unsafe.pop("fingerprint")
        unsafe["fingerprint"] = canonical_sha256(unsafe)
        self.assertEqual(["bad", "unsafe-uncertainty-pass"], [item["code"] for item in review_uncertainty_propagation(unsafe)])

        missing_seed = copy.deepcopy(receipt)
        missing_seed["monte_carlo"]["seed"] = None
        missing_seed.pop("fingerprint")
        missing_seed["fingerprint"] = canonical_sha256(missing_seed)
        self.assertEqual(
            ["uncertainty-seed-missing", "unsafe-uncertainty-pass"],
            [item["code"] for item in review_uncertainty_propagation(missing_seed)],
        )

    def test_uncertainty_receipt_refusals_name_detected_problem(self) -> None:
        receipt = run_uncertainty_propagation(self.payload())
        cases = []
        for mutate, message in (
            (lambda value: value.update(schema_version=2), "unsupported uncertainty-propagation receipt schema"),
            (lambda value: value.update(propagation_id=""), "propagation_id is required"),
            (lambda value: value.update(status="unknown"), "invalid uncertainty propagation status"),
            (lambda value: value.update(linear=[]), "linear result and findings are required"),
            (lambda value: value.update(findings=None), "linear result and findings are required"),
        ):
            candidate = copy.deepcopy(receipt)
            mutate(candidate)
            cases.append((candidate, message))
        for candidate, message in cases:
            before = copy.deepcopy(candidate)
            with self.subTest(message=message):
                with self.assertRaises(ValueError) as caught:
                    validate_uncertainty_propagation(candidate)
                self.assertIn(message, str(caught.exception))
                self.assertEqual(before, candidate)


class QuantitativeInputTypeTests(unittest.TestCase):
    def cases(self):
        import json
        from pathlib import Path
        from codex_science.artifact_runtime import describe_runtime, validate_runtime_descriptor
        from codex_science.decision_analysis import run_decision_analysis
        from codex_science.experiment_planner import plan_next_experiment
        from codex_science.formal_proof import run_formal_proof_check
        from codex_science.safe_expression import search_counterexample
        from codex_science.statistics_runtime import run_statistical_analysis

        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / "examples/quantitative-research/input.json").read_text())
        statistics = data["statistical_analysis"]
        statistics.update(bootstrap_replicates=200, permutation_replicates=200)
        uncertainty = data["uncertainty_propagation"]
        uncertainty.update(method="linear")
        formal = json.loads((root / "examples/formal-theorem-proving/input.json").read_text())
        decision = json.loads((root / "examples/statistical-decision-analysis/input.json").read_text())
        artifact = describe_runtime(root / "examples/formal-theorem-proving/Main.lean",
                                    artifact_path="Main.lean", kind="text").to_dict()
        return [
            ("check_dimensions", run_dimension_check, data["dimension_check"],
             ["check_id", "claim_id"], ["conversions.0.value"]),
            ("check_formal_proof", lambda p: run_formal_proof_check(
                p, workspace=root / "examples/formal-theorem-proving", execute=False), formal,
             ["check_id", "receipt_id", "claim_id", "statement", "theorem_file"], ["timeout_seconds"]),
            ("propagate_uncertainty", run_uncertainty_propagation, uncertainty,
             ["propagation_id", "claim_id", "expression"], ["confidence_level", "samples"]),
            ("run_statistical_analysis", run_statistical_analysis, statistics,
             ["analysis_id", "claim_id", "design_id", "data.0.unit_id"],
             ["confidence_level", "bootstrap_replicates", "permutation_replicates"]),
            ("verify_numerical_result", run_numerical_verification, data["numerical_verification"],
             ["verification_id", "claim_id", "method"],
             ["reference_value", "refinements.0.resolution", "refinements.0.estimate"]),
            ("search_counterexample", search_counterexample, data["finite_statement_search"],
             ["claim_id", "statement", "conclusion"], ["max_evaluations"]),
            ("run_decision_analysis", run_decision_analysis, decision,
             ["analysis_id", "claim_id"], []),
            ("plan_next_experiment", plan_next_experiment,
             {"decision": "Choose measurements", "objectives": [{"name": "s", "direction": "maximize"}],
              "candidates": [{"id": "a", "properties": {"s": 1}}], "constraints": {"batch_size": 1}},
             ["decision", "candidates.0.id"], ["objectives.0.required"]),
            ("render_artifact_runtime", validate_runtime_descriptor, artifact, [], ["size_bytes"]),
        ]

    def mutate(self, payload, field, value):
        result = copy.deepcopy(payload)
        target = result
        parts = field.split(".")
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        target[parts[-1]] = value
        return result

    def test_required_text_and_schema_are_not_coerced(self):
        for name, run, payload, fields, _ in self.cases():
            for field in fields:
                for value in (None, [], {}, True, 0, 10**400, float("nan"), float("inf"), "", "  "):
                    with self.subTest(cli=name, field=field, value=repr(value)):
                        with self.assertRaises(ValueError):
                            run(self.mutate(payload, field, value))
            for version in (True, 1.0, "1", None, [], {}):
                with self.subTest(cli=name, schema=version), self.assertRaises(ValueError):
                    run({**payload, "schema_version": version})
        from codex_science.numerical_verification import validate_numerical_verification
        from codex_science.safe_expression import validate_counterexample_receipt
        from codex_science.statistics_runtime import validate_statistical_analysis
        validators = {
            "check_dimensions": validate_dimension_check,
            "propagate_uncertainty": validate_uncertainty_propagation,
            "run_statistical_analysis": validate_statistical_analysis,
            "verify_numerical_result": validate_numerical_verification,
            "search_counterexample": validate_counterexample_receipt,
        }
        for name, run, payload, fields, _ in self.cases():
            if name not in validators:
                continue
            receipt = run(payload)
            for field, value in (("schema_version", True), (fields[0], None)):
                malformed = {**receipt, field: value}
                malformed.pop("fingerprint")
                malformed["fingerprint"] = canonical_sha256(malformed)
                with self.subTest(receipt=name, field=field), self.assertRaises(ValueError):
                    validators[name](malformed)
        planner = next(item for item in self.cases() if item[0] == "plan_next_experiment")
        payload = copy.deepcopy(planner[2])
        payload.pop("decision")
        with self.assertRaises(ValueError):
            planner[1](payload)

    def test_numeric_fields_refuse_invalid_types_and_overflow(self):
        for name, run, payload, _, fields in self.cases():
            for field in fields:
                invalid = [None, [], {}, "", "1", float("inf"), float("nan")]
                if field == "reference_value":
                    invalid.remove(None)
                candidate = {**payload, "method": "both", "samples": 100} if field == "samples" else payload
                if field == "objectives.0.required":
                    invalid.extend([0, 1, 1.5, 10**400])
                else:
                    invalid.append(True)
                if field not in {"objectives.0.required", "size_bytes"}:
                    invalid.append(10**400)
                if field in {"timeout_seconds", "samples", "bootstrap_replicates", "permutation_replicates",
                             "max_evaluations", "size_bytes"}:
                    invalid.extend([1.5, -1] + ([] if field == "size_bytes" else [0]))
                for value in invalid:
                    with self.subTest(cli=name, field=field, value=repr(value)), self.assertRaises(ValueError):
                        run(self.mutate(candidate, field, value))
        by_name = {case[0]: case for case in self.cases()}
        for name, field, bounds in (
            ("check_formal_proof", "timeout_seconds", (1, 600)),
            ("search_counterexample", "max_evaluations", (1, 1_000_000)),
            ("run_statistical_analysis", "bootstrap_replicates", (200, 100_000)),
            ("run_statistical_analysis", "permutation_replicates", (200, 100_000)),
            ("propagate_uncertainty", "samples", (100, 1_000_000)),
        ):
            _, run, payload, _, _ = by_name[name]
            if field == "samples":
                payload = {**payload, "method": "monte-carlo", "seed": 1}
            for value in bounds:
                with self.subTest(cli=name, field=field, boundary=value):
                    run(self.mutate(payload, field, value))
            with self.subTest(cli=name, field=field, above=bounds[1] + 1), self.assertRaises(ValueError):
                run(self.mutate(payload, field, bounds[1] + 1))
        _, run, payload, _, _ = by_name["check_dimensions"]
        self.assertEqual(0, run(self.mutate(payload, "conversions.0.value", 0))["conversions"][0]["converted"])
        _, run, payload, _, _ = by_name["render_artifact_runtime"]
        payload = {**payload, "size_bytes": 0}
        payload.pop("fingerprint")
        payload["fingerprint"] = canonical_sha256(payload)
        run(payload)
        _, run, payload, _, _ = by_name["verify_numerical_result"]
        run({**payload, "reference_value": None})
        _, run, payload, _, _ = by_name["plan_next_experiment"]
        for required in (False, True):
            run(self.mutate(payload, "objectives.0.required", required))
        # An integer expression can be within the expression evaluator's limit
        # yet outside binary64, so conversion must still report a refusal.
        case = next(item for item in self.cases() if item[0] == "propagate_uncertainty")
        with self.assertRaises(ValueError):
            case[1]({**case[2], "expression": str(10**400)})

    def test_cli_refusals_preserve_existing_and_absent_outputs(self):
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile

        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tempdir:
            folder = Path(tempdir)
            source = folder / "input.json"
            for name, _, payload, text_fields, numeric_fields in self.cases():
                mutations = [(field, 10**400 if field == "reference_value" else None)
                             for field in (text_fields[:1] + numeric_fields[:1])]
                for field, value in mutations:
                    source.write_text(json.dumps(self.mutate(payload, field, value)))
                    for exists in (False, True):
                        output = folder / "output.json"
                        if exists:
                            output.write_bytes(b"existing output\n")
                        args = [sys.executable, str(root / "scripts" / (name + ".py"))]
                        if name == "render_artifact_runtime":
                            args.append("render")
                        args += [str(source), "--output", str(output)]
                        if name == "check_formal_proof":
                            args += ["--workspace", str(root / "examples/formal-theorem-proving"), "--preview"]
                        with self.subTest(cli=name, field=field, exists=exists):
                            completed = subprocess.run(args, capture_output=True, text=True,
                                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                            self.assertEqual(1, completed.returncode)
                            self.assertEqual("", completed.stdout)
                            self.assertTrue(completed.stderr.startswith("error: "), completed.stderr)
                            self.assertNotIn("Traceback", completed.stderr)
                            if exists:
                                self.assertEqual(b"existing output\n", output.read_bytes())
                            else:
                                self.assertFalse(output.exists())
                        output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
