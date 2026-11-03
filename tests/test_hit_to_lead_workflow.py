from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.lead_optimization import analyze_hit_to_lead
from codex_science.virtual_screening import fingerprint

ROOT = Path(__file__).resolve().parents[1]


class HitToLeadTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/hit-to-lead-optimization/input.json").read_text())

    def freeze(self):
        self.data["contract_sha256"] = fingerprint(self.data["contract"])

    def test_supplied_property_selection_and_full_denominator(self):
        result = analyze_hit_to_lead(self.data)
        self.assertEqual(result, json.loads((ROOT / "examples/hit-to-lead-optimization/expected.json").read_text()))
        self.assertEqual(result["candidate_count"], 4)
        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual({r["id"] for r in result["proposal"]["selected"]}, {"a", "c"})
        self.assertFalse(result["engine_executed"])

    def test_failed_or_absent_controls_stop_proposal(self):
        for controls in ([], [{"id": "failed", "passed": False}]):
            self.data["controls"] = controls
            result = analyze_hit_to_lead(self.data)
            self.assertIsNone(result["proposal"])
            self.assertEqual(len(result["candidates"]), 4)

    def test_endpoint_identity_cannot_mix(self):
        for key in ("unit", "assay_id", "source_kind"):
            data = copy.deepcopy(self.data)
            data["candidates"][1]["properties"]["potency"][key] = "different"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "endpoint identity"):
                analyze_hit_to_lead(data)

    def test_missing_and_unknown_overlap_remain_excluded(self):
        self.data["candidates"][1]["properties"]["potency"] = None
        self.data["candidates"][3]["training_overlap"] = "unknown"
        result = analyze_hit_to_lead(self.data)
        self.assertEqual(result["eligible_count"], 0)
        self.assertIsNone(result["proposal"])
        self.assertIn("missing-potency", result["candidates"][1]["exclusion_reasons"])

    def test_scaffold_reuse_allowed_prospectively_but_not_held_out_evaluation(self):
        self.assertEqual(analyze_hit_to_lead(self.data)["eligible_count"], 2)
        self.data["contract"]["selection_context"] = "held_out_evaluation"
        self.freeze()
        with self.assertRaisesRegex(ValueError, "scaffold leakage"):
            analyze_hit_to_lead(self.data)

    def test_duplicate_identity_wrong_parent_cycle_and_target(self):
        mutations = [lambda d: d["candidates"].append(copy.deepcopy(d["candidates"][0])),
                     lambda d: d["candidates"][1].update(parent_id="absent"),
                     lambda d: d["candidates"][0].update(parent_id="a"),
                     lambda d: d["candidates"][1].update(target_id="wrong"),
                     lambda d: d["candidates"][1].update(chemical_identity=d["candidates"][0]["chemical_identity"])]
        for mutate in mutations:
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(ValueError):
                analyze_hit_to_lead(data)

    def test_stale_and_nonfinite_values(self):
        self.data["contract"]["decision"] = "changed"
        with self.assertRaisesRegex(ValueError, "hash"):
            analyze_hit_to_lead(self.data)
        self.freeze()
        for value in (float("nan"), float("inf"), True, 10**1000):
            self.data["candidates"][1]["properties"]["potency"]["value"] = value
            with self.assertRaises(ValueError):
                analyze_hit_to_lead(self.data)

    def test_diversity_and_budget_reach_existing_planner(self):
        self.data["candidates"][3]["scaffold_group"] = "series-A"
        self.data["contract"]["selection"]["budget"] = 1
        self.freeze()
        result = analyze_hit_to_lead(self.data)
        self.assertEqual(result["proposal"]["selected_count"], 1)
        self.assertLessEqual(result["proposal"]["total_cost"], 1)

    def test_objective_weights_control_selection_and_bad_policy_rejected_even_without_controls(self):
        self.data["contract"]["selection"]["budget"] = 1
        self.data["contract"]["objectives"][0]["weight"] = 0
        self.freeze()
        result = analyze_hit_to_lead(self.data)
        self.assertEqual(result["proposal"]["selected"][0]["id"], "c")
        self.data["controls"] = []
        self.data["contract"]["selection"]["batch_size"] = True
        self.freeze()
        with self.assertRaisesRegex(ValueError, "batch_size"):
            analyze_hit_to_lead(self.data)

    def test_nonfinite_unknown_metadata_is_rejected_by_api_and_cli(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            self.data["candidates"][0]["extra"] = {"measurement": value}
            with self.assertRaises(ValueError):
                analyze_hit_to_lead(self.data)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "bad.json"
                path.write_text(json.dumps(self.data))
                result = subprocess.run([sys.executable, str(ROOT / "scripts/analyze_hit_to_lead.py"), str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("nonfinite JSON", json.loads(result.stdout)["error"])
                self.assertFalse(result.stderr)

    def test_input_unchanged_and_cli_foreign_cwd_duplicate_keys(self):
        original = copy.deepcopy(self.data)
        analyze_hit_to_lead(self.data)
        self.assertEqual(self.data, original)
        with tempfile.TemporaryDirectory() as temporary:
            script = ROOT / "scripts/analyze_hit_to_lead.py"
            result = subprocess.run([sys.executable, str(script), str(ROOT / "examples/hit-to-lead-optimization/input.json")], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["eligible_count"], 2)
            path = Path(temporary) / "bad.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            result = subprocess.run([sys.executable, str(script), str(path)], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate JSON key", json.loads(result.stdout)["error"])
            self.assertFalse(result.stderr)
