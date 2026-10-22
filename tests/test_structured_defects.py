import copy
import unittest

from codex_science.structured_defects import structured_review_findings


def review_input(**sections):
    return {"schema": "structured-review-input-v1", **sections}


def finding_codes(payload):
    return {item["code"] for item in structured_review_findings(payload)}


class StructuredDefectTests(unittest.TestCase):
    def test_causal_overreach_requires_only_observational_support(self) -> None:
        payload = review_input(
            claims=[{"id": "claim-1", "kind": "causal", "supported_by": ["study-1"]}],
            studies=[{"id": "study-1", "design": "cohort", "population": "adults"}],
        )
        self.assertIn("causal-overreach", finding_codes(payload))

        payload["studies"][0]["design"] = "randomized controlled trial"
        self.assertNotIn("causal-overreach", finding_codes(payload))

        for design in ("prospective cohort", "retrospective case-control", "nested case control"):
            with self.subTest(design=design):
                payload["studies"][0]["design"] = design
                self.assertIn("causal-overreach", finding_codes(payload))

        for design in (
            "prospective cohort randomized trial",
            "nested case-control RCT",
            "interventional cohort study",
            "prospective cohort Mendelian randomization study",
            "prospective cohort MR study",
        ):
            with self.subTest(design=design):
                payload["studies"][0]["design"] = design
                self.assertNotIn("causal-overreach", finding_codes(payload))

        for design in ("non-randomized", "nonrandomized", "non randomised", "quasi-randomized"):
            with self.subTest(design=design):
                payload["studies"][0]["design"] = design
                self.assertIn("causal-overreach", finding_codes(payload))

    def test_population_overreach_requires_uncovered_claim_population(self) -> None:
        payload = review_input(
            claims=[{"id": "claim-1", "kind": "associational", "population": "Homo sapiens", "supported_by": ["study-1"]}],
            studies=[{"id": "study-1", "design": "cross-sectional", "population": "Mus musculus"}],
        )
        self.assertIn("population-overreach", finding_codes(payload))

        payload["studies"][0]["population"] = "Homo sapiens"
        self.assertNotIn("population-overreach", finding_codes(payload))

    def test_population_overreach_requires_declared_supporting_population(self) -> None:
        cases = [
            review_input(
                claims=[{"id": "claim-1", "kind": "associational", "population": "people", "supported_by": []}],
            ),
            review_input(
                claims=[{"id": "claim-1", "kind": "associational", "population": "people", "supported_by": ["study-1"]}],
                studies=[{"id": "study-1", "design": "cohort"}],
            ),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertNotIn("population-overreach", finding_codes(payload))

    def test_population_overreach_accepts_prefix_qualifier(self) -> None:
        payload = review_input(
            claims=[{"id": "claim-1", "kind": "associational", "population": "adults aged 18-65", "supported_by": ["study-1"]}],
            studies=[{"id": "study-1", "design": "cohort", "population": "adults"}],
        )
        self.assertNotIn("population-overreach", finding_codes(payload))

    def test_multiplicity_requires_significance_and_no_correction(self) -> None:
        payload = review_input(
            claims=[{"id": "claim-1", "kind": "associational", "significant": True, "supported_by": []}],
            analyses=[{"claim_id": "claim-1", "tests_performed": 40, "alpha": 0.05, "correction": None}],
        )
        findings = structured_review_findings(payload)
        self.assertIn("multiplicity-uncorrected", {item["code"] for item in findings})
        self.assertIn("1-(1-alpha)^m", findings[0]["message"])
        self.assertIn("0.871", findings[0]["message"])

        payload["analyses"][0]["correction"] = "holm"
        self.assertNotIn("multiplicity-uncorrected", finding_codes(payload))

        for correction in ("none", "UNCORRECTED", "No correction", " unadjusted ", " NO   CORRECTION "):
            with self.subTest(correction=correction):
                payload["analyses"][0]["correction"] = correction
                self.assertIn("multiplicity-uncorrected", finding_codes(payload))

    def test_train_test_leakage_checks_ids_and_group_ids(self) -> None:
        payload = review_input(
            model_evaluations=[{
                "train_ids": ["sample-1", "sample-2"],
                "test_ids": ["sample-2", "sample-3"],
                "train_groups": {"patient": ["patient-1"]},
                "test_groups": {"patient": ["patient-1", "patient-2"]},
            }],
        )
        findings = structured_review_findings(payload)
        self.assertEqual("train-test-leakage", findings[0]["code"])
        self.assertIn("overlap count 2", findings[0]["message"])

        evaluation = payload["model_evaluations"][0]
        evaluation["test_ids"] = ["sample-3"]
        evaluation["test_groups"] = {"patient": ["patient-2"]}
        self.assertNotIn("train-test-leakage", finding_codes(payload))

        group_only = review_input(model_evaluations=[{
            "train_groups": {"scaffold": ["scaffold-a", "scaffold-b"]},
            "test_groups": {"scaffold": ["scaffold-b", "scaffold-c"]},
        }])
        group_finding = structured_review_findings(group_only)[0]
        self.assertEqual("train-test-leakage", group_finding["code"])
        self.assertIn("overlap count 1", group_finding["message"])

    def test_unit_scale_mismatch_flags_unconverted_value_only(self) -> None:
        payload = review_input(
            source_records=[{"id": "dose", "value": 250, "unit": "mg"}],
            reported_quantities=[{"source_id": "dose", "value": 250, "unit": "g"}],
        )
        self.assertIn("unit-scale-mismatch", finding_codes(payload))

        payload["reported_quantities"][0]["value"] = 0.25
        self.assertNotIn("unit-scale-mismatch", finding_codes(payload))

    def test_unit_scale_mismatch_tolerates_normal_rounding(self) -> None:
        for source_value, reported_value in ((1234, 1.23), (1234, 1.2), (100, 0.25), (0, 0)):
            with self.subTest(source_value=source_value, reported_value=reported_value):
                payload = review_input(
                    source_records=[{"id": "dose", "value": source_value, "unit": "mg"}],
                    reported_quantities=[{"source_id": "dose", "value": reported_value, "unit": "g"}],
                )
                self.assertNotIn("unit-scale-mismatch", finding_codes(payload))

        payload = review_input(
            source_records=[{"id": "dose", "value": 100, "unit": "mg"}],
            reported_quantities=[{"source_id": "dose", "value": 1, "unit": "g"}],
        )
        self.assertIn("unit-scale-mismatch", finding_codes(payload))

    def test_unit_scale_mismatch_detects_same_unit_power_of_ten(self) -> None:
        for source_value, reported_value in ((100, 1000), (1000, 100)):
            with self.subTest(source_value=source_value, reported_value=reported_value):
                payload = review_input(
                    source_records=[{"id": "dose", "value": source_value, "unit": "mg"}],
                    reported_quantities=[{"source_id": "dose", "value": reported_value, "unit": "mg"}],
                )
                findings = structured_review_findings(payload)
                self.assertEqual("unit-scale-mismatch", findings[0]["code"])

        payload = review_input(
            source_records=[{"id": "dose", "value": 100, "unit": "mg"}],
            reported_quantities=[{"source_id": "dose", "value": 250, "unit": "mg"}],
        )
        self.assertNotIn("unit-scale-mismatch", finding_codes(payload))

    def test_common_volume_unit_case_aliases(self) -> None:
        for source_unit, reported_unit in (("ml", "mL"), ("mL", "ml"), ("l", "L"), ("L", "l")):
            with self.subTest(source_unit=source_unit, reported_unit=reported_unit):
                payload = review_input(
                    source_records=[{"id": "volume", "value": 1, "unit": source_unit}],
                    reported_quantities=[{"source_id": "volume", "value": 1, "unit": reported_unit}],
                )
                self.assertNotIn("unit-scale-mismatch", finding_codes(payload))

    def test_each_detector_rejects_malformed_relevant_structure(self) -> None:
        malformed_payloads = [
            (
                review_input(
                    claims=[{"id": "claim-1", "kind": "causal", "supported_by": "study-1"}],
                    studies=[{"id": "study-1", "design": "cohort", "population": "adults"}],
                ),
                ".+",
            ),
            (
                review_input(
                    claims=[{"id": "claim-1", "kind": "associational", "population": ["people"], "supported_by": ["study-1"]}],
                    studies=[{"id": "study-1", "design": "cohort", "population": "adults"}],
                ),
                ".+",
            ),
            (
                review_input(
                    claims=[{"id": "claim-1", "kind": "associational", "significant": True, "supported_by": []}],
                    analyses=[{"claim_id": "claim-1", "tests_performed": "40", "alpha": 0.05, "correction": None}],
                ),
                "tests_performed",
            ),
            (review_input(model_evaluations=[{"train_ids": "sample-1", "test_ids": []}]), ".+"),
            (
                review_input(
                    source_records=[{"id": "dose", "value": 250, "unit": "furlong"}],
                    reported_quantities=[{"source_id": "dose", "value": 250, "unit": "g"}],
                ),
                ".+",
            ),
        ]
        for payload, expected_error in malformed_payloads:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, expected_error):
                structured_review_findings(payload)

    def test_detector_does_not_mutate_review_input(self) -> None:
        payload = review_input(
            claims=[{"id": " claim-1 ", "kind": "associational", "supported_by": []}],
            source_records=[{"id": "dose", "value": 250, "unit": "mg"}],
            reported_quantities=[{"source_id": "dose", "value": 0.25, "unit": "g"}],
        )
        original = copy.deepcopy(payload)
        structured_review_findings(payload)
        self.assertEqual(original, payload)


if __name__ == "__main__":
    unittest.main()
