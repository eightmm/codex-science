from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.virtual_screening import analyze_screening, fingerprint


ROOT = Path(__file__).resolve().parents[1]


class VirtualScreeningTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/virtual-screening-campaign/screening.json").read_text())

    def freeze(self):
        self.data["contract_sha256"] = fingerprint(self.data["contract"])

    def test_full_compound_aggregation_and_expected_artifact(self):
        result = analyze_screening(self.data)
        self.assertEqual(result, json.loads((ROOT / "examples/virtual-screening-campaign/expected.json").read_text()))
        self.assertEqual(result["acceptance"], "accepted_analysis")
        self.assertEqual(result["metrics"]["average_precision"], 1)
        self.assertEqual(result["metrics"]["enrichment_factor"], 2)
        self.assertEqual(result["denominators"]["planned_attempts"], 8)
        self.assertEqual(len(result["compounds"]), 4)
        self.assertEqual(result["compounds"][0]["score"], -8.9)
        self.assertFalse(result["engine_executed"])

    def test_direction_changes_admissible_result(self):
        self.data["contract"]["score_direction"] = "higher"
        self.freeze()
        result = analyze_screening(self.data)
        self.assertEqual(result["acceptance"], "inconclusive")
        self.assertEqual(result["metrics"]["enrichment_factor"], 0)

    def test_ties_are_order_independent_and_fractional(self):
        for result in self.data["results"]:
            result["score"] = 1
        result = analyze_screening(self.data)
        self.assertEqual(result["metrics"]["average_precision"], 0.5)
        self.assertEqual(result["metrics"]["enrichment_factor"], 1)
        self.data["compounds"].reverse()
        self.assertEqual(result["metrics"], analyze_screening(self.data)["metrics"])
        self.assertEqual(result["acceptance"], "inconclusive")

    def test_duplicate_and_wrong_parent_identities_rejected(self):
        for field, change in (("compounds", lambda rows: rows.append(copy.deepcopy(rows[0]))),
                              ("states", lambda rows: rows[0].update(compound_id="absent")),
                              ("planned_attempts", lambda rows: rows[0].update(state_id="absent")),
                              ("results", lambda rows: rows[0].update(id="unplanned"))):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                change(data[field])
                with self.assertRaises(ValueError):
                    analyze_screening(data)
        self.data["compounds"][1]["chemical_identity"] = self.data["compounds"][0]["chemical_identity"]
        with self.assertRaisesRegex(ValueError, "chemical identity"):
            analyze_screening(self.data)

    def test_leakage_and_target_mismatch_rejected(self):
        for mutation in (lambda d: d["compounds"][0].update(training_overlap="known"),
                         lambda d: d["compounds"][0].update(target_id="different"),
                         lambda d: (d["compounds"][0].update(partition="train"), d["compounds"][1].update(scaffold_group="scaffold-1")),
                         lambda d: d["contract"].update(pocket_source="held_out_pose")):
            data = copy.deepcopy(self.data)
            mutation(data)
            data["contract_sha256"] = fingerprint(data["contract"])
            with self.assertRaises(ValueError):
                analyze_screening(data)

    def test_result_lineage_and_score_endpoint_cannot_be_silently_replaced(self):
        for field in ("state_id", "compound_id", "target_id", "score_name"):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["results"][0][field] = "wrong"
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    analyze_screening(data)

    def test_failed_control_blocks_acceptance_without_erasing_metrics(self):
        self.data["controls"][0]["status"] = "failed"
        result = analyze_screening(self.data)
        self.assertEqual(result["metrics"]["average_precision"], 1)
        self.assertEqual(result["acceptance"], "inconclusive")
        self.assertEqual(result["controls"][0]["status"], "failed")

    def test_absent_controls_and_unknown_overlap_block_acceptance(self):
        self.data["controls"] = []
        self.data["compounds"][0]["training_overlap"] = "unknown"
        result = analyze_screening(self.data)
        self.assertEqual(result["acceptance"], "inconclusive")
        self.assertTrue(any("overlap" in reason for reason in result["reasons"]))

    def test_missing_and_failed_attempts_keep_denominator(self):
        self.data["results"].pop()
        self.data["results"][0] = {"id": self.data["results"][0]["id"], "status": "failed", "reason": "engine failed"}
        result = analyze_screening(self.data)
        self.assertEqual(len(result["attempts"]), 8)
        self.assertEqual(result["denominators"]["attempt_status"], {"ok": 6, "failed": 1, "missing": 1})
        self.assertEqual(result["acceptance"], "inconclusive")

    def test_no_labels_and_no_scores_are_unavailable(self):
        for row in self.data["compounds"]:
            row["active"] = None
        result = analyze_screening(self.data)
        self.assertEqual(result["metrics"]["status"], "unavailable")
        self.data["results"] = []
        result = analyze_screening(self.data)
        self.assertEqual(result["denominators"]["test_evaluable"], 0)
        self.assertEqual(result["denominators"]["attempt_status"], {"missing": 8})
        self.assertEqual(result["acceptance"], "inconclusive")

    def test_zero_survivors_does_not_filter_metric_denominator(self):
        self.data["contract"]["score_threshold"] = -100
        self.freeze()
        result = analyze_screening(self.data)
        self.assertEqual(result["denominators"]["test_retained"], 0)
        self.assertEqual(result["metrics"]["n"], 4)
        self.assertEqual(result["acceptance"], "inconclusive")

    def test_bad_scores_labels_status_and_stale_hash(self):
        for change in (lambda d: d["results"][0].update(score=float("nan")),
                       lambda d: d["results"][0].update(score=True),
                       lambda d: d["results"][0].update(status="failed"),
                       lambda d: d["compounds"][0].update(active="false"),
                       lambda d: d["contract"].update(top_k=9)):
            data = copy.deepcopy(self.data)
            change(data)
            with self.assertRaises(ValueError):
                analyze_screening(data)

    def test_input_not_mutated(self):
        old = copy.deepcopy(self.data)
        analyze_screening(self.data)
        self.assertEqual(self.data, old)

    def test_cli_json_only_foreign_cwd_and_duplicate_key_error(self):
        script = ROOT / "scripts/analyze_virtual_screening.py"
        with tempfile.TemporaryDirectory() as temporary:
            output = subprocess.run([sys.executable, str(script), str(ROOT / "examples/virtual-screening-campaign/screening.json")], cwd=temporary, text=True, capture_output=True)
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertFalse(output.stderr)
            self.assertEqual(json.loads(output.stdout)["acceptance"], "accepted_analysis")
            path = Path(temporary) / "bad.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            output = subprocess.run([sys.executable, str(script), str(path)], cwd=temporary, text=True, capture_output=True)
            self.assertEqual(output.returncode, 1)
            self.assertFalse(output.stderr)
            self.assertEqual(json.loads(output.stdout)["status"], "error")


if __name__ == "__main__":
    unittest.main()
