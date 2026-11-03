import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.campaign_feedback import import_assay_feedback


class CampaignFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.contract = {"schema": "campaign-feedback-v1",
            "assay": {"id": "a1", "target_construct_id": "target1", "unit": "activity-unit", "direction": "maximize"},
            "prediction_contract": {"scale": "assay-value", "unit": "activity-unit", "source_id": "toy-model", "calibration_reference": "synthetic-assay-scale"},
            "controls": [{"id": "positive", "passed": True}],
            "constraints": {"batch_size": 1, "budget": 1, "diversity_group_cap": 1},
            "candidates": [
                {"id": "parent", "construct_id": "c1", "prediction": 0, "role": "feedback"},
                {"id": "heldout", "construct_id": "c2", "prediction": 1, "role": "holdout"},
                {"id": "new-a", "construct_id": "c3", "prediction": 1, "role": "candidate", "parent_id": "parent"},
                {"id": "new-b", "construct_id": "c4", "prediction": 0, "role": "candidate", "parent_id": "heldout"},
            ]}
        self.csv = "candidate_id,assay_id,target_construct_id,construct_id,unit,replicate_id,status,value\nparent,a1,target1,c1,activity-unit,r1,measured,-2\nparent,a1,target1,c1,activity-unit,r2,measured,0\nheldout,a1,target1,c2,activity-unit,r1,measured,3\n"

    def test_negative_measurements_replicates_and_parent_feedback_change_selection(self):
        result = import_assay_feedback(self.contract, self.csv)
        self.assertEqual(result["summaries"]["parent"], {"n_independent": 2, "mean": -1, "standard_error": 1})
        self.assertEqual(result["heldout_mae"], 2)
        self.assertEqual(result["next_batch"]["selected"][0]["id"], "new-a")
        changed = self.csv.replace("measured,-2", "measured,-20")
        result = import_assay_feedback(self.contract, changed)
        self.assertEqual(result["next_batch"]["selected"][0]["id"], "new-b")

    def test_heldout_label_never_changes_candidate_proposal(self):
        first = import_assay_feedback(self.contract, self.csv)
        changed = self.csv.replace("r1,measured,3", "r1,measured,10000")
        second = import_assay_feedback(self.contract, changed)
        for result in (first, second):
            result["next_batch"].pop("created_at", None)
            result["next_batch"].pop("fingerprint", None)
        self.assertEqual(first["next_batch"], second["next_batch"])
        self.assertNotEqual(first["heldout_mae"], second["heldout_mae"])

    def test_missing_failed_censored_retained_and_not_silently_retried(self):
        for status in ("missing", "failed", "censored"):
            with self.subTest(status=status):
                text = self.csv + f"new-a,a1,target1,c3,activity-unit,r1,{status},\n"
                result = import_assay_feedback(self.contract, text)
                self.assertEqual(result["rows"][-1]["status"], status)
                self.assertIsNone(result["rows"][-1]["value"])
                self.assertEqual(result["next_batch"]["selected"][0]["id"], "new-b")

    def test_failed_control_blocks_next_batch(self):
        self.contract["controls"][0]["passed"] = False
        result = import_assay_feedback(self.contract, self.csv)
        self.assertFalse(result["controls_passed"])
        self.assertIsNone(result["next_batch"])

    def test_mismatched_identity_unit_duplicate_replicate_and_nonfinite_rejected(self):
        for text in (self.csv.replace("a1", "wrong"), self.csv.replace("c1", "wrong"),
                     self.csv.replace("activity-unit", "nM"), self.csv.replace("parent,a1", "unknown,a1"),
                     self.csv + self.csv.splitlines()[1] + "\n", self.csv.replace("measured,-2", "measured,NaN"),
                     self.csv.replace("measured,-2", "measured,Inf"), self.csv.replace("measured,-2", "failed,-2")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                import_assay_feedback(self.contract, text)

    def test_invalid_contracts_rejected(self):
        cases = []
        for key, value in (("parent_feedback_weight", 2), ("controls", []), ("controls", [{"id": "x", "passed": "true"}])):
            item = copy.deepcopy(self.contract)
            item[key] = value
            cases.append(item)
        item = copy.deepcopy(self.contract)
        item["candidates"][2]["parent_id"] = "unknown"
        cases.append(item)
        item = copy.deepcopy(self.contract)
        item["candidates"][0]["construct_id"] = "other"
        cases.append(item)
        item = copy.deepcopy(self.contract)
        item["prediction_contract"]["unit"] = "logit"
        cases.append(item)
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                import_assay_feedback(item, self.csv)

    def test_candidate_and_target_constructs_are_distinct_join_keys(self):
        self.contract["candidates"][1]["construct_id"] = "binder2"
        text = self.csv.replace("heldout,a1,target1,c2", "heldout,a1,target1,binder2")
        self.assertEqual(import_assay_feedback(self.contract, text)["heldout_mae"], 2)
        with self.assertRaises(ValueError):
            import_assay_feedback(self.contract, text.replace("target1", "other-target"))

    def test_construct_alias_cannot_bypass_holdout_or_reselect_measured_construct(self):
        for index in (0, 2):
            contract = copy.deepcopy(self.contract)
            contract["candidates"][index]["construct_id"] = "c2"
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "duplicate immutable"):
                import_assay_feedback(contract, self.csv)

    def test_cli_works_from_foreign_cwd_without_pythonpath(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            (temporary / "contract.json").write_text(json.dumps(self.contract))
            (temporary / "assay.csv").write_text(self.csv)
            result = subprocess.run([sys.executable, str(root / "scripts/import_campaign_feedback.py"),
                str(temporary / "contract.json"), str(temporary / "assay.csv")], cwd=directory,
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["heldout_mae"], 2)
