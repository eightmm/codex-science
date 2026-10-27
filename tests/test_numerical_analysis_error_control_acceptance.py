import json
import unittest
from pathlib import Path

from codex_science.numerical_verification import run_numerical_verification


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "numerical-analysis-error-control" / "input.json"

SEEDED_FAILURE_TESTS = {
    "non-refining-resolution-sequence": "test_non_refining_resolution_sequence_is_detected",
    "nonmonotone-error": "test_nonmonotone_error_is_detected",
    "convergence-order-below-threshold": "test_convergence_order_below_threshold_is_detected",
    "residual-threshold-failure": "test_residual_threshold_failure_is_detected",
    "invariant-threshold-failure": "test_invariant_threshold_failure_is_detected",
    "cross-method-disagreement": "test_cross_method_disagreement_is_detected",
}


class NumericalAnalysisErrorControlAcceptanceTests(unittest.TestCase):
    def payload(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assertFinding(self, payload, code, message_fragment):
        result = run_numerical_verification(payload)
        self.assertEqual("findings", result["status"])
        matching = [item for item in result["findings"] if item["code"] == code]
        self.assertTrue(matching, result["findings"])
        self.assertIn(message_fragment, matching[0]["message"])

    def test_acceptance_fixture_passes(self):
        result = run_numerical_verification(self.payload())
        self.assertEqual("passed", result["status"])
        self.assertEqual("manufactured-second-order-refinement", result["verification_id"])
        self.assertEqual(4, len(result["refinements"]))
        self.assertAlmostEqual(2.0, result["minimum_observed_order"])
        self.assertEqual([], result["findings"])
        self.assertEqual(64, len(result["fingerprint"]))

    def test_non_refining_resolution_sequence_is_detected(self):
        payload = self.payload()
        payload["refinements"][1]["resolution"] = payload["refinements"][0]["resolution"]
        self.assertFinding(payload, "non-refining-resolution-sequence", "strictly decrease")

    def test_nonmonotone_error_is_detected(self):
        payload = self.payload()
        payload["refinements"][1]["estimate"] = 1.2
        self.assertFinding(payload, "nonmonotone-error", "does not decrease monotonically")

    def test_convergence_order_below_threshold_is_detected(self):
        payload = self.payload()
        payload["refinements"] = [
            {"resolution": 0.4, "estimate": 1.08, "residual": 0.001, "invariants": {"mass": 0.001}},
            {"resolution": 0.2, "estimate": 1.04, "residual": 0.001, "invariants": {"mass": 0.001}},
            {"resolution": 0.1, "estimate": 1.02, "residual": 0.001, "invariants": {"mass": 0.001}},
            {"resolution": 0.05, "estimate": 1.01, "residual": 0.001, "invariants": {"mass": 0.001}},
        ]
        self.assertFinding(payload, "convergence-order-below-threshold", "below required")

    def test_residual_threshold_failure_is_detected(self):
        payload = self.payload()
        payload["refinements"][1]["residual"] = 0.02
        self.assertFinding(payload, "residual-threshold-failed", "exceeds")

    def test_invariant_threshold_failure_is_detected(self):
        payload = self.payload()
        payload["refinements"][1]["invariants"]["mass"] = 0.02
        self.assertFinding(payload, "invariant-threshold-failed", "exceeds")

    def test_cross_method_disagreement_is_detected(self):
        payload = self.payload()
        payload["cross_method"][1]["estimate"] = 1.02
        self.assertFinding(payload, "cross-method-disagreement", "disagree by")

    def test_quality_seeded_failures_have_matching_tests(self):
        quality = json.loads(
            (ROOT / "authored-skills" / "numerical-analysis-error-control" / "quality.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        for test_name in SEEDED_FAILURE_TESTS.values():
            with self.subTest(test_name=test_name):
                self.assertTrue(callable(getattr(self, test_name, None)))


if __name__ == "__main__":
    unittest.main()
