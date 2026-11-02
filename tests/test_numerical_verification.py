import copy
import hashlib
import math
import struct
import tempfile
import unittest
from pathlib import Path

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

    def forge(self, receipt: dict, mutate) -> dict:
        from codex_science.safe_expression import canonical_sha256
        forged = copy.deepcopy(receipt)
        mutate(forged)
        forged.pop("fingerprint")
        forged["fingerprint"] = canonical_sha256(forged)
        return forged

    def test_runtime_receipts_validate_including_infinite_agreement(self) -> None:
        for payload in (
            self.payload(),
            self.payload(refinements=self.payload()["refinements"][:2], thresholds={"minimum_order": 1.8}),
            self.payload(reference_value=None, solver={}, cross_method=[]),
            self.payload(refinements=[{"resolution": 1, "estimate": 2, "error": 0.5}, {"resolution": 0.5, "estimate": 1.5}]),
            self.payload(cross_method=[{"method": "a", "estimate": 0, "uncertainty": 0},
                                       {"method": "b", "estimate": 1, "uncertainty": 0},
                                       {"method": "c", "estimate": 0, "uncertainty": 0}]),
        ):
            receipt = run_numerical_verification(payload)
            with self.subTest(status=receipt["status"], orders=receipt["observed_orders"]):
                validate_numerical_verification(receipt)
        self.assertEqual(math.inf, receipt["cross_method"][1]["combined_uncertainty_z"])

    def test_sidecar_loader_keeps_infinite_agreement_and_refuses_nan_and_overflow(self) -> None:
        from codex_science.advanced_sidecars import validate_advanced_sidecars
        from codex_science.cli_io import write_json_atomic

        receipt = run_numerical_verification(self.payload(cross_method=[
            {"method": "a", "estimate": 0, "uncertainty": 0},
            {"method": "b", "estimate": 1, "uncertainty": 0},
        ]))
        self.assertEqual(math.inf, receipt["cross_method"][1]["combined_uncertainty_z"])
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)

            def validate(name: str, content: bytes | None = None) -> dict:
                path = root / f"{name}.json"
                if content is None:
                    write_json_atomic(path, receipt)
                else:
                    path.write_bytes(content)
                manifest = {"artifacts": [{"kind": "numerical-verification", "path": path.name,
                                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
                return validate_advanced_sidecars(manifest, root, {path.name: path})

            self.assertEqual([receipt], validate("infinite-agreement")["numerical_verifications"])
            written = (root / "infinite-agreement.json").read_text(encoding="utf-8")
            self.assertIn('"combined_uncertainty_z": Infinity', written)
            for literal in ("-Infinity", "1e308"):
                with self.subTest(loaded_then_refused=literal):
                    forged = written.replace('"combined_uncertainty_z": Infinity', f'"combined_uncertainty_z": {literal}')
                    with self.assertRaisesRegex(ValueError, r"^forged\.json \(numerical-verification\): .*combined_uncertainty_z"):
                        validate("forged", forged.encode())
            residual = written.replace('"maximum_residual": 0.064', '"maximum_residual": Infinity')
            self.assertNotEqual(written, residual)
            with self.assertRaisesRegex(ValueError, "maximum_residual must be finite"):
                validate("residual", residual.encode())
            documents = {
                "nan": written.replace('"combined_uncertainty_z": Infinity', '"combined_uncertainty_z": NaN'),
                "overflow": written.replace('"maximum_residual": 0.064', '"maximum_residual": 1e999'),
                "negative-overflow": written.replace('"maximum_residual": 0.064', '"maximum_residual": -1e999'),
                "nested": "[" * 100_000 + "]" * 100_000,
                "syntax": "{",
            }
            for name, content in documents.items():
                self.assertNotEqual(written, content)
                with self.subTest(document=name):
                    with self.assertRaisesRegex(ValueError, f"^invalid JSON in numerical-verification: {name}.json: "):
                        validate(name, content.encode())
            with self.assertRaisesRegex(ValueError, "^invalid JSON in numerical-verification: encoding.json: "):
                validate("encoding", b"\xff")

    def test_validator_refuses_inconsistent_or_nonfinite_numbers(self) -> None:
        receipt = run_numerical_verification(self.payload())
        validate_numerical_verification(receipt)

        def put(path, value):
            def mutate(item):
                for key in path[:-1]:
                    item = item[key]
                item[path[-1]] = value
            return mutate

        cases = [
            (put(("findings",), [{}]), "finding.code is required"),
            (put(("findings",), [{"code": "c", "severity": "major", "message": ""}]), "finding.message is required"),
            (put(("findings",), [{"code": "c", "severity": "fatal", "message": "m"}]), "invalid numerical finding severity"),
            (put(("status",), "findings"), "findings status requires"),
            (put(("reference_value",), math.nan), "reference_value must be finite"),
            (put(("refinements", 0, "error"), math.inf), r"refinements\[0\].error must be finite"),
            (put(("refinements", 0, "error"), math.nan), r"refinements\[0\].error must be finite"),
            (put(("refinements", 0, "error"), -0.1), r"refinements\[0\].error must be non-negative"),
            (put(("refinements", 0, "resolution"), 0), "resolution must be positive"),
            (put(("refinements", 0, "estimate"), None), "estimate must be numeric"),
            (put(("refinements", 0, "residual"), math.inf), "residual must be finite"),
            (put(("refinements", 0, "invariants"), []), "invariants must be an object"),
            (put(("refinements", 0, "invariants", "mass"), None), "invariants.mass must be numeric"),
            (put(("refinements", 1), 5), r"refinements\[1\] must be an object"),
            (put(("maximum_residual",), math.inf), "maximum_residual must be finite"),
            (put(("maximum_residual",), 0.0064), "maximum_residual does not match"),
            (put(("maximum_residual",), None), "maximum_residual does not match"),
            (put(("maximum_invariant_deviation",), 1.0), "maximum_invariant_deviation does not match"),
            (put(("observed_orders",), None), "observed_orders must be a list"),
            (put(("observed_orders",), [math.nan]), "must be finite"),
            (put(("minimum_observed_order",), 9.0), "minimum_observed_order does not match"),
            (put(("minimum_observed_order",), True), "minimum_observed_order does not match"),
            (put(("error_monotone",), False), "error_monotone does not match"),
            (put(("error_monotone",), "yes"), "error_monotone requires a boolean"),
            (put(("refinements", 1, "error"), None), "error at every refinement"),
            (put(("cross_method",), None), "cross_method must be a list"),
            (put(("cross_method", 1, "combined_uncertainty_z"), 0.1), "combined_uncertainty_z does not match"),
            (put(("cross_method", 1, "difference_from_first"), 5.0), "difference_from_first does not match"),
            (put(("cross_method", 1, "uncertainty"), -0.01), "uncertainty must be non-negative"),
        ]
        for mutate, message in cases:
            forged = self.forge(receipt, mutate)
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_numerical_verification(forged)
                self.assertEqual("invalid-numerical-verification", review_numerical_verification(forged)[0]["code"])
        for findings in ([5], [{}], [{"code": "c"}]):
            with self.subTest(findings=findings):
                review = review_numerical_verification(self.forge(receipt, put(("findings",), findings)))
                self.assertEqual(["invalid-numerical-verification"], [item["code"] for item in review])
        suggestion = self.forge(receipt, put(("findings",), [{"code": "c", "severity": "suggestion", "message": "m"}]))
        validate_numerical_verification(suggestion)

    def test_estimate_differences_without_reference_report_order(self) -> None:
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
        self.assertAlmostEqual(math.log2(1 + math.sqrt(3)), result["observed_orders"][0])
        self.assertIn("floating-precision-unstated", codes)
        self.assertIn("solver-tolerance-unstated", codes)
        self.assertIsNone(result["error_monotone"])
        self.assertEqual("passed", result["status"])

    def test_unequal_refinement_ratios_solve_power_model(self) -> None:
        for gap, expected in ((0, "passed"), (0.5e-12, "passed"), (2e-12, "passed")):
            receipt = run_numerical_verification(self.payload(
                reference_value=None, thresholds={"minimum_order": 0},
                refinements=[{"resolution": h, "estimate": h} for h in (4 * (1 + gap), 2, 1)],
            ))
            self.assertEqual(expected, receipt["status"])
            if gap <= 0.5e-12:
                expected_order = math.log((2 + 4 * gap) / 1) / math.log(2 * (1 + gap))
                self.assertEqual(expected_order, receipt["observed_orders"][0])
        equal_order = self.payload(reference_value=None, thresholds={"minimum_order": 1}, refinements=[
            {"resolution": h, "estimate": h} for h in (1, 0.5, 0.25)
        ])
        self.assertEqual("passed", run_numerical_verification(equal_order)["status"])
        equal_order["thresholds"] = {}
        equal_order["refinements"][-1]["estimate"] = 0.5
        self.assertEqual("passed", run_numerical_verification(equal_order)["status"])

    def test_critic_unequal_grid_reports_first_order(self) -> None:
        result = run_numerical_verification(self.payload(
            reference_value=None, thresholds={"minimum_order": 2},
            refinements=[{"resolution": h, "estimate": h} for h in (1.0302, 1.01, 1)],
        ))
        self.assertAlmostEqual(1, result["observed_orders"][0])
        self.assertEqual("findings", result["status"])
        self.assertIn("convergence-order-below-threshold", {item["code"] for item in result["findings"]})

    def test_binary32_grid_reports_second_order(self) -> None:
        grid = [struct.unpack("f", struct.pack("f", h))[0] for h in (0.09, 0.03, 0.01)]
        result = run_numerical_verification(self.payload(
            reference_value=None, thresholds={"minimum_order": 1.8},
            refinements=[{"resolution": h, "estimate": 1 + h * h} for h in grid],
        ))
        self.assertEqual("passed", result["status"])
        self.assertAlmostEqual(2, result["observed_orders"][0], places=8)

    def test_unequal_ratio_root_bracket_boundaries(self) -> None:
        # h1/h2=4 and h2/h3=2 make the difference ratio t*(t+1), t=2**p.
        for order in (-65, -64, -1, 0, 1, 64, 65):
            with self.subTest(order=order):
                ratio = 2.0 ** order * (2.0 ** order + 1)
                result = run_numerical_verification(self.payload(
                    reference_value=None, thresholds={"minimum_order": -100},
                    refinements=[{"resolution": h, "estimate": q}
                                 for h, q in ((4, ratio), (1, 0), (0.5, -1))],
                ))
                if abs(order) > 64:
                    self.assertEqual([], result["observed_orders"])
                    self.assertIn("observed-order-unavailable", {f["code"] for f in result["findings"]})
                else:
                    self.assertAlmostEqual(order, result["observed_orders"][0], places=10)
        for estimates in ((0, 0, 0), (1, 0, 1)):
            result = run_numerical_verification(self.payload(
                reference_value=None, thresholds={"minimum_order": 0},
                refinements=[{"resolution": h, "estimate": q} for h, q in zip((4, 1, 0.5), estimates)],
            ))
            self.assertEqual([], result["observed_orders"])

    def test_stalled_tail_cannot_pass_minimum_order(self) -> None:
        for reference in (None, 1.01):
            with self.subTest(reference=reference):
                result = run_numerical_verification(self.payload(
                    reference_value=reference, thresholds={"minimum_order": 1.8},
                    refinements=[{"resolution": h, "estimate": q} for h, q in (
                        (1, 1.16), (0.5, 1.04), (0.25, 1.01), (0.125, 1.01),
                    )],
                ))
                self.assertEqual("findings", result["status"])
                self.assertIn("observed-order-series-incomplete", {item["code"] for item in result["findings"]})

    def test_invariant_threshold_requires_each_name_at_each_level(self) -> None:
        for invariants in (({"mass": 0}, {}), ({}, {"mass": 0}), ({"mass": 0}, {"energy": 0})):
            with self.subTest(invariants=invariants):
                result = run_numerical_verification(self.payload(
                    thresholds={"max_invariant_deviation": 0.1},
                    refinements=[{"resolution": h, "estimate": 1, "invariants": inv}
                                 for h, inv in zip((1, 0.5), invariants)],
                ))
                self.assertEqual("findings", result["status"])
                self.assertIn("invariant-series-incomplete", {item["code"] for item in result["findings"]})
        for limit in (0, 0.1):
            result = run_numerical_verification(self.payload(
                thresholds={"max_invariant_deviation": limit},
                refinements=[{"resolution": h, "estimate": 1, "invariants": {"mass": limit}}
                             for h in (1, 0.5)],
            ))
            self.assertEqual("passed", result["status"])

    def test_cross_method_threshold_refuses_nonfinite_and_nonnumeric_values(self) -> None:
        for value in ("nan", "3", "", None, True, [], float("nan"), float("inf"), -1, 0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_numerical_verification(self.payload(thresholds={"max_cross_method_z": value}))

        for threshold, status in ((1, "passed"), (0.99, "findings")):
            result = run_numerical_verification(self.payload(
                thresholds={"max_cross_method_z": threshold}, cross_method=[
                    {"method": "a", "estimate": 0, "uncertainty": 1},
                    {"method": "b", "estimate": 1, "uncertainty": 0},
                ],
            ))
            self.assertEqual(status, result["status"])


    def honest_payloads(self) -> list[dict]:
        import json
        root = Path(__file__).resolve().parents[1]
        example = json.loads((root / "examples/numerical-analysis-error-control/input.json").read_text(encoding="utf-8"))
        quantitative = json.loads((root / "examples/quantitative-research/input.json").read_text(encoding="utf-8"))
        seeded = []
        for path, value in ((("refinements", 1, "resolution"), 0.4), (("refinements", 1, "estimate"), 1.2),
                            (("refinements", 1, "residual"), 0.02), (("cross_method", 1, "estimate"), 1.02)):
            changed = copy.deepcopy(example)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            seeded.append(changed)
        refinements = self.payload()["refinements"]
        return [
            example, quantitative["numerical_verification"], *seeded,
            self.payload(),
            self.payload(refinements=refinements[:2], thresholds={}),
            self.payload(refinements=refinements[:2], thresholds={"minimum_order": 1.8}),
            self.payload(reference_value=None, solver={}, cross_method=[]),
            self.payload(refinements=[{"resolution": 1, "estimate": 2, "error": 0.5}, {"resolution": 0.5, "estimate": 1.5}]),
            self.payload(refinements=[{"resolution": h, "estimate": 1.0} for h in (0.4, 0.2, 0.1)]),
            self.payload(cross_method=[{"method": "a", "estimate": 0, "uncertainty": 0},
                                       {"method": "b", "estimate": 1, "uncertainty": 0}]),
            self.payload(reference_value=None, thresholds={"minimum_order": 2},
                         refinements=[{"resolution": h, "estimate": h} for h in (1.0302, 1.01, 1)]),
            self.payload(thresholds={"minimum_order": 1.8}, refinements=[
                {"resolution": h, "estimate": q} for h, q in ((1, 1.16), (0.5, 1.04), (0.25, 1.01), (0.125, 1.01))]),
        ]

    def test_runtime_receipts_review_without_inconsistency(self) -> None:
        import json
        statuses = set()
        for payload in self.honest_payloads():
            receipt = json.loads(json.dumps(run_numerical_verification(payload)))
            statuses.add(receipt["status"])
            codes = [item["code"] for item in review_numerical_verification(receipt)]
            with self.subTest(status=receipt["status"], codes=codes):
                if receipt["status"] == "passed":
                    self.assertEqual(sorted(item["code"] for item in receipt["findings"]), codes)
                else:
                    self.assertTrue({item["code"] for item in receipt["findings"]} <= set(codes))
                    self.assertFalse({"numerical-receipt-inconsistent", "unsafe-numerical-pass",
                                      "invalid-numerical-verification"} & set(codes))
        self.assertEqual({"passed", "findings"}, statuses)

    def test_review_rederives_outcome_from_recorded_inputs(self) -> None:
        receipt = run_numerical_verification(self.payload())

        def set_threshold(item):
            item["thresholds"]["minimum_order"] = 5.0

        def repeat_resolution(item):
            item["refinements"][1]["resolution"] = item["refinements"][0]["resolution"]

        def drop_finding(item):
            item["findings"] = []
            item["status"] = "passed"

        def unknown_threshold(item):
            item["thresholds"]["bogus_limit"] = 1.0

        def disagreeing_third_method(item):
            item["cross_method"].append({"method": "c", "estimate": 9.0, "uncertainty": 0.01,
                                         "difference_from_first": 8.0, "combined_uncertainty_z": 8.0 / math.hypot(0.01, 0.01)})

        failing = run_numerical_verification(self.payload(refinements=[
            {**record, "resolution": 0.4} for record in self.payload()["refinements"]]))
        cases = ((receipt, set_threshold), (receipt, repeat_resolution), (failing, drop_finding),
                 (receipt, unknown_threshold), (receipt, disagreeing_third_method))
        for source, mutate in cases:
            forged = self.forge(source, mutate)
            with self.subTest(mutation=mutate.__name__):
                validate_numerical_verification(forged)
                review = review_numerical_verification(forged)
                inconsistent = [item for item in review if item["code"] == "numerical-receipt-inconsistent"]
                self.assertEqual(1, len(inconsistent), review)
                self.assertEqual("critical", inconsistent[0]["severity"])

    def test_order_claim_underidentified_requires_declared_minimum_order(self) -> None:
        two_levels = self.payload()["refinements"][:2]
        for thresholds, flagged in (({}, False), ({"minimum_order": None}, False), ({"minimum_order": 1.8}, True)):
            receipt = run_numerical_verification(self.payload(refinements=two_levels, thresholds=thresholds))
            self.assertIsNotNone(receipt["minimum_observed_order"])
            codes = {item["code"] for item in review_numerical_verification(receipt)}
            with self.subTest(thresholds=thresholds):
                self.assertEqual(flagged, "order-claim-underidentified" in codes)
                self.assertEqual(flagged, receipt["status"] == "findings")

    def test_overflowing_derived_quantities_are_refused(self) -> None:
        def levels(*pairs, key="estimate"):
            return [{"resolution": h, key: value} for h, value in pairs]

        cases = (
            (self.payload(reference_value=None, refinements=levels((0.4, 1e308), (0.2, -1e308), (0.1, 0.0))),
             "successive difference in refinements[0] to refinements[2] is not finite"),
            (self.payload(reference_value=-1e308, refinements=levels((0.4, 1e308), (0.2, 0.0), (0.1, 0.0))),
             r"refinements[0].error derived from reference_value is not finite"),
            (self.payload(reference_value=None, refinements=[
                {"resolution": h, "estimate": 1.0, "error": e} for h, e in ((0.4, 1e300), (0.2, 1e-300), (0.1, 1e-301))]),
             "error ratio between refinements[0] and refinements[1] is not a finite positive number"),
            (self.payload(reference_value=None, refinements=[
                {"resolution": h, "estimate": 1.0, "error": e} for h, e in ((0.4, 1e-300), (0.2, 1e300), (0.1, 1.0))]),
             "error ratio between refinements[0] and refinements[1] is not a finite positive number"),
            (self.payload(reference_value=None, refinements=[
                {"resolution": h, "estimate": 1.0, "error": e} for h, e in ((1e300, 1.0), (1e-300, 0.5))]),
             "resolution ratio between refinements[0] and refinements[1] is not finite"),
            (self.payload(reference_value=None, refinements=levels((0.4, 1e300), (0.2, 0.0), (0.1, -1e-300))),
             "successive difference ratio in refinements[0] to refinements[2] is not a finite positive number"),
            (self.payload(cross_method=[{"method": "a", "estimate": 1e308, "uncertainty": 1},
                                        {"method": "b", "estimate": -1e308, "uncertainty": 1}]),
             "cross_method[0] and cross_method[1] estimate difference is not finite"),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                self.assertRefusedWithoutMutation(payload, message)
        largest = run_numerical_verification(self.payload(
            reference_value=None, thresholds={"minimum_order": 0.9},
            refinements=levels((0.4, 1e308), (0.2, 5e307), (0.1, 2.5e307))))
        self.assertEqual(("passed", [1.0]), (largest["status"], largest["observed_orders"]))

    def test_cli_refuses_overflowing_order_without_writing(self) -> None:
        import json
        import os
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        payload = self.payload(reference_value=None, refinements=[
            {"resolution": h, "estimate": q} for h, q in ((0.4, 1e308), (0.2, -1e308), (0.1, 0.0))])
        with tempfile.TemporaryDirectory() as tempdir:
            source, output = Path(tempdir) / "input.json", Path(tempdir) / "output.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(root / "scripts" / "verify_numerical_result.py"), str(source), "--output", str(output)],
                capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
            self.assertEqual(1, completed.returncode)
            self.assertEqual("", completed.stdout)
            self.assertTrue(completed.stderr.startswith("error: "), completed.stderr)
            self.assertIn("not finite", completed.stderr)
            self.assertFalse(output.exists())

    def test_negative_absolute_tolerance_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute_tolerance must not be negative"):
            run_numerical_verification(self.payload(
                reference_value=1.0,
                refinements=[{"resolution": h, "estimate": 1.0 + h * h} for h in (0.4, 0.2, 0.1)],
                thresholds={"minimum_order": 1.5},
                solver={"precision": "binary64", "absolute_tolerance": -1e-12}, cross_method=[]))

    def test_order_from_errors_at_or_below_absolute_tolerance_is_noise(self) -> None:
        near_one = [{"resolution": h, "estimate": 1 + e} for h, e in ((0.4, 3.6e-15), (0.2, 9e-16), (0.1, 2.3e-16))]
        exact = [{"resolution": h, "estimate": 1.0, "error": e} for h, e in ((0.4, 4e-12), (0.2, 2e-12), (0.1, 1e-12))]
        above = [{"resolution": h, "estimate": 1.0, "error": e} for h, e in ((0.4, 4e-12), (0.2, 2e-12), (0.1, 1.0001e-12))]
        zero = [{"resolution": h, "estimate": 1.0} for h in (0.4, 0.2, 0.1)]
        differences = [{"resolution": h, "estimate": q} for h, q in ((0.4, 5e-12), (0.2, 1e-12), (0.1, 0.0))]
        cases = (
            (near_one, 1.0, {"absolute_tolerance": 1e-12}, True),
            (exact, None, {"absolute_tolerance": 1e-12}, True),
            (above, None, {"absolute_tolerance": 1e-12}, False),
            (near_one, 1.0, {"absolute_tolerance": 0}, False),
            (near_one, 1.0, {"relative_tolerance": 1e-12}, False),
            (near_one, 1.0, {"absolute_tolerance": "1e-12"}, False),
            (near_one, 1.0, {"absolute_tolerance": True}, False),
            (zero, 1.0, {"absolute_tolerance": 1e-12}, False),
            (differences, None, {"absolute_tolerance": 1e-12}, True),
        )
        for refinements, reference, solver, noisy in cases:
            receipt = run_numerical_verification(self.payload(
                reference_value=reference, refinements=refinements,
                thresholds={"minimum_order": 0.5} if refinements is not zero else {},
                solver={"precision": "binary64", **solver}, cross_method=[]))
            codes = {item["code"] for item in receipt["findings"]}
            with self.subTest(solver=solver, first=refinements[0]):
                self.assertEqual(noisy, "order-below-noise-floor" in codes)
                if noisy:
                    self.assertEqual("findings", receipt["status"])
                    self.assertTrue(receipt["observed_orders"])
        self.assertEqual("passed", run_numerical_verification(self.payload(
            refinements=zero, thresholds={}, cross_method=[]))["status"])

    def test_cross_method_agreement_compares_every_pair(self) -> None:
        methods = [{"method": "a", "estimate": 0.0, "uncertainty": 1.0},
                   {"method": "b", "estimate": 2.9, "uncertainty": 0.0},
                   {"method": "c", "estimate": -2.9, "uncertainty": 0.0}]
        receipt = run_numerical_verification(self.payload(cross_method=methods))
        disagreements = [item["message"] for item in receipt["findings"] if item["code"] == "cross-method-disagreement"]
        self.assertEqual(["Methods b and c disagree by inf combined standard uncertainties."], disagreements)
        self.assertEqual("findings", receipt["status"])
        self.assertEqual([2.9, 2.9], [item["difference_from_first"] for item in receipt["cross_method"][1:]])
        validate_numerical_verification(receipt)
        for cross_method in ([], methods[:1], methods[:2], [methods[0], methods[1], {**methods[1], "method": "d"}]):
            with self.subTest(methods=[item["method"] for item in cross_method]):
                self.assertEqual("passed", run_numerical_verification(self.payload(cross_method=cross_method))["status"])

    def test_explicit_error_must_match_reference_value(self) -> None:
        def levels(*errors):
            return [{"resolution": h, "estimate": q, "error": e}
                    for (h, q), e in zip(((0.4, 1.16), (0.2, 1.04), (0.1, 1.01)), errors)]

        for reference, errors, flagged in (
            (1.0, (0.5, 0.1, 0.02), True),
            (1.0, (0.16, 0.04, 0.0), True),
            (1.0, (abs(1.16 - 1.0), abs(1.04 - 1.0), abs(1.01 - 1.0)), False),
            (None, (0.5, 0.1, 0.02), False),
        ):
            receipt = run_numerical_verification(self.payload(
                reference_value=reference, refinements=levels(*errors), thresholds={}))
            with self.subTest(reference=reference, errors=errors):
                self.assertEqual(flagged, "error-reference-mismatch" in {item["code"] for item in receipt["findings"]})
                self.assertEqual("findings" if flagged else "passed", receipt["status"])
        rounded = 0.1 + 0.2
        self.assertNotEqual(0.3, rounded)
        for first_error, flagged in ((0.0, False), (abs(rounded - 0.3), False), (1e-15, True)):
            receipt = run_numerical_verification(self.payload(
                reference_value=0.3, thresholds={}, refinements=[
                    {"resolution": 0.2, "estimate": rounded, "error": first_error},
                    {"resolution": 0.1, "estimate": 0.3, "error": 0.0}]))
            with self.subTest(rounded_first_error=first_error):
                self.assertEqual(flagged, "error-reference-mismatch" in {item["code"] for item in receipt["findings"]})
                self.assertEqual("findings" if flagged else "passed", receipt["status"])

    def test_review_refuses_receipt_without_minimum_observed_order(self) -> None:
        from codex_science.quantitative_sidecars import review_quantitative_sidecars

        receipt = run_numerical_verification(self.payload(
            reference_value=None, thresholds={}, refinements=self.payload()["refinements"][:2]))
        self.assertIsNone(receipt["minimum_observed_order"])
        self.assertEqual([], [item for item in review_numerical_verification(receipt) if item["severity"] != "minor"])
        forged = self.forge(receipt, lambda item: item.pop("minimum_observed_order"))
        with self.assertRaisesRegex(ValueError, "minimum_observed_order is required"):
            validate_numerical_verification(forged)
        self.assertEqual(["invalid-numerical-verification"], [item["code"] for item in review_numerical_verification(forged)])
        codes = {item["code"] for item in review_quantitative_sidecars({"numerical_verifications": [forged]})}
        self.assertIn("invalid-numerical-verification", codes)

    def test_cross_method_entry_count_is_bounded(self) -> None:
        from codex_science import numerical_verification

        limit = numerical_verification.MAX_CROSS_METHODS
        agreeing = [{"method": f"method-{index}", "estimate": 1.0, "uncertainty": 0.01} for index in range(limit)]
        receipt = run_numerical_verification(self.payload(cross_method=agreeing))
        self.assertEqual(("passed", limit), (receipt["status"], len(receipt["cross_method"])))
        for extra in (agreeing[:1], [{}]):
            with self.subTest(extra=extra):
                self.assertRefusedWithoutMutation(
                    self.payload(cross_method=agreeing + extra), f"cross_method must contain at most {limit} entries")

    def test_unknown_threshold_keys_are_refused(self) -> None:
        for thresholds in ({"minimum_orders": 1.8}, {"max_cross_method_z": 3.0, "max_resid": 0.1}):
            with self.subTest(thresholds=thresholds):
                self.assertRefusedWithoutMutation(
                    self.payload(thresholds=thresholds),
                    "allowed: max_cross_method_z, max_invariant_deviation, max_residual, minimum_order")
        for thresholds in ({}, {"minimum_order": 1.8, "max_residual": 0.1, "max_invariant_deviation": 0.1,
                                "max_cross_method_z": 3.0}):
            self.assertEqual("passed", run_numerical_verification(self.payload(thresholds=thresholds))["status"])


if __name__ == "__main__":
    unittest.main()
