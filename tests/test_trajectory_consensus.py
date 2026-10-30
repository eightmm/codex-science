import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from codex_science import trajectory_consensus
from codex_science.trajectory_consensus import build_consensus, plan_comparisons

ROOT = Path(__file__).resolve().parents[1]


def trajectories(n=4):
    return [{"id": f"t{i}", "claims": [
        {"key": "  Shared   Claim ", "statement": "shared", "status": "supported" if i < 2 else "uncertain"},
        *([{"key": "half", "statement": "half", "status": "supported"}] if i < 2 else []),
        *([{"key": "rare", "statement": "rare", "status": "supported"}] if i == 0 else []),
    ]} for i in range(n)]


def dense_rank_reference(comparisons):
    """Original dense MM loop, retained as an exact regression oracle."""
    ids = sorted({item["winner"] for item in comparisons} | {item["loser"] for item in comparisons})
    wins = {candidate: {other: 0 for other in ids if other != candidate} for candidate in ids}
    for item in comparisons:
        wins[item["winner"]][item["loser"]] += 1
    components = trajectory_consensus._components(ids, wins)
    warnings = [{"code": "not_strongly_connected", "component": component}
                for component in components if not trajectory_consensus._strongly_connected(component, wins)]
    result = {"candidates": [], "disconnected_components": components if len(components) > 1 else [],
              "warnings": warnings, "converged": False, "iterations": 0}
    for candidate in ids:
        result["candidates"].append({"candidate_id": candidate,
                                     "wins": sum(wins[candidate].values()),
                                     "losses": sum(wins[other][candidate] for other in ids if other != candidate)})
    if len(components) != 1:
        result["ranking"] = None
        return result
    has_mle = not warnings
    strengths = {candidate: 1.0 for candidate in ids}
    converged = False
    for iteration in range(1, trajectory_consensus._MAX_ITERATIONS + 1):
        updated = {}
        for candidate in ids:
            numerator = sum(wins[candidate].values())
            if numerator == 0:
                updated[candidate] = 0.0
                continue
            denominator = 0.0
            for other in ids:
                if other == candidate:
                    continue
                games = wins[candidate][other] + wins[other][candidate]
                if not games:
                    continue
                strength_sum = strengths[candidate] + strengths[other]
                if strength_sum == 0:
                    denominator = math.inf
                    break
                denominator += games / strength_sum
            updated[candidate] = numerator / denominator if denominator else strengths[candidate]
        scale = max(updated.values())
        scaled = {key: value / scale for key, value in updated.items()}
        normalizer = sum(scaled.values())
        updated = {key: value / normalizer for key, value in scaled.items()}
        delta = max(abs(updated[key] - strengths[key]) for key in ids)
        strengths = updated
        result["iterations"] = iteration
        if has_mle and delta < trajectory_consensus._TOLERANCE:
            converged = True
            break
    result["converged"] = converged
    if not converged and result["iterations"] == trajectory_consensus._MAX_ITERATIONS:
        result["warnings"].append({"code": "iteration_cap_reached", "limit": trajectory_consensus._MAX_ITERATIONS})
    result["ranking"] = [{"candidate_id": candidate, "score": strengths[candidate]}
                         for candidate in sorted(ids, key=lambda key: (-strengths[key], key))]
    return result


class ConsensusTests(unittest.TestCase):
    def test_sparse_disconnected_rank_uses_bounded_memory(self):
        size = 512
        comparisons = [{"winner": str(i), "loser": str(i + 1)} for i in range(0, size, 2)]
        tracemalloc.start()
        try:
            result = trajectory_consensus._rank(comparisons)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertIsNone(result["ranking"])
        self.assertEqual(size // 2, len(result["disconnected_components"]))
        self.assertLess(peak, size * 4096)

    def test_rank_matches_dense_reference(self):
        cases = [
            [{"winner": "a", "loser": "b"}, {"winner": "b", "loser": "c"},
             {"winner": "c", "loser": "a"}],
            [{"winner": "a", "loser": "b"}, {"winner": "b", "loser": "c"}],
            [{"winner": "a", "loser": "b"}, {"winner": "c", "loser": "d"}],
            ([{"winner": "a", "loser": "b"}] * 4 + [{"winner": "b", "loser": "a"}] * 4 +
             [{"winner": "a", "loser": "c"}] * 3 + [{"winner": "c", "loser": "a"}] * 2 +
             [{"winner": "b", "loser": "c"}] * 2 + [{"winner": "c", "loser": "b"}] * 3),
        ]
        for comparisons in cases:
            with self.subTest(comparisons=comparisons):
                self.assertEqual(trajectory_consensus._rank(comparisons), dense_rank_reference(comparisons))

    def test_200_candidate_chain_ranks_under_eight_seconds(self):
        comparisons = [{"winner": f"c{i:03d}", "loser": f"c{i + 1:03d}"} for i in range(199)]
        start = time.perf_counter()
        result = trajectory_consensus._rank(comparisons)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 8.0, f"200-candidate chain took {elapsed:.3f}s")
        self.assertEqual(result["iterations"], 10_000)
        self.assertIn({"code": "iteration_cap_reached", "limit": 10_000}, result["warnings"])

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
