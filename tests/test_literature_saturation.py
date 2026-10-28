import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.literature_saturation import estimate_saturation

ROOT = Path(__file__).resolve().parents[1]


def curve(tau=80, total=30):
    return [{"evaluated": n, "relevant": round(total * (1 - math.exp(-n / tau)))}
            for n in (20, 40, 80, 160, 240, 320)]


class SaturationTests(unittest.TestCase):
    def test_fit_and_recommendations(self):
        result = estimate_saturation(curve(), hard_cap=500, remaining_threshold=4)
        self.assertLess(abs(result["tau"] - 80) / 80, .1)
        self.assertEqual(result["recommendation"], "stop_saturated")
        self.assertEqual(estimate_saturation(curve(), hard_cap=240)["recommendation"], "stop_hard_cap")

    def test_insufficient_and_linear(self):
        self.assertEqual(estimate_saturation(curve()[:2], hard_cap=500)["recommendation"], "insufficient_data")
        capped = estimate_saturation(curve()[:2], hard_cap=40)
        self.assertEqual(capped["recommendation"], "stop_hard_cap")
        self.assertIn("hard_cap_reached", capped["reasons"])
        linear = [{"evaluated": n, "relevant": n // 2} for n in (10, 20, 30, 40)]
        result = estimate_saturation(linear, hard_cap=100)
        self.assertEqual(result["recommendation"], "continue")
        self.assertIn("no_saturation_signal", result["reasons"])

    def test_uneven_spacing_and_plateau_are_not_linear(self):
        plateau = [{"evaluated": n, "relevant": 15} for n in (40, 80, 120, 160)]
        plateau_result = estimate_saturation(plateau, hard_cap=500, remaining_threshold=1)
        self.assertNotIn("no_saturation_signal", plateau_result["reasons"])
        self.assertTrue(plateau_result["recommendation"] == "stop_saturated" or
                        plateau_result["predicted_remaining"] < 1)

        uneven = [{"evaluated": n, "relevant": r} for n, r in ((20, 10), (40, 15), (80, 20), (160, 25))]
        uneven_result = estimate_saturation(uneven, hard_cap=500)
        self.assertNotIn("no_saturation_signal", uneven_result["reasons"])

    def test_underestimated_fit_cannot_claim_saturation_or_recall_over_one(self):
        points = [{"evaluated": n, "relevant": r}
                  for n, r in ((30, 10), (60, 10), (90, 10), (120, 11))]
        result = estimate_saturation(points, hard_cap=1000)
        self.assertEqual(result["recommendation"], "continue")
        self.assertIn("fit_underestimates_found", result["reasons"])
        self.assertGreaterEqual(result["total_relevant_estimate"], result["found"])
        self.assertLessEqual(result["expected_recall"], 1)

    def test_tau_search_bound_cannot_claim_saturation(self):
        points = [{"evaluated": n, "relevant": 10} for n in (30, 60, 90)]
        result = estimate_saturation(points, hard_cap=1000)
        self.assertEqual(result["recommendation"], "continue")
        self.assertIn("tau_at_search_bound", result["reasons"])

    def test_validation_and_determinism(self):
        for bad in (
            [{"evaluated": 10, "relevant": 1}, {"evaluated": 9, "relevant": 1}, {"evaluated": 20, "relevant": 2}],
            [{"evaluated": 10, "relevant": 11}, {"evaluated": 20, "relevant": 12}, {"evaluated": 30, "relevant": 13}],
            [{"evaluated": True, "relevant": 1}, {"evaluated": 20, "relevant": 2}, {"evaluated": 30, "relevant": 3}],
            [{"evaluated": 10, "relevant": -1}, {"evaluated": 20, "relevant": 2}, {"evaluated": 30, "relevant": 3}],
            [{"evaluated": 30, "relevant": 10}, {"evaluated": 30, "relevant": 11}, {"evaluated": 50, "relevant": 12}],
            [{"evaluated": 30, "relevant": 10}, {"evaluated": 60, "relevant": 10}, {"evaluated": 10**9 + 1, "relevant": 11}],
        ):
            with self.assertRaises(ValueError):
                estimate_saturation(bad, hard_cap=100)
        self.assertEqual(estimate_saturation(curve(), hard_cap=500), estimate_saturation(curve(), hard_cap=500))

    def test_repeated_checkpoints_do_not_supply_fit_points(self):
        points = [{"evaluated": n, "relevant": r}
                  for n, r in ((10, 10), (30, 15), (30, 15))]
        for log in ([], points[:1] * 3, points):
            with self.subTest(log=log):
                result = estimate_saturation(log, hard_cap=1000, min_evaluated=0)
                self.assertEqual(result["recommendation"], "insufficient_data")
                self.assertEqual(result["reasons"], ["fewer_than_three_points"])
                self.assertIsNone(result["expected_recall"])
        capped = estimate_saturation(points, hard_cap=30)
        self.assertEqual(capped["recommendation"], "stop_hard_cap")
        self.assertIn("fewer_than_three_points", capped["reasons"])

    def test_repeated_checkpoints_do_not_reweight_the_fit(self):
        points = curve()
        original = [dict(point) for point in points]
        repeated = [point for i, point in enumerate(points) for _ in range(i + 1)]
        self.assertEqual(estimate_saturation(points, hard_cap=500),
                         estimate_saturation(repeated, hard_cap=500))
        self.assertEqual(points, original)

    def test_relevant_increment_cannot_exceed_evaluated_increment(self):
        for pairs in (((50, 40), (51, 50), (100, 50)),
                      ((50, 40), (50, 41)), ((50, 40), (51, 42)),
                      ((50, 40), (51.0, 41)), ((0, 0),)):
            with self.subTest(pairs=pairs):
                points = [{"evaluated": n, "relevant": r} for n, r in pairs]
                with self.assertRaisesRegex(ValueError, "invalid or decreasing cumulative checkpoint"):
                    estimate_saturation(points, hard_cap=50)
        for relevant in (40, 41):
            with self.subTest(relevant=relevant):
                points = [{"evaluated": n, "relevant": r}
                          for n, r in ((50, 40), (51, relevant), (100, relevant))]
                result = estimate_saturation(points, hard_cap=1000)
                self.assertEqual(result["found"], relevant)
                self.assertNotIn("fewer_than_three_points", result["reasons"])

    def test_cli_checkpoint_validity_preserves_existing_output_on_refusal(self):
        script = ROOT / "scripts" / "estimate_saturation.py"
        cases = ((((10, 10), (30, 15), (30, 15)), 0),
                 (((50, 40), (51, 50), (100, 50)), 2))
        with tempfile.TemporaryDirectory() as cwd:
            target = Path(cwd) / "estimate.json"
            for pairs, status in cases:
                with self.subTest(pairs=pairs):
                    target.write_text("keep", encoding="utf-8")
                    payload = {"hard_cap": 1000, "checkpoints": [
                        {"evaluated": n, "relevant": r} for n, r in pairs]}
                    proc = subprocess.run(
                        [sys.executable, str(script), "--input", "-", "--output", str(target)],
                        input=json.dumps(payload), text=True, capture_output=True, cwd=cwd)
                    self.assertEqual(proc.returncode, status, proc.stderr)
                    result = json.loads(proc.stdout)
                    if status:
                        self.assertEqual(result["schema"], "saturation-estimate-error-v1")
                        self.assertEqual(result["error"], {
                            "code": "invalid_request",
                            "message": "invalid or decreasing cumulative checkpoint"})
                        self.assertEqual(target.read_text(encoding="utf-8"), "keep")
                    else:
                        self.assertEqual(result["recommendation"], "insufficient_data")
                        self.assertIsNone(result["expected_recall"])
                        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), result)

    def test_cli(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        payload = json.dumps({"schema": "saturation-log-v1", "hard_cap": 500, "checkpoints": curve()})
        script = ROOT / "scripts" / "estimate_saturation.py"
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input=payload,
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["schema"], "saturation-estimate-v1")
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input="{",
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 2)
        error = json.loads(proc.stdout)
        self.assertEqual(error["schema"], "saturation-estimate-error-v1")
        self.assertEqual(error["error"]["code"], "invalid_request")
        self.assertIn("message", error["error"])

    def test_cli_output_file(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        payload = json.dumps({"schema": "saturation-log-v1", "hard_cap": 500, "checkpoints": curve()})
        script = ROOT / "scripts" / "estimate_saturation.py"
        with tempfile.TemporaryDirectory() as cwd:
            target = Path(cwd) / "sub" / "out.json"
            proc = subprocess.run([sys.executable, str(script), "--input", "-", "--output", str(target)],
                                  input=payload, text=True, capture_output=True, env=env, cwd=cwd)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), json.loads(proc.stdout))
            target.write_text("keep", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(script), "--input", "-", "--output", str(target)],
                                  input="{", text=True, capture_output=True, env=env, cwd=cwd)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["error"]["code"], "invalid_request")
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            proc = subprocess.run([sys.executable, str(script), "--input", "-", "--output", cwd],
                                  input=payload, text=True, capture_output=True, env=env, cwd=cwd)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stdout)["error"]["code"], "output_write_failed")

    def test_cli_rejects_absurd_evaluated_count(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        huge = 10**305
        payload = json.dumps({"schema": "saturation-log-v1", "hard_cap": 2 * huge,
                              "checkpoints": [{"evaluated": n, "relevant": r}
                                              for n, r in ((30, 10), (60, 10), (huge, 11))]})
        script = ROOT / "scripts" / "estimate_saturation.py"
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, str(script), "--input", "-"], input=payload,
                                  text=True, capture_output=True, env=env, cwd=cwd)
        self.assertEqual(proc.returncode, 2)
        error = json.loads(proc.stdout)
        self.assertEqual(error["schema"], "saturation-estimate-error-v1")
        self.assertEqual(error["error"]["code"], "invalid_request")

    def test_skill_guidance(self):
        with open(ROOT / "authored-skills/literature-review/SKILL.md", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("estimate_saturation.py", text)
        self.assertIn("complete recall", text)
        self.assertIn('"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/estimate_saturation.py"', text)
        self.assertIn("--hard-cap N", text)
        for key in ('schema="saturation-log-v1"', "checkpoints", "evaluated", "relevant",
                    "remaining_threshold", "min_evaluated"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
