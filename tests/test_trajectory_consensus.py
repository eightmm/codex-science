import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from codex_science.trajectory_consensus import build_consensus, plan_comparisons

ROOT = Path(__file__).resolve().parents[1]


def trajectories(n=4):
    return [{"id": f"t{i}", "claims": [
        {"key": "  Shared   Claim ", "statement": "shared", "status": "supported" if i < 2 else "uncertain"},
        *([{"key": "half", "statement": "half", "status": "supported"}] if i < 2 else []),
        *([{"key": "rare", "statement": "rare", "status": "supported"}] if i == 0 else []),
    ]} for i in range(n)]


class ConsensusTests(unittest.TestCase):
    def test_majority_is_strict_and_status_disagreement_is_reported(self):
        result = build_consensus({"schema": "trajectory-set-v1", "trajectories": trajectories()})
        self.assertEqual([x["key"] for x in result["consensus_claims"]], ["shared claim"])
        shared = result["consensus_claims"][0]
        self.assertEqual(shared["support_fraction"], 1)
        self.assertTrue(shared["status_disagreement"])
        self.assertIn("half", [x["key"] for x in result["contested_claims"]])
        self.assertEqual(result["singleton_claims"][0]["key"], "rare")

    def test_bradley_terry_recovers_order_and_ties(self):
        comparisons = ([{"winner": "strong", "loser": "weak"}] * 20 +
                       [{"winner": "strong", "loser": "mid"}] * 15 +
                       [{"winner": "mid", "loser": "weak"}] * 12 +
                       [{"winner": "weak", "loser": "strong"}] * 2)
        ranking = build_consensus({"schema": "trajectory-set-v1", "trajectories": trajectories(),
                                   "comparisons": comparisons})["bradley_terry"]["ranking"]
        self.assertEqual([x["candidate_id"] for x in ranking], ["strong", "mid", "weak"])
        tied = build_consensus({"schema": "trajectory-set-v1", "trajectories": trajectories(),
                                "comparisons": [{"winner": "a", "loser": "b"},
                                                {"winner": "b", "loser": "a"}]})["bradley_terry"]["ranking"]
        self.assertAlmostEqual(tied[0]["score"], tied[1]["score"])

    def test_zero_win_candidates_and_cli_do_not_crash(self):
        payload = {"schema": "trajectory-set-v1", "trajectories": trajectories(),
                   "comparisons": [{"winner": "a", "loser": "b"},
                                   {"winner": "a", "loser": "c"}]}
        bt = build_consensus(payload)["bradley_terry"]
        self.assertEqual([x["candidate_id"] for x in bt["ranking"]], ["a", "b", "c"])
        self.assertFalse(bt["converged"])
        self.assertEqual(bt["iterations"], 10_000)
        self.assertIn({"code": "not_strongly_connected", "component": ["a", "b", "c"]}, bt["warnings"])
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        script = ROOT / "scripts" / "rank_trajectories.py"
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input=json.dumps(payload),
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["bradley_terry"]["ranking"][0]["candidate_id"], "a")

    def test_cli_converts_arithmetic_errors_to_json(self):
        script = ROOT / "scripts" / "rank_trajectories.py"
        spec = importlib.util.spec_from_file_location("rank_trajectories_cli", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with patch.object(module, "build_consensus", side_effect=ZeroDivisionError("fit failed")), \
                patch.object(sys, "stdin", io.StringIO("{}")), \
                patch.object(sys, "argv", [str(script), "--input", "-"]), \
                redirect_stdout(output):
            code = module.main()
        self.assertEqual(code, 2)
        error = json.loads(output.getvalue())
        self.assertEqual(error["schema"], "trajectory-consensus-error-v1")
        self.assertEqual(error["error"]["code"], "invalid_request")

    def test_chain_has_no_finite_mle_and_reports_iteration_cap(self):
        bt = build_consensus({"schema": "trajectory-set-v1", "trajectories": trajectories(),
                              "comparisons": [{"winner": "a", "loser": "b"},
                                              {"winner": "b", "loser": "c"}]})["bradley_terry"]
        self.assertEqual([x["candidate_id"] for x in bt["ranking"]], ["a", "b", "c"])
        self.assertIn({"code": "not_strongly_connected", "component": ["a", "b", "c"]}, bt["warnings"])
        self.assertIn({"code": "iteration_cap_reached", "limit": 10_000}, bt["warnings"])
        self.assertFalse(bt["converged"])
        self.assertEqual(bt["iterations"], 10_000)

    def test_disconnected_graph_does_not_rank_across_components(self):
        result = build_consensus({"schema": "trajectory-set-v1", "trajectories": trajectories(),
                                  "comparisons": [{"winner": "a", "loser": "b"},
                                                  {"winner": "c", "loser": "d"}]})["bradley_terry"]
        self.assertIsNone(result["ranking"])
        self.assertEqual(result["disconnected_components"], [["a", "b"], ["c", "d"]])

    def test_comparison_planning(self):
        self.assertEqual(len(plan_comparisons(list("abc"))), 3)
        self.assertEqual(len(plan_comparisons([str(i) for i in range(26)])), 300)
        self.assertEqual(plan_comparisons([str(i) for i in range(26)]),
                         plan_comparisons([str(i) for i in range(26)]))

    def test_validation_and_cli_from_foreign_cwd(self):
        with self.assertRaises(ValueError):
            build_consensus({"schema": "trajectory-set-v1", "trajectories": [], "min_support_fraction": 0.5})
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        script = ROOT / "scripts" / "rank_trajectories.py"
        payload = json.dumps({"schema": "trajectory-set-v1", "trajectories": trajectories()})
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input=payload,
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["schema"], "trajectory-consensus-v1")
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input="{",
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["schema"], "trajectory-consensus-error-v1")

    def test_singletons_status_normalization_and_statement_choice(self):
        result = build_consensus({"schema": "trajectory-set-v1", "trajectories": [
            {"id": "z", "claims": [{"key": "Claim", "statement": "late", "status": "Supported"}]},
            {"id": "a", "claims": [{"key": " claim ", "statement": "early", "status": "supported"}]},
        ]})
        self.assertEqual(len(result["consensus_claims"]), 1)
        self.assertEqual(result["contested_claims"], [])
        self.assertEqual(result["singleton_claims"], [])
        item = result["consensus_claims"][0]
        self.assertEqual(item["key"], "claim")
        self.assertEqual(item["statement"], "early")
        self.assertEqual(item["statuses"], {"supported": ["a", "z"]})

        only = build_consensus({"schema": "trajectory-set-v1", "trajectories": [
            {"id": "one", "claims": [{"key": "claim", "statement": "text", "status": "Supported"}]},
        ]})
        self.assertEqual(only["consensus_claims"], [])
        self.assertEqual(only["contested_claims"], [])
        self.assertEqual([x["key"] for x in only["singleton_claims"]], ["claim"])


if __name__ == "__main__":
    unittest.main()
