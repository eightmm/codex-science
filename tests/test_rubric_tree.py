from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.rubric_tree import grade, validate_tree


def leaf(ident, weight=1, check=None):
    return {"id": ident, "title": ident, "weight": weight,
            "check": check or {"kind": "criterion", "criterion_id": ident}}


class RubricTreeTests(unittest.TestCase):
    def test_nested_weighting_and_manual_exclusion(self):
        tree = {"schema": "rubric-tree-v1", "id": "r", "root": {
            "id": "root", "title": "Root", "weight": 1, "children": [
                {"id": "group", "title": "Group", "weight": 3, "children": [leaf("a", 1), leaf("b", 3)]},
                leaf("manual", 1, {"kind": "manual"})]}}
        result = grade(tree, {"a": True, "b": False})
        self.assertEqual(result["score"], 0.25)
        self.assertEqual(result["per_node_scores"]["group"], 0.25)
        self.assertEqual(result["ungraded_ids"], ["manual"])
        self.assertIn("evidence_boundary", result)

    def test_missing_criterion_counts_as_fail(self):
        result = grade({"schema": "rubric-tree-v1", "id": "r", "root": leaf("x")}, {})
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(result["missing_criterion_ids"], ["x"])

    def test_review_pass_fail_and_escape(self):
        tree = {"schema": "rubric-tree-v1", "id": "r", "root": leaf("review", check={"kind": "review", "verdict_path": "receipt.json"})}
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            run = parent / "run"
            run.mkdir()
            (run / "receipt.json").write_text('{"verdict":"passed"}')
            self.assertEqual(grade(tree, {}, run)["score"], 1.0)
            (run / "receipt.json").write_text('{"verdict":"failed"}')
            self.assertEqual(grade(tree, {}, run)["score"], 0.0)
            outside = parent / "outside-rubric.json"
            outside.write_text('{"verdict":"passed"}')
            (run / "escape.json").symlink_to(outside)
            tree["root"]["check"]["verdict_path"] = "escape.json"
            with self.assertRaises(ValueError):
                grade(tree, {}, run)
            tree["root"]["check"]["verdict_path"] = "../outside-rubric.json"
            with self.assertRaises(ValueError):
                grade(tree, {}, parent / "missing-run")
            tree["root"]["check"]["verdict_path"] = "nonregular"
            (run / "nonregular").mkdir()
            with self.assertRaises(ValueError):
                grade(tree, {}, run)
            tree["root"]["check"]["verdict_path"] = "oversized.json"
            (run / "oversized.json").write_bytes(b"x" * (1_000_001))
            with self.assertRaises(ValueError):
                grade(tree, {}, run)

    def test_missing_review_evidence_is_reported(self):
        tree = {"schema": "rubric-tree-v1", "id": "r", "root": leaf(
            "review", check={"kind": "review", "verdict_path": "nested/receipt.json"})}
        expected = [{"node_id": "review", "path": "nested/receipt.json"}]
        no_run = grade(tree, {})
        self.assertEqual(no_run["score"], 0.0)
        self.assertEqual(no_run["missing_review_paths"], expected)
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "nested").mkdir()
            missing = grade(tree, {}, run)
            self.assertEqual(missing["score"], 0.0)
            self.assertEqual(missing["missing_review_paths"], expected)

    def test_validation_errors(self):
        base = {"schema": "rubric-tree-v1", "id": "r", "root": leaf("x")}
        duplicate = {**base, "root": {"id": "g", "title": "g", "weight": 1,
                                      "children": [leaf("x"), leaf("x")]}}
        for tree in (duplicate, {**base, "root": leaf("x", 0)},
                     {**base, "root": leaf("x", float("nan"))},
                     {**base, "root": leaf("x", 10 ** 400)}):
            with self.assertRaises(ValueError):
                validate_tree(tree)
        node = leaf("deep")
        for index in range(8):
            node = {"id": f"g{index}", "title": "g", "weight": 1, "children": [node]}
        with self.assertRaises(ValueError):
            validate_tree({"schema": "rubric-tree-v1", "id": "r", "root": node})

    def test_non_finite_sibling_weight_sum_is_rejected(self):
        tree = {"schema": "rubric-tree-v1", "id": "r", "root": {
            "id": "root", "title": "Root", "weight": 1, "children": [
                leaf("a", 1e308), leaf("b", 1e308)]}}
        with self.assertRaises(ValueError):
            grade(tree, {"a": True, "b": True})

    def test_deterministic_output(self):
        tree = {"schema": "rubric-tree-v1", "id": "r", "root": {"id": "g", "title": "g", "weight": 1,
                "children": [leaf("z"), leaf("a")]}}
        self.assertEqual(grade(tree, {"z": True, "a": False}), grade(tree, {"a": False, "z": True}))

    def test_cli_from_temp_cwd_and_error_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rubric = tmp_path / "rubric.json"
            results = tmp_path / "results.json"
            rubric.write_text(json.dumps({"schema": "rubric-tree-v1", "id": "r", "root": leaf("x")}))
            results.write_text('{"x":true}')
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            command = [sys.executable, str(ROOT / "scripts/grade_rubric.py"), "--rubric", str(rubric), "--results", str(results)]
            good = subprocess.run(command, cwd=tmp, env=env, text=True, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)["score"], 1.0)
            stdin_results = subprocess.run(
                [sys.executable, str(ROOT / "scripts/grade_rubric.py"), "--rubric", str(rubric), "--results", "-"],
                cwd=tmp, env=env, input='{"x":true}', text=True, capture_output=True)
            self.assertEqual(stdin_results.returncode, 0, stdin_results.stderr)
            self.assertEqual(json.loads(stdin_results.stdout)["score"], 1.0)
            stdin_rubric = subprocess.run(
                [sys.executable, str(ROOT / "scripts/grade_rubric.py"), "--rubric", "-", "--results", str(results)],
                cwd=tmp, env=env,
                input=json.dumps({"schema": "rubric-tree-v1", "id": "r", "root": leaf("x")}),
                text=True, capture_output=True)
            self.assertEqual(stdin_rubric.returncode, 0, stdin_rubric.stderr)
            self.assertEqual(json.loads(stdin_rubric.stdout)["score"], 1.0)
            both_stdin = subprocess.run(
                [sys.executable, str(ROOT / "scripts/grade_rubric.py"), "--rubric", "-", "--results", "-"],
                cwd=tmp, env=env, input="", text=True, capture_output=True)
            self.assertEqual(both_stdin.returncode, 2)
            self.assertIn("at most one", json.loads(both_stdin.stdout)["error"]["message"])
            rubric.write_text("{")
            bad = subprocess.run(command, cwd=tmp, env=env, text=True, capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(json.loads(bad.stdout)["schema"], "rubric-score-error-v1")


if __name__ == "__main__":
    unittest.main()
