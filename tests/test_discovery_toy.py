import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "examples" / "research-discovery" / "toy_evaluator.py"
spec = importlib.util.spec_from_file_location("toy_evaluator", EVALUATOR_PATH)
assert spec is not None and spec.loader is not None
toy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = toy
spec.loader.exec_module(toy)


class ResearchDiscoveryToyTests(unittest.TestCase):
    def test_information_loss_has_a_held_out_half_accuracy_bound(self) -> None:
        baseline = toy.evaluate("baseline")
        capacity = toy.evaluate("capacity")

        for receipt in (baseline, capacity):
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(0.5, receipt["primary_accuracy"])
            self.assertTrue(receipt["controls"]["all_held_out_opposite_label_pairs_identical"])
            self.assertEqual(0.5, receipt["controls"]["information_bound_accuracy"])
            self.assertEqual({"test:-5", "test:+5", "test:-6", "test:+6"}, set(receipt["test_ids"]))
            self.assertTrue(all(item["id"].startswith("test:") for item in receipt["predictions"]))

    def test_directional_representation_generalizes_on_unseen_magnitudes(self) -> None:
        directional = toy.evaluate("directional")

        self.assertEqual("completed", directional["status"])
        self.assertEqual(1.0, directional["primary_accuracy"])
        self.assertEqual(0.5, directional["baseline_accuracy"])
        self.assertEqual(0.5, directional["effect_vs_baseline_accuracy"])
        self.assertFalse(directional["controls"]["all_held_out_opposite_label_pairs_identical"])
        self.assertTrue(all(item["correct"] for item in directional["predictions"]))

    def test_candidate_source_is_real_and_failure_is_not_a_science_conclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate.py"
            toy.write_candidate(candidate, "directional")
            receipt = toy.evaluate_candidate(candidate, mode="external")
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(1.0, receipt["primary_accuracy"])
            self.assertEqual(64, len(receipt["candidate_sha256"]))

            candidate.write_text("def represent(x):\n    return ()\n", encoding="utf-8")
            failed = toy.evaluate_candidate(candidate, mode="external")
            self.assertEqual("implementation_failure", failed["status"])
            self.assertEqual("not_assessed", failed["science_conclusion"])
            self.assertIsNone(failed["primary_accuracy"])

    def test_candidate_contract_rejects_boolean_and_inference_width_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate.py"
            candidate.write_text("def represent(x):\n    return (True,)\n", encoding="utf-8")
            boolean = toy.evaluate_candidate(candidate)
            self.assertEqual("implementation_failure", boolean["status"])
            self.assertIn("boolean", boolean["failure"]["message"])

            candidate.write_text(
                "def represent(x):\n"
                "    return (x,) if abs(x) < 5 else (x, x * x)\n",
                encoding="utf-8",
            )
            changing_width = toy.evaluate_candidate(candidate)
            self.assertEqual("implementation_failure", changing_width["status"])
            self.assertIn("feature width", changing_width["failure"]["message"])

    def test_cli_emits_json_and_fails_for_injected_candidate_defect(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(EVALUATOR_PATH), "--mode", "directional"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn('"primary_accuracy": 1.0', completed.stdout)

        failed = subprocess.run(
            [sys.executable, str(EVALUATOR_PATH), "--mode", "baseline", "--broken"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, failed.returncode)
        self.assertIn('"status": "implementation_failure"', failed.stdout)


if __name__ == "__main__":
    unittest.main()
