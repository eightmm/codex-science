import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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

    def _assert_population_coverage(self, target, populations, overreach) -> None:
        payload = review_input(
            claims=[{"id": "C", "kind": "associational", "population": target,
                     "supported_by": [str(index) for index in range(len(populations))]}],
            studies=[{"id": str(index), "design": "cohort", "population": population}
                     for index, population in enumerate(populations)],
        )
        original = copy.deepcopy(payload)
        expected = [{"code": "population-overreach", "severity": "major"}] if overreach else []
        with tempfile.TemporaryDirectory() as temporary:
            case_path = Path(temporary) / "population.json"
            input_bytes = (json.dumps({"case_id": "population", "structured_review_input": payload,
                                      "expected_findings": expected}, indent=2) + "\n").encode()
            case_path.write_bytes(input_bytes)
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" /
                                     "run_reviewer_benchmark.py"), "--cases", temporary],
                capture_output=True, text=True,
                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")),
            )
            self.assertEqual(input_bytes, case_path.read_bytes())
            self.assertEqual(2 if overreach is None else 0, result.returncode, result.stderr)
            if overreach is None:
                self.assertIn("population must be a non-empty string", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
            else:
                detail = json.loads(result.stdout)["details"][0]
                self.assertTrue(detail["passed"], detail)
        if overreach is None:
            with self.assertRaisesRegex(ValueError, "population must be a non-empty string"):
                structured_review_findings(payload)
        else:
            self.assertEqual(overreach, "population-overreach" in finding_codes(payload))
        self.assertEqual(original, payload)

    def test_population_overreach_rejects_added_list_components(self) -> None:
        for target, populations, overreach in (
            ("adults and children", ["adults"], True),
            ("adults, children", ["adults"], True),
            ("adults; children", ["adults"], True),
            ("adults / children", ["adults"], True),
            ("children and adults", ["adults"], True),
            ("adults aged 18-65 and children", ["adults"], True),
            ("adults 65 and older and children", ["adults"], True),
            ("men aged 20-30", ["men and women aged 50-70"], True),
            ("men in europe", ["men and women with diabetes"], True),
            ("men aged 20-30", ["men and women \u226565"], True),
            ("men aged 20-30", ["men and women (\u226565 y)"], True),
            ("men aged 20-30", ["men and women over-65"], True),
            ("adults and older children", ["adults"], True),
            ("young adults and older adults", ["young adults"], True),
            ("adults, children.", ["adults"], True),
            ("adults aged between 18 and 65 and children", ["adults"], True),
            ("adults and children and infants", ["adults", "children"], True),
            ("children", [", ; / and "], True),
            (", ; / and ", ["adults"], True),
            ("adults and children", [], False),
            ("adults or children", ["adults"], False),
            ("children", ["adults or children"], True),
            ("", ["adults"], None),
            ("  ", ["adults"], None),
            (0, ["adults"], None),
            (None, ["adults"], None),
            (["adults"], ["adults"], None),
            ("adults", [""], None),
            ("adults", [0], None),
            ("adults", [None], None),
            ("adults", [["adults"]], None),
        ):
            with self.subTest(target=target, populations=populations):
                self._assert_population_coverage(target, populations, overreach)

    def test_population_overreach_accepts_reordered_list_components(self) -> None:
        for target, populations in (
            ("adults and children", ["children and adults"]),
            ("adults, children", ["children and adults"]),
            ("adults; children", ["children / adults"]),
            (" ADULTS AND children ", [" Children, ADULTS "]),
            ("adults and children", ["adults", "children"]),
            ("adults and adults", ["adults"]),
            ("adults, and children", ["children, adults"]),
            ("adults", ["adults"]),
            ("patients aged 18 and over", ["patients"]),
            ("adults 65 and older", ["adults"]),
            ("adults aged between 18 and 65", ["adults"]),
            ("adults, aged 18-65", ["adults"]),
            ("patients aged 18 and up", ["patients"]),
            ("patients aged 65 years and greater", ["patients"]),
            ("men", ["men and women aged 50-70"]),
            ("older adults", ["middle-aged and older adults"]),
            ("at-risk adults", ["healthy adults and at-risk adults"]),
            ("patients with heart failure and reduced ejection fraction", ["patients with heart failure"]),
            ("adults with diabetes and hypertension", ["adults with diabetes"]),
            ("women aged 50-70 and men", ["men and women aged 50-70"]),
        ):
            with self.subTest(target=target, populations=populations):
                self._assert_population_coverage(target, populations, False)

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

    def test_group_names_must_be_unique_after_normalization(self) -> None:
        pairs = [("patient", ["p1"]), (" patient ", ["p2"])]
        for field in ("train_groups", "test_groups"):
            for entries in (pairs, list(reversed(pairs))):
                with self.subTest(field=field, entries=entries):
                    evaluation = {"train_groups": {"patient": ["p1"]},
                                  "test_groups": {"patient": ["p1"]}}
                    evaluation[field] = dict(entries)
                    with self.assertRaisesRegex(ValueError, field + r".*duplicate.*patient"):
                        structured_review_findings(review_input(model_evaluations=[evaluation]))
        self.assertEqual(set(), finding_codes(review_input(model_evaluations=[{
            "train_ids": [], "test_ids": [], "train_groups": {}, "test_groups": {},
        }])))
        for name in ("", "  ", 0):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "group name"):
                structured_review_findings(review_input(model_evaluations=[{
                    "train_groups": {name: []}, "test_groups": {name: []},
                }]))
        self.assertIn("train-test-leakage", finding_codes(review_input(model_evaluations=[{
            "train_groups": {" patient ": ["p1"]}, "test_groups": {"patient": ["p1"]},
        }])))

    def test_population_overreach_accepts_explicit_whole_subgroup(self) -> None:
        payload = review_input(
            claims=[{"id": "C", "kind": "associational", "population": "children", "supported_by": ["S"]}],
            studies=[{"id": "S", "design": "cohort", "population": "adults and children"}],
        )
        for target, population, overreach in (
            ("children", "adults and children", False),
            ("children", "adults, children", False),
            ("children", "adults; children", False),
            ("children", "adults / children", False),
            ("CHILDREN", " Adults AND Children ", False),
            (" children ", "adults ; CHILDREN", False),
            ("young children", "adults and young children", False),
            ("adults", "older adults", True),
            ("patients", "diabetic patients", True),
            ("children", "adults, excluding children", True),
            ("children", "adults and older children", True),
            ("children", "adults and children.", True),
            ("children", "adults andchildren", True),
            ("children", "adultsand children", True),
            ("children", ", ; / and ", True),
            ("children", "schoolchildren", True),
            ("children", "childrenhood", True),
            ("young children", "young childrens", True),
            ("children", "adults", True),
        ):
            with self.subTest(target=target, population=population):
                payload["claims"][0]["population"] = target
                payload["studies"][0]["population"] = population
                self.assertEqual(overreach, "population-overreach" in finding_codes(payload))
        payload["studies"].append({"id": "unrelated", "design": "cohort", "population": "children"})
        self.assertIn("population-overreach", finding_codes(payload))

    def test_multiplicity_count_refuses_float_overflow(self) -> None:
        payload = review_input(
            claims=[{"id": "C", "kind": "associational", "significant": True, "supported_by": []}],
            analyses=[{"claim_id": "C", "tests_performed": 10**309, "alpha": 0.05, "correction": None}],
        )
        limit = int(sys.float_info.max)
        for count in (10**309, limit + 1, 0, -1, "2", None, True):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "analyses.*tests_performed"):
                payload["analyses"][0]["tests_performed"] = count
                structured_review_findings(payload)
        for count, expected in ((1, False), (2, True), (limit, True)):
            with self.subTest(count=count):
                payload["analyses"][0]["tests_performed"] = count
                self.assertEqual(expected, "multiplicity-uncorrected" in finding_codes(payload))

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
