import copy
import unittest

from codex_science.research_design import build_research_design, review_research_design
from codex_science.statistics_runtime import (
    _extreme,
    _finite,
    _hedges_g,
    _median,
    _paired_standardized,
    _quantile,
    benjamini_hochberg,
    review_statistical_analysis,
    run_statistical_analysis,
    validate_statistical_analysis,
)


class ResearchDesignStatisticsTests(unittest.TestCase):
    def valid_design(self) -> dict:
        return {
            "schema_version": 1,
            "design_id": "D1",
            "question": "Does B differ from A?",
            "experimental_unit": "sample",
            "observational_unit": "sample",
            "outcome": {"name": "response", "measurement": "one value per sample", "subjective": False},
            "estimand": {"population": "fixture samples", "contrast": "B-A", "summary_measure": "mean difference", "causal": False},
            "assignment": {"type": "randomized", "mechanism": "fixed balanced randomization", "allocation_concealment": True},
            "analysis": {"method": "exact randomization", "aggregation_unit": "sample", "cluster_adjustment": False},
            "primary_endpoints": [{"id": "primary", "decision_threshold": "report effect and interval"}],
            "multiplicity": {"method": "none", "family_size": 1},
            "missing_data": {"strategy": "none-expected", "assumptions": "none missing"},
            "exclusions": {"prespecified": True, "criteria": ["malformed records only"]},
            "stopping": {"planned_looks": 1, "decision_rule": "one final analysis"},
            "sample_size": {"planned": 8, "rationale": "exact deterministic fixture"},
            "sensitivity_analyses": ["median difference"],
            "identification_assumptions": [],
            "blinding": {"outcome_assessor": True},
            "locked_before_outcomes": True,
        }

    def test_valid_design_is_fingerprinted_and_clean(self) -> None:
        design = build_research_design(self.valid_design())
        self.assertEqual("passed", design["audit_status"])
        self.assertEqual([], design["audit_findings"])
        self.assertEqual([], review_research_design(design))
        self.assertEqual(64, len(design["fingerprint"]))

    def test_design_detects_pseudoreplication_optional_stopping_and_causal_gap(self) -> None:
        broken = self.valid_design()
        broken["experimental_unit"] = "animal"
        broken["observational_unit"] = "cell"
        broken["analysis"]["aggregation_unit"] = "cell"
        broken["stopping"] = {"planned_looks": 4}
        broken["estimand"]["causal"] = True
        broken["assignment"] = {"type": "observational"}
        broken["identification_assumptions"] = []
        broken["locked_before_outcomes"] = False
        broken["exclusions"]["prespecified"] = False
        result = build_research_design(broken)
        codes = {item["code"] for item in result["audit_findings"]}
        self.assertIn("pseudoreplication-risk", codes)
        self.assertIn("optional-stopping-uncontrolled", codes)
        self.assertIn("causal-identification-missing", codes)
        self.assertIn("observational-confounding-unaddressed", codes)
        self.assertIn("outcome-dependent-design", codes)
        self.assertIn("posthoc-exclusion-risk", codes)

    def independent_input(self) -> dict:
        return {
            "schema_version": 1,
            "analysis_id": "A1",
            "claim_id": "C1",
            "design_id": "D1",
            "analysis_type": "independent",
            "group_labels": ["control", "treatment"],
            "estimand": "mean-difference",
            "alternative": "two-sided",
            "confidence_level": 0.95,
            "seed": 42,
            "bootstrap_replicates": 2000,
            "permutation_replicates": 5000,
            "within_unit_aggregation": "mean",
            "data": [
                {"unit_id": "C1", "group": "control", "value": 1.0},
                {"unit_id": "C2", "group": "control", "value": 1.5},
                {"unit_id": "C3", "group": "control", "value": 2.0},
                {"unit_id": "C4", "group": "control", "value": 2.5},
                {"unit_id": "T1", "group": "treatment", "value": 3.0},
                {"unit_id": "T2", "group": "treatment", "value": 3.5},
                {"unit_id": "T3", "group": "treatment", "value": 4.0},
                {"unit_id": "T4", "group": "treatment", "value": 4.5},
            ],
            "hypotheses": [],
        }

    def test_independent_analysis_is_exact_and_deterministic(self) -> None:
        first = run_statistical_analysis(self.independent_input())
        second = run_statistical_analysis(self.independent_input())
        self.assertEqual(first, second)
        self.assertAlmostEqual(2.0, first["effect"]["estimate"])
        self.assertEqual("treatment - control", first["contrast"])
        self.assertTrue(first["test"]["exact"])
        self.assertEqual(70, first["test"]["permutations"])
        self.assertAlmostEqual(2 / 70, first["test"]["p_value"])
        self.assertEqual(4, first["sample"]["experimental_units"]["control"])
        self.assertEqual("completed", first["status"])

    def test_repeated_measurements_are_aggregated_to_experimental_units(self) -> None:
        payload = self.independent_input()
        payload["data"].extend(
            [
                {"unit_id": "C1", "group": "control", "value": 1.2},
                {"unit_id": "T1", "group": "treatment", "value": 3.2},
            ]
        )
        result = run_statistical_analysis(payload)
        self.assertEqual(2, result["sample"]["duplicate_observations_aggregated"])
        self.assertEqual(4, result["sample"]["experimental_units"]["control"])

    def test_paired_sign_flip_analysis(self) -> None:
        payload = {
            "schema_version": 1,
            "analysis_id": "paired",
            "claim_id": "C2",
            "design_id": "D2",
            "analysis_type": "paired",
            "group_labels": ["before", "after"],
            "estimand": "mean-difference",
            "alternative": "two-sided",
            "confidence_level": 0.95,
            "seed": 7,
            "bootstrap_replicates": 1000,
            "permutation_replicates": 1000,
            "within_unit_aggregation": "mean",
            "data": [
                {"unit_id": "P1-before", "pair_id": "P1", "group": "before", "value": 1.0},
                {"unit_id": "P1-after", "pair_id": "P1", "group": "after", "value": 2.0},
                {"unit_id": "P2-before", "pair_id": "P2", "group": "before", "value": 2.0},
                {"unit_id": "P2-after", "pair_id": "P2", "group": "after", "value": 3.0},
                {"unit_id": "P3-before", "pair_id": "P3", "group": "before", "value": 1.5},
                {"unit_id": "P3-after", "pair_id": "P3", "group": "after", "value": 2.5},
                {"unit_id": "P4-before", "pair_id": "P4", "group": "before", "value": 0.5},
                {"unit_id": "P4-after", "pair_id": "P4", "group": "after", "value": 1.5},
            ],
            "hypotheses": [],
        }
        result = run_statistical_analysis(payload)
        self.assertAlmostEqual(1.0, result["effect"]["estimate"])
        self.assertTrue(result["test"]["exact"])
        self.assertEqual(16, result["test"]["permutations"])
        self.assertAlmostEqual(2 / 16, result["test"]["p_value"])

    def test_benjamini_hochberg_is_monotone_in_rank(self) -> None:
        adjusted = benjamini_hochberg(
            [
                {"id": "h1", "p_value": 0.01},
                {"id": "h2", "p_value": 0.04},
                {"id": "h3", "p_value": 0.03},
            ]
        )
        by_id = {item["id"]: item["q_value"] for item in adjusted}
        self.assertAlmostEqual(0.03, by_id["h1"])
        self.assertAlmostEqual(0.04, by_id["h2"])
        self.assertAlmostEqual(0.04, by_id["h3"])

    def test_seed_is_mandatory(self) -> None:
        payload = self.independent_input()
        payload.pop("seed")
        with self.assertRaises(ValueError):
            run_statistical_analysis(payload)

    def test_numeric_helpers_reject_invalid_inputs_and_handle_boundaries(self) -> None:
        for value, message in ((True, "value must be numeric"), (float("nan"), "value must be finite")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                _finite(value, "value")
        self.assertEqual(4.0, _quantile([4.0], 0.25))
        self.assertEqual(2.0, _quantile([1.0, 3.0], 0.5))
        with self.assertRaisesRegex(ValueError, "empty sample"):
            _quantile([], 0.5)
        self.assertEqual(2.5, _median([1.0, 4.0]))
        with self.assertRaisesRegex(ValueError, "requires observations"):
            _median([])

    def test_standardized_effects_are_missing_for_degenerate_samples(self) -> None:
        self.assertIsNone(_hedges_g([1.0], [2.0, 3.0]))
        self.assertIsNone(_hedges_g([1.0, 1.0], [2.0, 2.0]))
        self.assertIsNone(_paired_standardized([1.0]))
        self.assertIsNone(_paired_standardized([1.0, 1.0]))

    def test_extreme_value_supports_each_alternative_and_rejects_unknown(self) -> None:
        self.assertTrue(_extreme(-3.0, 2.0, "two-sided"))
        self.assertTrue(_extreme(3.0, 2.0, "greater"))
        self.assertTrue(_extreme(-3.0, -2.0, "less"))
        with self.assertRaisesRegex(ValueError, "unsupported alternative"):
            _extreme(1.0, 1.0, "sideways")

    def test_benjamini_hochberg_refusals_do_not_mutate_hypotheses(self) -> None:
        for invalid, message in (
            ([{"id": "", "p_value": 0.2}], r"hypotheses\[0\]\.id"),
            ([{"id": "h", "p_value": 1.01}], "between 0 and 1"),
            ([{"id": "h", "p_value": 0.2}, {"id": "h", "p_value": 0.3}], "unique"),
        ):
            original = copy.deepcopy(invalid)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                benjamini_hochberg(invalid)
            self.assertEqual(original, invalid)
        self.assertEqual([], benjamini_hochberg([]))

    def test_analysis_refusals_name_detected_problem_without_mutating_payload(self) -> None:
        cases = (
            ("schema_version", 2, "schema"),
            ("confidence_level", 0.5, "confidence_level"),
            ("bootstrap_replicates", 199, "bootstrap_replicates"),
            ("permutation_replicates", 100001, "permutation_replicates"),
        )
        for field, value, message in cases:
            payload = self.independent_input()
            payload[field] = value
            original = copy.deepcopy(payload)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                run_statistical_analysis(payload)
            self.assertEqual(original, payload)

    def test_analysis_rejects_malformed_rows_and_bad_hypotheses_without_mutation(self) -> None:
        cases = (
            (lambda p: p["data"].__setitem__(0, None), r"data\[0\] must be an object"),
            (lambda p: p["data"][0].update(group="other"), r"data\[0\]\.group"),
            (lambda p: p["data"][0].update(value=float("inf")), r"data\[0\]\.value must be finite"),
            (lambda p: p.update(hypotheses=[{"id": "h", "p_value": 2}]), "p-values"),
            (lambda p: p.update(hypotheses=[None]), "hypotheses must be a list of objects"),
        )
        for change, message in cases:
            payload = self.independent_input()
            change(payload)
            original = copy.deepcopy(payload)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                run_statistical_analysis(payload)
            self.assertEqual(original, payload)

    def test_row_preparation_rejects_empty_groups_and_invalid_group_contracts(self) -> None:
        cases = (
            (lambda p: p.update(data=[]), "non-empty list"),
            (lambda p: p.update(group_labels=["same", "same"]), "distinct"),
            (lambda p: p["data"][0].update(unit_id=" "), r"data\[0\]\.unit_id is empty"),
            (lambda p: [row.update(value=None) for row in p["data"] if row["group"] == "control"], "each analysis group needs"),
            (lambda p: p.update(within_unit_aggregation="mode"), "within_unit_aggregation"),
        )
        for change, message in cases:
            payload = self.independent_input()
            change(payload)
            original = copy.deepcopy(payload)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                run_statistical_analysis(payload)
            self.assertEqual(original, payload)

    def test_paired_monte_carlo_and_incomplete_pairs_are_reported(self) -> None:
        payload = {
            "schema_version": 1,
            "analysis_id": "paired-mc",
            "claim_id": "C3",
            "design_id": "D3",
            "analysis_type": "paired",
            "group_labels": ["before", "after"],
            "seed": 11,
            "bootstrap_replicates": 200,
            "permutation_replicates": 200,
            "data": [],
        }
        for index in range(17):
            payload["data"].extend(
                [
                    {"unit_id": f"b{index}", "pair_id": f"p{index}", "group": "before", "value": 1.0},
                    {"unit_id": f"a{index}", "pair_id": f"p{index}", "group": "after", "value": 2.0 + index},
                ]
            )
        payload["data"].append({"unit_id": "orphan", "pair_id": "incomplete", "group": "before", "value": 1.0})
        result = run_statistical_analysis(payload)
        self.assertFalse(result["test"]["exact"])
        self.assertEqual("monte-carlo-randomization", result["test"]["method"])
        self.assertEqual(200, result["test"]["permutations"])
        self.assertEqual(1, result["sample"]["incomplete_pairs_excluded"])
        self.assertEqual(17, result["sample"]["experimental_units"]["before"])

    def test_independent_monte_carlo_is_seeded_and_reports_replicate_count(self) -> None:
        payload = self.independent_input()
        for index in range(4, 10):
            payload["data"].append({"unit_id": f"C{index + 1}", "group": "control", "value": float(index)})
            payload["data"].append({"unit_id": f"T{index + 1}", "group": "treatment", "value": float(index + 2)})
        payload["permutation_replicates"] = 200
        first = run_statistical_analysis(payload)
        second = run_statistical_analysis(payload)
        self.assertEqual(first, second)
        self.assertFalse(first["test"]["exact"])
        self.assertEqual("monte-carlo-randomization", first["test"]["method"])
        self.assertEqual(200, first["test"]["permutations"])

    def test_analysis_median_output_adjusts_hypotheses_and_records_missing_data(self) -> None:
        payload = self.independent_input()
        payload["estimand"] = "median-difference"
        payload["alternative"] = "less"
        payload["hypotheses"] = [
            {"id": "secondary", "p_value": 0.04},
            {"id": "primary", "p_value": 0.01},
        ]
        payload["data"].append({"unit_id": "C5-missing", "group": "control", "value": None})
        result = run_statistical_analysis(payload)
        self.assertEqual(2.0, result["effect"]["estimate"])
        self.assertIsNone(result["effect"]["standardized_estimate"])
        self.assertEqual("benjamini-hochberg", result["multiplicity"]["method"])
        self.assertEqual(["secondary", "primary"], [item["id"] for item in result["multiplicity"]["hypotheses"]])
        self.assertEqual(1, result["sample"]["missing_counts"]["control"])
        self.assertEqual("completed", result["status"])
        validate_statistical_analysis(result)
        self.assertEqual([], review_statistical_analysis(result))

    def test_receipt_validation_and_review_report_detected_failures(self) -> None:
        receipt = run_statistical_analysis(self.independent_input())
        validate_statistical_analysis(receipt)
        broken = copy.deepcopy(receipt)
        broken["interval"]["lower"] = broken["interval"]["upper"] + 1
        original = copy.deepcopy(broken)
        with self.assertRaisesRegex(ValueError, "interval lower exceeds upper"):
            validate_statistical_analysis(broken)
        self.assertEqual(original, broken)
        findings = review_statistical_analysis(broken)
        self.assertEqual("invalid-statistical-analysis", findings[0]["code"])
        self.assertIn("interval lower exceeds upper", findings[0]["message"])

    def test_receipt_validation_names_required_fields_and_fingerprint_mismatch(self) -> None:
        receipt = run_statistical_analysis(self.independent_input())
        for field, message in (("claim_id", "claim_id is required"), ("seed", "explicit integer seed"), ("limitations", "requires limitations")):
            broken = copy.deepcopy(receipt)
            broken.pop(field, None) if field == "claim_id" else broken.update({field: [] if field == "limitations" else True})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                validate_statistical_analysis(broken)
        broken = copy.deepcopy(receipt)
        broken["analysis_id"] = "tampered"
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            validate_statistical_analysis(broken)


if __name__ == "__main__":
    unittest.main()
