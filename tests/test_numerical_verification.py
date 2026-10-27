import copy
import unittest

from codex_science.numerical_verification import (
    MAX_REFINEMENTS,
    review_numerical_verification,
    run_numerical_verification,
    validate_numerical_verification,
)


class NumericalVerificationContractTests(unittest.TestCase):
    def payload(self, **overrides: object) -> dict:
        value: dict = {
            "schema_version": 1,
            "verification_id": "verify-1",
            "claim_id": "claim-1",
            "method": "manufactured fixture",
            "reference_value": 1.0,
            "thresholds": {"minimum_order": 1.8, "max_residual": 0.1, "max_invariant_deviation": 0.1},
            "solver": {"precision": "binary64", "absolute_tolerance": 1e-12},
            "refinements": [
                {"resolution": 0.4, "estimate": 1.16, "residual": 0.064, "invariants": {"mass": 0.016}},
                {"resolution": 0.2, "estimate": 1.04, "residual": 0.008, "invariants": {"mass": 0.004}},
                {"resolution": 0.1, "estimate": 1.01, "residual": 0.001, "invariants": {"mass": 0.001}},
            ],
            "cross_method": [
                {"method": "method-a", "estimate": 1.0, "uncertainty": 0.01},
                {"method": "method-b", "estimate": 1.01, "uncertainty": 0.01},
            ],
        }
        value.update(overrides)
        return value

    def assertRefusedWithoutMutation(self, payload: dict, message: str) -> None:
        before = copy.deepcopy(payload)
        with self.assertRaises(ValueError) as caught:
            run_numerical_verification(payload)
        self.assertIn(message, str(caught.exception))
        self.assertEqual(before, payload)

    def test_pass_receipt_outputs_are_complete_and_fingerprinted(self) -> None:
        result = run_numerical_verification(self.payload())
        self.assertEqual(("passed", "verify-1", "claim-1"), (result["status"], result["verification_id"], result["claim_id"]))
        self.assertAlmostEqual(2.0, result["minimum_observed_order"])
        self.assertAlmostEqual(0.064, result["maximum_residual"])
        self.assertAlmostEqual(0.016, result["maximum_invariant_deviation"])
        self.assertAlmostEqual(0.01, result["cross_method"][1]["difference_from_first"])
        self.assertAlmostEqual(2 ** -0.5, result["cross_method"][1]["combined_uncertainty_z"])
        self.assertEqual(64, len(result["input_sha256"]))
        validate_numerical_verification(result)
        self.assertEqual([], review_numerical_verification(result))

    def test_input_schema_identity_and_collection_refusals_leave_input_unchanged(self) -> None:
        for payload, message in (
            (self.payload(schema_version=2), "unsupported numerical-verification input schema"),
            (self.payload(verification_id="  "), "verification_id, claim_id, and method are required"),
            (self.payload(refinements={}), "refinements must contain 2 to"),
            (self.payload(refinements=[]), "refinements must contain 2 to"),
            (self.payload(refinements=[{"resolution": 1, "estimate": 1}]), "refinements must contain 2 to"),
            (self.payload(thresholds=[]), "thresholds must be an object"),
            (self.payload(solver=[]), "solver must be an object"),
            (self.payload(cross_method=[None]), "cross_method must be a list of objects"),
        ):
            with self.subTest(message=message):
                self.assertRefusedWithoutMutation(payload, message)

    def test_numeric_and_refinement_validation_refusals_name_detected_field(self) -> None:
        cases = (
            (self.payload(reference_value=True), "reference_value must be numeric"),
            (self.payload(reference_value=float("inf")), "reference_value must be finite"),
            (self.payload(thresholds={"max_cross_method_z": 0}), "max_cross_method_z must be positive"),
            (self.payload(refinements=[None, {"resolution": 0.1, "estimate": 1}]), "refinements[0] must be an object"),
            (self.payload(refinements=[{"estimate": 1}, {"resolution": 0.1, "estimate": 1}]), "refinements[0].resolution must be numeric"),
            (self.payload(refinements=[{"resolution": 1, "estimate": float("nan")}, {"resolution": 0.1, "estimate": 1}]), "refinements[0].estimate must be finite"),
            (self.payload(refinements=[{"resolution": 0, "estimate": 1}, {"resolution": 0.1, "estimate": 1}]), "resolution values must be positive"),
            (self.payload(refinements=[{"resolution": 1, "estimate": 1, "error": -1}, {"resolution": 0.1, "estimate": 1}]), "errors must be non-negative"),
            (self.payload(refinements=[{"resolution": 1, "estimate": 1, "invariants": []}, {"resolution": 0.1, "estimate": 1}]), "refinements[0].invariants must be an object"),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                self.assertRefusedWithoutMutation(payload, message)

    def test_cross_method_validation_refusals_name_detected_item(self) -> None:
        for methods, message in (
            ([{}], "cross_method[0].method is required"),
            ([{"method": "other", "estimate": True, "uncertainty": 0.1}], "cross_method[0].estimate must be numeric"),
            ([{"method": "other", "estimate": 1.0, "uncertainty": float("inf")}], "cross_method[0].uncertainty must be finite"),
        ):
            with self.subTest(message=message):
                self.assertRefusedWithoutMutation(self.payload(cross_method=methods), message)

    def test_two_level_and_refinement_limit_boundaries_are_defined(self) -> None:
        two_levels = self.payload(refinements=self.payload()["refinements"][:2], thresholds={"minimum_order": 1.8})
        result = run_numerical_verification(two_levels)
        self.assertEqual("findings", result["status"])
        self.assertEqual(2, len(result["refinements"]))
        self.assertIn("insufficient-refinement-levels", {item["code"] for item in result["findings"]})

        at_limit = [
            {"resolution": float(MAX_REFINEMENTS - index), "estimate": 1.0}
            for index in range(MAX_REFINEMENTS)
        ]
        self.assertEqual("passed", run_numerical_verification(self.payload(refinements=at_limit, thresholds={}))["status"])
        above_limit = self.payload(refinements=at_limit + [{"resolution": 0.5, "estimate": 1.0}])
        self.assertRefusedWithoutMutation(above_limit, f"2 to {MAX_REFINEMENTS} levels")

    def test_sequence_threshold_and_receipt_review_findings(self) -> None:
        repeated = self.payload(refinements=[
            {"resolution": 0.2, "estimate": 1.1},
            {"resolution": 0.2, "estimate": 1.05},
            {"resolution": 0.1, "estimate": 1.01},
        ], thresholds={"minimum_order": 1.0, "max_residual": 0.1, "max_invariant_deviation": 0.1})
        receipt = run_numerical_verification(repeated)
        codes = {finding["code"] for finding in receipt["findings"]}
        self.assertIn("non-refining-resolution-sequence", codes)
        self.assertIn("residual-series-incomplete", codes)
        self.assertIn("invariant-audit-missing", codes)

        unsafe = copy.deepcopy(receipt)
        unsafe["status"] = "passed"
        unsafe["fingerprint"] = "0" * 64
        findings = review_numerical_verification(unsafe)
        self.assertIn("invalid-numerical-verification", {finding["code"] for finding in findings})

    def test_receipt_validator_and_reviewer_detect_fingerprint_and_claim_conflicts(self) -> None:
        receipt = run_numerical_verification(self.payload())
        changed = copy.deepcopy(receipt)
        changed["method"] = "tampered"
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            validate_numerical_verification(changed)
        review = review_numerical_verification(changed)
        self.assertIn("invalid-numerical-verification", {item["code"] for item in review})

        blocking = copy.deepcopy(receipt)
        blocking["findings"].append({"code": "bad", "severity": "critical", "message": "blocking"})
        from codex_science.safe_expression import canonical_sha256
        material = dict(blocking)
        material.pop("fingerprint")
        blocking["fingerprint"] = canonical_sha256(material)
        review = review_numerical_verification(blocking)
        self.assertIn("unsafe-numerical-pass", {item["code"] for item in review})

        underidentified = copy.deepcopy(receipt)
        underidentified["refinements"] = underidentified["refinements"][:2]
        material = dict(underidentified)
        material.pop("fingerprint")
        from codex_science.safe_expression import canonical_sha256
        underidentified["fingerprint"] = canonical_sha256(material)
        self.assertIn("order-claim-underidentified", {
            item["code"] for item in review_numerical_verification(underidentified)
        })

    def test_validator_rejects_malformed_receipt_fields(self) -> None:
        receipt = run_numerical_verification(self.payload())
        cases = (
            ({**receipt, "schema_version": 2}, "unsupported numerical-verification receipt schema"),
            ({**receipt, "verification_id": ""}, "verification_id is required"),
            ({**receipt, "status": "unknown"}, "invalid numerical verification status"),
            ({**receipt, "refinements": []}, "at least two refinements"),
            ({**receipt, "findings": [None]}, "findings must be a list of objects"),
        )
        for changed, message in cases:
            with self.subTest(message=message):
                material = dict(changed)
                material.pop("fingerprint", None)
                from codex_science.safe_expression import canonical_sha256
                changed["fingerprint"] = canonical_sha256(material)
                with self.assertRaises(ValueError) as caught:
                    validate_numerical_verification(changed)
                self.assertIn(message, str(caught.exception))

    def test_estimate_differences_without_reference_report_unavailable_order(self) -> None:
        payload = self.payload(
            reference_value=None,
            refinements=[
                {"resolution": 0.4, "estimate": 1.0},
                {"resolution": 0.2, "estimate": 1.1},
                {"resolution": 0.05, "estimate": 1.15},
            ],
            thresholds={"minimum_order": 0.5},
            solver={},
            cross_method=[],
        )
        result = run_numerical_verification(payload)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("observed-order-unavailable", codes)
        self.assertIn("floating-precision-unstated", codes)
        self.assertIn("solver-tolerance-unstated", codes)
        self.assertIsNone(result["error_monotone"])
        self.assertEqual("findings", result["status"])


if __name__ == "__main__":
    unittest.main()
