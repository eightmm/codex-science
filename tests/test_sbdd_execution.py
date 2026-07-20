import copy
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest
from codex_science.sbdd_execution import compute_acceptance, execute_acceptance
from codex_science.workbench import render_workbench


class ExecutableSBDDAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.input_path = self.root / "examples" / "sbdd-executable" / "input.json"
        self.payload = json.loads(self.input_path.read_text(encoding="utf-8"))

    def test_numeric_acceptance_metrics_pass_prespecified_thresholds(self) -> None:
        poses, metrics, leakage = compute_acceptance(self.payload)
        self.assertEqual([], leakage)
        self.assertEqual(6, len(poses))
        by_name = {item["name"]: item for item in metrics}
        self.assertTrue(by_name["top1_symmetry_rmsd"]["passed"])
        self.assertTrue(by_name["interaction_recovery"]["passed"])
        self.assertTrue(by_name["pr_auc"]["passed"])
        self.assertAlmostEqual(1.0, by_name["pr_auc"]["value"])
        self.assertIsInstance(by_name["top1_symmetry_rmsd"]["confidence_interval"], list)

    def test_threshold_failure_is_machine_readable(self) -> None:
        failed = copy.deepcopy(self.payload)
        failed["numeric_thresholds"]["top1_symmetry_rmsd"] = 0.1
        _poses, metrics, _leakage = compute_acceptance(failed)
        by_name = {item["name"]: item for item in metrics}
        self.assertFalse(by_name["top1_symmetry_rmsd"]["passed"])

    def test_threshold_failure_cannot_pass_artifact_review(self) -> None:
        failed = copy.deepcopy(self.payload)
        failed["numeric_thresholds"]["top1_symmetry_rmsd"] = 0.1
        with tempfile.TemporaryDirectory() as tempdir:
            temporary = Path(tempdir)
            input_path = temporary / "input.json"
            output = temporary / "run"
            input_path.write_text(json.dumps(failed), encoding="utf-8")
            manifest_path = execute_acceptance(
                input_path,
                output,
                registry_path=self.root / "models" / "registry-v2.json",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            review = review_manifest(manifest, output, sidecars=validate_bundle(manifest, output))
            self.assertEqual("findings", review["status"])
            self.assertIn("acceptance-metric-failed", {item["code"] for item in review["findings"]})

    def test_acceptance_receipts_describe_the_actual_local_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            execute_acceptance(
                self.input_path,
                output,
                registry_path=self.root / "models" / "registry-v2.json",
            )
            model_receipt = json.loads((output / "model_receipt.json").read_text(encoding="utf-8"))
            review_receipt = json.loads((output / "review_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("deterministic-translation-baseline", model_receipt["model_id"])
            self.assertFalse(review_receipt["independent"])
            self.assertNotIn("reproduction", review_receipt["review_modes"])

    def test_execution_writes_a_valid_reviewed_bundle_and_offline_workbench(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            manifest_path = execute_acceptance(self.input_path, output, registry_path=self.root / "models" / "registry-v2.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sidecars = validate_bundle(manifest, output)
            review = review_manifest(manifest, output, sidecars=sidecars)
            self.assertEqual("passed", review["status"], json.dumps(review, indent=2))
            self.assertEqual([], sidecars["advanced_findings"])
            self.assertTrue((output / "metrics.json").is_file())
            self.assertTrue((output / "review_receipt.json").is_file())
            html = render_workbench(manifest, output)
            self.assertIn("Scientific workbench", html)
            self.assertIn("claim-sbdd-acceptance", html)
            self.assertIn("not evidence of experimental binding affinity", (output / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
