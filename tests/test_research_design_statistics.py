import copy
import unittest

from codex_science.research_design import build_research_design, review_research_design
from codex_science.statistics_runtime import benjamini_hochberg, run_statistical_analysis


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


if __name__ == "__main__":
    unittest.main()
