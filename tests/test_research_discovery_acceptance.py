import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_discovery_acceptance.py"
TOY_PATH = ROOT / "examples" / "research-discovery" / "toy_evaluator.py"
spec = importlib.util.spec_from_file_location("run_discovery_acceptance", RUNNER_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ResearchDiscoveryAcceptanceTests(unittest.TestCase):
    def test_acceptance_runs_actual_candidates_and_leaves_review_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "acceptance"
            result = runner.run_acceptance(output)
            self.assertEqual("completed", result["status"])
            self.assertEqual("pending_independent_review", result["review"])
            scenarios = {item["scenario"]: item for item in result["scenarios"]}
            capacity = scenarios["capacity-revision"]
            self.assertEqual(0.5, capacity["first_accuracy"])
            self.assertEqual(1.0, capacity["second_accuracy"])
            self.assertTrue(capacity["changed_source_hash"])
            self.assertEqual("implementation_failure", scenarios["implementation-repair"]["failed_status"])
            self.assertEqual("not_assessed", scenarios["implementation-repair"]["failed_science_conclusion"])
            self.assertEqual(0.0, scenarios["budget-overlap-inconclusive"]["overlap"]["remaining_budget"])

            expected_evaluator_hash = hashlib.sha256(TOY_PATH.read_bytes()).hexdigest()
            for name in scenarios:
                manifest = json.loads((output / name / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual("pending", manifest["review"]["status"])
                validate_bundle(manifest, output / name)
                artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
                self.assertEqual(expected_evaluator_hash, artifacts["protected/toy_evaluator.py"])
                self.assertTrue(any(path.startswith("discovery/revisions/") for path in artifacts))
                self.assertTrue((output / name / "cycle-input.json").is_file())
                self.assertIn("Independent review: **pending**", (output / name / "index.md").read_text(encoding="utf-8"))
                self.assertEqual("independent-review", scenarios[name]["checkpoint"]["current_step"])

    def test_cycle_revision_records_the_observation_driven_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "acceptance"
            runner.run_acceptance(output)
            revisions = sorted((output / "capacity-revision" / "discovery" / "revisions").glob("*.json"))
            cycle = json.loads(revisions[-1].read_text(encoding="utf-8"))
            methods = {item["id"]: item for item in cycle["methods"]}
            self.assertNotEqual(
                methods["capacity"]["code_refs"][0]["sha256"],
                methods["directional"]["code_refs"][0]["sha256"],
            )
            experiments = {item["id"]: item for item in cycle["experiments"]}
            self.assertEqual("completed", experiments["baseline-evaluation"]["state"])
            self.assertEqual("completed", experiments["directional-evaluation"]["state"])
            self.assertEqual("nonpositive", experiments["baseline-evaluation"]["method_effect"])
            self.assertEqual(
                {"information-loss": [0.45, 0.55], "capacity-only": [0.85, 1.05]},
                experiments["baseline-evaluation"]["predictions"],
            )
            self.assertEqual(
                {"information-loss": "consistent", "capacity-only": "contradicted"},
                experiments["baseline-evaluation"]["explanation_support"],
            )
            self.assertEqual(
                {"information-loss": "consistent", "capacity-only": "contradicted"},
                experiments["directional-evaluation"]["explanation_support"],
            )
            self.assertEqual(
                {"information-loss": [0.95, 1.05], "capacity-only": [0.45, 0.55]},
                experiments["directional-evaluation"]["predictions"],
            )
            self.assertEqual("pending", experiments["directional-evaluation"]["verification"])
            self.assertEqual("improved", cycle["status"])

    def test_failure_evidence_and_overlapping_predictions_do_not_refute_a_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "acceptance"
            runner.run_acceptance(output)
            repair = json.loads(sorted((output / "implementation-repair" / "discovery" / "revisions").glob("*.json"))[-1].read_text(encoding="utf-8"))
            broken = {item["id"]: item for item in repair["experiments"]}["baseline-evaluation"]
            self.assertEqual("failed", broken["state"])
            self.assertEqual("implementation", broken["failure_kind"])
            self.assertNotIn("explanation_support", broken)
            repair_artifacts = {item["path"] for item in json.loads((output / "implementation-repair" / "manifest.json").read_text(encoding="utf-8"))["artifacts"]}
            self.assertIn("evidence/broken-receipt.json", repair_artifacts)
            self.assertIn("evidence/broken-execution.json", repair_artifacts)

            inconclusive = json.loads(sorted((output / "budget-overlap-inconclusive" / "discovery" / "revisions").glob("*.json"))[-1].read_text(encoding="utf-8"))
            experiment = inconclusive["experiments"][0]
            self.assertEqual("inconclusive", inconclusive["status"])
            self.assertEqual(
                {"information-loss", "capacity-only"}, set(experiment["explanation_support"]),
            )
            self.assertEqual(1, len(set(experiment["explanation_support"].values())))

    def test_execution_receipt_binds_measurement_to_reserved_method_and_evaluator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "acceptance"
            runner.run_acceptance(output)
            root = output / "capacity-revision"
            cycle = json.loads(sorted((root / "discovery" / "revisions").glob("*.json"))[-1].read_text(encoding="utf-8"))
            experiment = {item["id"]: item for item in cycle["experiments"]}["directional-evaluation"]
            method = {item["id"]: item for item in cycle["methods"]}["directional"]
            execution = json.loads((root / "evidence" / "directional-execution.json").read_text(encoding="utf-8"))
            measurement = json.loads((root / "evidence" / "directional-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(1, execution["schema_version"])
            self.assertEqual(experiment["id"], execution["experiment_id"])
            self.assertEqual(experiment["fingerprint"], execution["experiment_fingerprint"])
            self.assertEqual(method["id"], execution["method_id"])
            self.assertEqual(method["code_refs"], execution["code_refs"])
            self.assertEqual(cycle["evaluation"]["artifact_refs"], execution["evaluation_refs"])
            self.assertEqual(0, execution["exit_code"])
            self.assertEqual(method["code_refs"][0]["sha256"], measurement["candidate_sha256"])
            self.assertEqual("evidence/directional-receipt.json", execution["measurement_refs"][0]["path"])


if __name__ == "__main__":
    unittest.main()
