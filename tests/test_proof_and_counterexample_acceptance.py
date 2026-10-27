import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "search_counterexample.py"
FIXTURE = ROOT / "examples" / "proof-and-counterexample" / "input.json"

SEEDED_FAILURE_TESTS = {
    "false-universal-claim": "test_false_universal_claim_is_disproved",
    "sampled-grid-cannot-prove-finite-claim": "test_sampled_grid_cannot_prove_finite_claim",
    "truncated-search-cannot-prove-claim": "test_truncated_search_cannot_prove_claim",
}


class ProofAndCounterexampleAcceptanceTests(unittest.TestCase):
    def _run(self, payload: dict) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            input_path = temporary / "input.json"
            output_path = temporary / "result.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(input_path), "--output", str(output_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            result = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
            return completed, result

    def _fixture(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_acceptance_fixture_is_exact_finite_exhaustion(self) -> None:
        completed, result = self._run(self._fixture())
        self.assertEqual(0, completed.returncode, completed.stderr)
        assert result is not None
        self.assertEqual("acceptance-square-nonnegative", result["claim_id"])
        self.assertEqual("proved-by-exhaustion", result["status"])
        self.assertTrue(result["exhaustive"])
        self.assertTrue(result["exact_domains"])
        self.assertEqual(5, result["evaluations"])
        self.assertFalse(result["general_proof"])

    def test_false_universal_claim_is_disproved(self) -> None:
        payload = self._fixture()
        payload["conclusion"] = "x*x > 0"
        completed, result = self._run(payload)
        self.assertEqual(0, completed.returncode, completed.stderr)
        assert result is not None
        self.assertEqual("disproved", result["status"])
        self.assertEqual({"x": 0}, result["counterexample"])

    def test_sampled_grid_cannot_prove_finite_claim(self) -> None:
        payload = self._fixture()
        payload["variables"] = [{"name": "x", "float_grid": {"start": -1.0, "stop": 1.0, "count": 5}}]
        completed, result = self._run(payload)
        self.assertEqual(0, completed.returncode, completed.stderr)
        assert result is not None
        self.assertEqual("tested-no-counterexample", result["status"])
        self.assertFalse(result["exact_domains"])
        self.assertFalse(result["exhaustive"])

    def test_truncated_search_cannot_prove_claim(self) -> None:
        payload = self._fixture()
        payload["variables"] = [{"name": "x", "integer_range": {"start": 0, "stop": 4, "step": 1}}]
        payload["conclusion"] = "x < 2"
        payload["max_evaluations"] = 1
        completed, result = self._run(payload)
        self.assertEqual(0, completed.returncode, completed.stderr)
        assert result is not None
        self.assertEqual("bounded-no-counterexample", result["status"])
        self.assertEqual(1, result["evaluations"])
        self.assertFalse(result["exhaustive"])

    def test_quality_declares_only_exercised_seeded_failures(self) -> None:
        quality = json.loads((ROOT / "authored-skills" / "proof-and-counterexample" / "quality.json").read_text(encoding="utf-8"))
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertIn("examples/proof-and-counterexample/input.json", quality["acceptance_fixtures"])
        self.assertIn("tests/test_proof_and_counterexample_acceptance.py", quality["test_files"])
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        for test_name in SEEDED_FAILURE_TESTS.values():
            with self.subTest(test=test_name):
                self.assertTrue(callable(getattr(self, test_name, None)))


if __name__ == "__main__":
    unittest.main()
