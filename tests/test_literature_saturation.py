import io
import json
import math
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_cli_bounds_file_and_stdin_reads(self):
        command = runpy.run_path(str(ROOT / "scripts/estimate_saturation.py"))
        limit = 128
        valid = '[{"evaluated":30,"relevant":10}]'

        class BoundedInput(io.StringIO):
            def read(stream, size=-1):
                self.assertGreater(size, 0, "stdin must use a bounded read")
                self.assertLessEqual(size, limit + 1)
                return super().read(size)

        wide_prefix = '{"checkpoints":[],"extra":"'
        wide = wide_prefix + "é" * (limit - len(wide_prefix) - 2) + '"}'
        cases = (("", 2, 2), ("0", 2, 2), ("{", 2, 2), (valid, 0, 0),
                 (valid + " " * (limit - len(valid)), 0, 0),
                 (valid + " " * (limit + 1 - len(valid)), 2, 2),
                 (valid + " " * (limit * 4), 2, 2),
                 (valid + "é" * limit, 2, 2), (valid + "\r\n" * limit, 2, 2),
                 (b"\xff", 2, 2), (wide, 2, 0), (wide + " ", 2, 2),
                 ('[' * 1100 + '0' + ']' * 1100, 2, 2))
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "input.json"
            output = Path(tempdir) / "output.json"
            for raw, file_status, stdin_status in cases:
                for from_stdin in (False, True):
                    with self.subTest(length=len(raw), stdin=from_stdin):
                        encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
                        source.write_bytes(encoded)
                        output.write_text("keep")
                        stdout = io.StringIO()
                        stdin = BoundedInput(raw if isinstance(raw, str) else "\udcff")
                        expected = stdin_status if from_stdin else file_status
                        argv = ["estimate_saturation.py", "--input",
                                "-" if from_stdin else str(source), "--hard-cap", "500",
                                "--output", str(output)]
                        with patch.dict(command["main"].__globals__, DEFAULT_MAX_JSON_BYTES=limit), \
                                patch("sys.argv", argv), patch("sys.stdin", stdin), \
                                patch("sys.stdout", stdout):
                            status = command["main"]()
                        self.assertEqual(expected, status, stdout.getvalue())
                        result = json.loads(stdout.getvalue())
                        if expected:
                            self.assertEqual("invalid_request", result["error"]["code"])
                            self.assertEqual("keep", output.read_text())
                            size = len(stdin.getvalue()) if from_stdin else len(encoded)
                            if size > limit:
                                unit = "characters" if from_stdin else "bytes"
                                self.assertIn(f"exceeds {limit} {unit}", result["error"]["message"])
                        else:
                            self.assertEqual(json.loads(output.read_text()), result)

            raw_metadata = b'{"checkpoints":[],"hard_cap":500,"extra":"\xff"}\r\n'
            expected_output = json.dumps(estimate_saturation([], hard_cap=500), sort_keys=True) + "\n"
            reference = """\
import json, sys
from codex_science.literature_saturation import estimate_saturation
try:
    params = json.loads(sys.stdin.read())
    result = estimate_saturation(params["checkpoints"], hard_cap=params["hard_cap"])
except (OSError, UnicodeError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
    print(json.dumps({"schema": "saturation-estimate-error-v1",
                      "error": {"code": "invalid_request", "message": str(error)}}, sort_keys=True))
    raise SystemExit(2)
print(json.dumps(result, sort_keys=True))
"""
            locale = os.environ.get("LC_ALL", "C.UTF-8")
            if locale not in ("C", "C.UTF-8"):
                locale = "C.UTF-8"
            for setting in (None, "utf-8:strict", "utf-8:surrogateescape", "latin-1:strict",
                            "utf-8:replace", "utf-8:ignore", "utf-16:strict", "utf-32:strict"):
                env = dict(os.environ, LC_ALL=locale, LANG=locale,
                           PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
                env.pop("PYTHONIOENCODING", None)
                if setting is not None:
                    env["PYTHONIOENCODING"] = setting
                with self.subTest(stdin_encoding=setting):
                    configuration = subprocess.run(
                        [sys.executable, "-c", "import json,sys; print(json.dumps([sys.stdin.encoding,sys.stdin.errors,sys.stdout.encoding]))"],
                        capture_output=True, env=env,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                    self.assertEqual(0, configuration.returncode, configuration.stderr)
                    encoding, errors, output_encoding = json.loads(configuration.stdout)
                    payload = (raw_metadata.decode("latin-1").encode(encoding)
                               if setting in ("utf-16:strict", "utf-32:strict") else raw_metadata)
                    try:
                        payload.decode(encoding, errors)
                    except UnicodeError:
                        expected_exit = 2
                    else:
                        expected_exit = 0
                    native = subprocess.run(
                        [sys.executable, "-c", reference],
                        input=payload, capture_output=True, env=env,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                    self.assertEqual(expected_exit, native.returncode, native.stderr)
                    completed = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/estimate_saturation.py"), "--input", "-"],
                        input=payload, capture_output=True, env=env,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                    self.assertEqual(native.returncode, completed.returncode, completed.stdout)
                    self.assertEqual(native.stdout, completed.stdout)
                    if not expected_exit:
                        self.assertEqual(expected_output, completed.stdout.decode(output_encoding))
                    source.write_bytes(raw_metadata)
                    completed = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/estimate_saturation.py"), "--input", str(source)],
                        capture_output=True, env=env,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                    self.assertEqual(2, completed.returncode)
                    self.assertEqual("invalid_request", json.loads(completed.stdout)["error"]["code"])
            stdout = io.StringIO()
            with patch("sys.argv", ["estimate_saturation.py", "--input", "-"]), \
                    patch.dict(command["main"].__globals__, DEFAULT_MAX_JSON_BYTES=limit), \
                    patch("sys.stdin", BoundedInput(raw_metadata.decode("utf-8", "surrogateescape"))), \
                    patch("sys.stdout", stdout):
                self.assertEqual(0, command["main"]())
            self.assertEqual(expected_output, stdout.getvalue())

            source.write_bytes(b'\r\n{}0')
            stdout = io.StringIO()
            with self.assertRaises(ValueError) as native_error:
                json.loads(source.read_text(encoding="utf-8"))
            with patch("sys.argv", ["estimate_saturation.py", "--input", str(source)]), \
                    patch("sys.stdout", stdout):
                self.assertEqual(2, command["main"]())
            self.assertEqual(str(native_error.exception), json.loads(stdout.getvalue())["error"]["message"])

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
