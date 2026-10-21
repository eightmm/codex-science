from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from codex_science.rigor import classify_rigor

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "classify_rigor.py"


def request(**updates):
    value = {"schema": "rigor-request-v1", "deliverable": "answer",
             "source_count": 0, "claim_strength": "descriptive"}
    value.update(updates)
    return value


class RigorTests(unittest.TestCase):
    def test_each_floor_rule(self):
        cases = [
            ({"claim_strength": "causal"}, "full", "claim_strength"),
            ({"claim_strength": "confirmatory"}, "full", "claim_strength"),
            ({"domain_risk": "high_stakes"}, "full", "high_stakes_domain"),
            ({"synthesis": True, "source_count": 3}, "full", "multi_source_synthesis"),
            ({"deliverable": "durable_artifact"}, "standard", "durable_deliverable"),
            ({"deliverable": "reviewed_package"}, "standard", "durable_deliverable"),
            ({"computation": True}, "standard", "computation"),
            ({"synthesis": True, "source_count": 2}, "standard", "synthesis"),
            ({"source_count": 4}, "standard", "many_sources"),
            ({"claim_strength": "associational"}, "standard", "associational_claim"),
            ({"approval_gated_actions": True}, "standard", "approval_gated_action"),
        ]
        for changes, tier, code in cases:
            with self.subTest(changes=changes):
                result = classify_rigor(request(**changes))
                self.assertEqual(result["floor"], tier)
                self.assertIn(code, {reason["code"] for reason in result["reasons"]})

    def test_quick_default_and_requested_tiers(self):
        result = classify_rigor(request())
        self.assertEqual((result["tier"], result["floor"]), ("quick", "quick"))
        self.assertIn("default_quick", {r["code"] for r in result["reasons"]})
        low = classify_rigor(request(computation=True, requested_tier="quick"))
        self.assertEqual(low["tier"], "standard")
        self.assertIn("requested_below_floor", {r["code"] for r in low["reasons"]})
        high = classify_rigor(request(requested_tier="full"))
        self.assertEqual(high["tier"], "full")
        self.assertIn({"code": "requested_tier", "field": "requested_tier", "tier": "full"}, high["reasons"])
        escalated = classify_rigor(request(requested_tier="full", current_tier="quick"))
        self.assertTrue(escalated["escalated"])
        self.assertIn({"code": "requested_tier", "field": "requested_tier", "tier": "full"}, escalated["reasons"])

    def test_current_tier_is_monotonic_and_escalation_is_reported(self):
        retained = classify_rigor(request(current_tier="full"))
        self.assertEqual(retained["tier"], "full")
        self.assertFalse(retained["escalated"])
        self.assertIn({"code": "retained_current_tier", "field": "current_tier", "tier": "full"}, retained["reasons"])
        raised = classify_rigor(request(current_tier="quick", computation=True))
        self.assertEqual(raised["tier"], "standard")
        self.assertTrue(raised["escalated"])

    def test_approval_gate_and_policy_are_tier_independent(self):
        approval = classify_rigor(request(approval_gated_actions=True))
        decisions = [classify_rigor(request()),
                     classify_rigor(request(computation=True)),
                     classify_rigor(request(requested_tier="full")),
                     approval]
        self.assertEqual([item["tier"] for item in decisions[:3]], ["quick", "standard", "full"])
        self.assertNotEqual(approval["tier"], "quick")
        self.assertTrue(all(item["gate_policy"] == decisions[0]["gate_policy"] for item in decisions))
        self.assertTrue(decisions[0]["gate_policy"]["unchanged_by_tier"])

    def test_determinism_and_input_key_order(self):
        first = request(computation=True, source_count=2)
        second = dict(reversed(list(first.items())))
        self.assertEqual(classify_rigor(first), classify_rigor(second))

    def test_malformed_inputs(self):
        cases = [
            request(unexpected=True), request(source_count=True), request(source_count=-1),
            request(deliverable="unknown"), request(claim_strength="unknown"),
            {"schema": "rigor-request-v1"}, request(schema="wrong"),
            request(synthesis=1), request(requested_tier="highest"),
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                classify_rigor(value)

    def test_cli_success_and_invalid_exit(self):
        good = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(request()),
                              text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)["tier"], "quick")
        bad = subprocess.run([sys.executable, str(SCRIPT)], input="{}", text=True,
                             capture_output=True, cwd=ROOT)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("error", json.loads(bad.stdout))
        nested = "[" * 100000 + "]" * 100000
        deeply_nested = subprocess.run([sys.executable, str(SCRIPT)], input=nested, text=True,
                                       capture_output=True, cwd=ROOT)
        self.assertEqual(deeply_nested.returncode, 2)
        self.assertIn("error", json.loads(deeply_nested.stdout))


if __name__ == "__main__":
    unittest.main()
