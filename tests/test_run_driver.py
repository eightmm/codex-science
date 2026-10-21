from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.checkpoints import (
    advance_checkpoint,
    block_checkpoint,
    complete_checkpoint,
    create_checkpoint,
    record_review,
    verify_criterion,
)
from codex_science.run_driver import _argv, _run_turn, _write_receipt, drive


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "drive_codex_run.py"
FAKE_CODE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time

if "--version" in sys.argv:
    print("codex-cli fake-1")
    raise SystemExit(0)
args = sys.argv[1:]
scenario = json.loads(pathlib.Path(os.environ["FAKE_PLAN"]).read_text())
counter = pathlib.Path(os.environ["FAKE_COUNTER"])
number = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(number))
step = scenario[min(number - 1, len(scenario) - 1)]
last = pathlib.Path(args[args.index("-o") + 1])
if os.environ.get("FAKE_ARG_LOG"):
    with pathlib.Path(os.environ["FAKE_ARG_LOG"]).open("a") as stream:
        stream.write(json.dumps(args) + "\n")
if os.environ.get("FAKE_LAST_OBSERVATIONS"):
    with pathlib.Path(os.environ["FAKE_LAST_OBSERVATIONS"]).open("a") as stream:
        stream.write(json.dumps({"number": number, "existed": last.exists()}) + "\n")
if step.get("sleep"):
    time.sleep(step["sleep"])
if step.get("interrupt_parent"):
    import signal
    os.kill(os.getppid(), signal.SIGINT)
    while True:
        time.sleep(0.05)

def make_run(name):
    from codex_science.checkpoints import create_checkpoint
    from pathlib import Path
    run = pathlib.Path(os.environ["FAKE_PROJECT"]) / "artifacts" / name
    if not (run / "checkpoint.json").exists():
        create_checkpoint(run, goal="fixture goal", deliverable="fixture result",
            done_criteria=["evidence is checked"], steps=[("s", "step")],
            next_action="continue", session_key=__import__("hashlib").sha256(name.encode()).hexdigest())
    return run

def action(item):
    kind, name = item["kind"], item.get("name", step.get("run_name", "drive-run"))
    run = pathlib.Path(os.environ["FAKE_PROJECT"]) / "artifacts" / name
    if kind == "invalid":
        run.mkdir(parents=True, exist_ok=True)
        (run / "checkpoint.json").write_text('{"schema_version":999}\n')
        return
    run = make_run(name)
    if kind == "blocked":
        from codex_science.checkpoints import block_checkpoint
        block_checkpoint(run, reason="needs repair", next_action="repair")
    elif kind == "abandon":
        from codex_science.checkpoints import abandon_checkpoint
        abandon_checkpoint(run, reason="stopped")
    elif kind == "waiting":
        from codex_science.checkpoints import wait_checkpoint
        wait_checkpoint(run, reason="external event", next_action="resume", poll_interval_seconds=5, terminal_rule="event")
    elif kind == "gate":
        from codex_science.checkpoints import request_decision
        request_decision(run, questions=["approve?"], reason="approval needed")
    elif kind in {"complete", "inconclusive"}:
        from codex_science.checkpoints import advance_checkpoint, complete_checkpoint, record_review, verify_criterion
        (run / "evidence.json").write_text('{"ok":true}\n')
        verify_criterion(run, "criterion-1", ["evidence.json"])
        advance_checkpoint(run, completed_step="s", next_step=None, next_action="finish")
        (run / "review.json").write_text('{"status":"passed","reviewer":"fixture","independent":true,"findings":[]}\n')
        record_review(run, artifact_ref="review.json")
        complete_checkpoint(run)
        if kind == "inconclusive":
            (run / "manifest.json").write_text('{"result":{"status":"inconclusive"}}\n')

for item in step.get("actions", []):
    action(item)
    if item.get("updated_at"):
        checkpoint_path = pathlib.Path(os.environ["FAKE_PROJECT"]) / "artifacts" / item.get("name", step.get("run_name", "drive-run")) / "checkpoint.json"
        record = json.loads(checkpoint_path.read_text())
        record["updated_at"] = item["updated_at"]
        checkpoint_path.write_text(json.dumps(record))
if step.get("action"):
    action({"kind": step["action"], "name": step.get("run_name", "drive-run")})
for artifact in step.get("artifacts", []):
    path = pathlib.Path(os.environ["FAKE_PROJECT"]) / "artifacts" / artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture artifact\n")
if "last" in step:
    last.write_text(step["last"])
if not step.get("omit_thread"):
    print(json.dumps({"type":"thread.started", "thread_id":step.get("thread_id", "fake-thread")}))
if step.get("terminal", "completed") == "failed":
    print(json.dumps({"type":"turn.failed", "error":{"message":"fixture failure"}}))
    raise SystemExit(step.get("exit_code", 1))
if step.get("terminal", "completed") == "interrupted":
    raise SystemExit(step.get("exit_code", 0))
usage = step.get("usage", {"input_tokens":10,"output_tokens":2})
print(json.dumps({"type":"turn.completed", "usage":usage}))
raise SystemExit(step.get("exit_code", 0))
'''


class RunDriverTests(unittest.TestCase):
    def _fake(self, root: Path, steps: list[dict]) -> tuple[Path, dict[str, str]]:
        binary = root / "fake-codex"
        binary.write_text(FAKE_CODE, encoding="utf-8")
        binary.chmod(0o755)
        plan = root / "plan.json"
        plan.write_text(json.dumps(steps), encoding="utf-8")
        env = dict(os.environ)
        env.update({"PYTHONPATH": str(ROOT / "src"), "FAKE_PLAN": str(plan),
                    "FAKE_COUNTER": str(root / "counter"), "FAKE_PROJECT": str(root / "project")})
        return binary, env

    def _project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir(exist_ok=True)
        return project

    def _drive(self, root: Path, steps: list[dict], **kwargs):
        project = self._project(root)
        binary, env = self._fake(root, steps)
        with patch.dict(os.environ, env):
            receipt = drive(project, "initial task", run_dir=root / "out", codex_bin=str(binary), **kwargs)
        return receipt

    def _make_prior(self, project: Path, name: str, state: str) -> Path:
        run = project / "artifacts" / name
        create_checkpoint(run, goal="prior goal", deliverable="prior result", done_criteria=["criterion"],
                          steps=[("s", "step")], next_action="continue",
                          session_key=hashlib.sha256(name.encode()).hexdigest())
        if state == "blocked":
            block_checkpoint(run, reason="prior blocker", next_action="repair")
        elif state == "complete":
            (run / "evidence.json").write_text('{"ok":true}\n')
            verify_criterion(run, "criterion-1", ["evidence.json"])
            advance_checkpoint(run, completed_step="s", next_step=None, next_action="finish")
            (run / "review.json").write_text('{"status":"passed","reviewer":"fixture","independent":true,"findings":[]}\n')
            record_review(run, artifact_ref="review.json")
            complete_checkpoint(run)
        return run

    def test_completes_on_turn_three_and_resumes_same_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = self._drive(root, [{"action":"active"}, {}, {"action":"complete"}], max_turns=5)
            self.assertEqual("terminal", receipt["stop"]["code"])
            self.assertEqual("completed", receipt["stop"]["reason"])
            self.assertEqual(3, len(receipt["turns"]))
            self.assertEqual(["exec", "resume", "fake-thread"], receipt["turns"][1]["argv"][1:4])
            records = [json.loads(line) for line in (root / "out" / "turn-1" / "events.jsonl").read_text().splitlines()]
            self.assertGreaterEqual(len(records), 2)
            self.assertTrue(all(isinstance(record["t"], (int, float)) for record in records))
            self.assertEqual(sorted(record["t"] for record in records), [record["t"] for record in records])

    def test_waiting_checkpoint_stops_needs_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"action":"waiting"}, {}], max_turns=4)
            self.assertEqual("needs_human", receipt["stop"]["code"])
            self.assertEqual("external_wait", receipt["stop"]["reason"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_invalid_checkpoint_stops_needs_human_with_invalid_record_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"action":"invalid"}, {}], max_turns=4)
            self.assertEqual({"code":"needs_human", "reason":"invalid_record"}, receipt["stop"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_gate_checkpoint_stops_needs_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"action":"gate"}, {}], max_turns=4)
            self.assertEqual({"code":"needs_human", "reason":"approval_gate"}, receipt["stop"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_other_terminal_checkpoint_outcomes_stop(self):
        for action, outcome in (("abandon", "abandoned"), ("inconclusive", "terminal_inconclusive")):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                receipt = self._drive(Path(tmp), [{"action":action}, {}], max_turns=3)
                self.assertEqual({"code":"terminal", "reason":outcome}, receipt["stop"])
                self.assertEqual(1, len(receipt["turns"]))

    def test_quick_answer_without_checkpoint_stops_after_one_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"last":"a short answer"}, {}], max_turns=4)
            self.assertEqual("quick_answer", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_old_blocked_run_does_not_prevent_quick_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            self._make_prior(project, "old-blocked", "blocked")
            receipt = self._drive(root, [{"last": "answer"}], max_turns=3)
            self.assertEqual("quick_answer", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_existing_active_run_with_artifact_only_progress_does_not_quick_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            self._make_prior(project, "existing-active", "active")
            binary, env = self._fake(root, [
                {"artifacts":["notes/progress.txt"], "last":"turn one output"},
                {"action":"complete", "run_name":"existing-active"},
            ])
            with patch.dict(os.environ, env):
                receipt = drive(project, "resume", run_dir=root / "out", codex_bin=str(binary), max_turns=3)
            self.assertEqual({"code":"terminal", "reason":"completed"}, receipt["stop"])
            self.assertEqual(2, len(receipt["turns"]))

    def test_artifact_only_progress_prevents_fresh_quick_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"artifacts":["note.txt"], "last":"a short answer"}], max_turns=1)
            self.assertEqual("turn_cap", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_turn_failed_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"terminal":"failed"}], max_turns=4)
            self.assertEqual("turn_failed", receipt["stop"]["code"])

    def test_turn_cap_stops_after_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"action":"active"}], max_turns=1)
            self.assertEqual("turn_cap", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_wall_cap_checked_between_turns(self):
        class Clock:
            values = iter((0.0, 0.01, 1.1))
            @classmethod
            def monotonic(cls):
                return next(cls.values)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{}])
            events = [{"t":0.001, "event":{"type":"thread.started", "thread_id":"fixture"}},
                      {"t":0.002, "event":{"type":"turn.completed", "usage":{"input_tokens":1,"output_tokens":0}}}]
            with patch.dict(os.environ, env), patch("codex_science.run_driver.time", Clock), \
                 patch("codex_science.run_driver._run_turn", return_value=(events, 0, False, None, 0.01, False)) as turn:
                receipt = drive(project, "task", run_dir=root / "out", codex_bin=str(binary), max_turns=3, wall_seconds=1)
            self.assertEqual("wall_cap", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))
            turn.assert_called_once()

    def test_any_turn_timeout_maps_to_wall_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{}])

            def wall_timeout(argv, project, directory, timeout):
                return [], None, True, None, timeout, False

            with patch.dict(os.environ, env), patch("codex_science.run_driver._run_turn", side_effect=wall_timeout):
                wall_receipt = drive(project, "task", run_dir=root / "wall-out", codex_bin=str(binary), wall_seconds=10)
            self.assertEqual("wall_cap", wall_receipt["stop"]["code"])

            def shorter_timeout(argv, project, directory, timeout):
                return [], None, True, None, min(0.01, timeout / 2), False

            with patch.dict(os.environ, env), patch("codex_science.run_driver._run_turn", side_effect=shorter_timeout):
                turn_receipt = drive(project, "task", run_dir=root / "turn-out", codex_bin=str(binary), wall_seconds=10)
            self.assertEqual("wall_cap", turn_receipt["stop"]["code"])

    def test_token_cap_counts_raw_totals_conservatively_for_both_usage_shapes(self):
        cases = [
            ([{"action":"active", "usage":{"input_tokens":10,"output_tokens":5,"cached_input_tokens":900,"reasoning_tokens":800}},
              {"usage":{"input_tokens":40,"output_tokens":20,"cached_input_tokens":900,"reasoning_tokens":800}}],
             [15, 60], 75),
            ([{"action":"active", "usage":{"input_tokens":30,"output_tokens":10}},
              {"usage":{"input_tokens":9,"output_tokens":3}}],
             [40, 12], 52),
        ]
        for steps, raw_totals, total in cases:
            with self.subTest(raw_totals=raw_totals), tempfile.TemporaryDirectory() as tmp:
                receipt = self._drive(Path(tmp), steps, max_turns=5, max_total_tokens=50)
                self.assertEqual("token_cap", receipt["stop"]["code"])
                self.assertEqual("unverified", receipt["usage_mode_observed"])
                self.assertEqual(raw_totals, receipt["raw_token_totals"])
                self.assertEqual(raw_totals, [row["raw_token_total"] for row in receipt["turns"]])
                self.assertEqual("unverified", receipt["turns"][0]["usage_mode_observed"])
                self.assertEqual(total, receipt["tokens_counted"])
                self.assertEqual(total, receipt["token_total"])
                self.assertEqual(2, len(receipt["turns"]))

    def test_stalls_after_two_consecutive_no_progress_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"action":"active"}, {}, {}, {}], max_turns=6)
            self.assertEqual("stalled", receipt["stop"]["code"])
            self.assertEqual(3, len(receipt["turns"]))

    def test_prior_completed_and_blocked_runs_do_not_drive_stop_decision(self):
        for prior_state in ("complete", "blocked"):
            with self.subTest(prior_state=prior_state), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                project = self._project(root)
                self._make_prior(project, "zz-prior", prior_state)
                binary, env = self._fake(root, [
                    {"action":"active", "run_name":"aa-drive"}, {},
                    {"action":"complete", "run_name":"aa-drive"},
                ])
                with patch.dict(os.environ, env):
                    receipt = drive(project, "task", run_dir=root / "out", codex_bin=str(binary), max_turns=5)
                self.assertEqual("terminal", receipt["stop"]["code"])
                self.assertEqual(3, len(receipt["turns"]))

    def test_existing_run_changed_by_drive_is_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            self._make_prior(project, "existing-run", "active")
            binary, env = self._fake(root, [{"action":"complete", "run_name":"existing-run"}])
            with patch.dict(os.environ, env):
                receipt = drive(project, "task", run_dir=root / "out", codex_bin=str(binary), max_turns=3)
            self.assertEqual({"code":"terminal", "reason":"completed"}, receipt["stop"])
            self.assertEqual(1, len(receipt["turns"]))

    def test_newest_updated_changed_run_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = self._drive(root, [{"actions":[{"kind":"active", "name":"z-active", "updated_at":"2026-10-21T00:00:00Z"},
                                                    {"kind":"blocked", "name":"a-blocked", "updated_at":"2026-10-22T00:00:00Z"}]}, {}], max_turns=4)
            self.assertEqual("needs_human", receipt["stop"]["code"])
            self.assertEqual("blocker", receipt["stop"]["reason"])

    def test_resume_argv_uses_overrides_without_unsupported_or_forbidden_flags(self):
        argv = _argv("codex", Path("/tmp/project"), "continue", Path("/tmp/last"), "thread-1")
        self.assertEqual(["exec", "resume", "thread-1"], argv[1:4])
        self.assertIn('sandbox_mode="workspace-write"', argv)
        self.assertNotIn("-s", argv)
        self.assertNotIn("-C", argv)
        forbidden = {"--ephemeral", "--ignore-user-config", "--dangerously-bypass-approvals-and-sandbox", "--approve-for-me", "-a"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = self._drive(root, [{"action":"active"}, {}], max_turns=2)
            for turn in receipt["turns"]:
                self.assertTrue(forbidden.isdisjoint(turn["argv"]))
                self.assertNotIn("-s", turn["argv"])
                self.assertNotIn("-C", turn["argv"])

    def test_missing_thread_id_fails_without_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self._drive(Path(tmp), [{"omit_thread":True}], max_turns=3)
            self.assertEqual("turn_failed", receipt["stop"]["code"])
            self.assertEqual(1, len(receipt["turns"]))
            self.assertNotIn("resume", receipt["turns"][0]["argv"])

    def test_stale_last_message_is_removed_before_each_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{"action":"active"}, {"last":"fresh output"}])
            out = root / "out"
            stale = out / "turn-2" / "last.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale output")
            observe = root / "last-observations.jsonl"
            env["FAKE_LAST_OBSERVATIONS"] = str(observe)
            with patch.dict(os.environ, env):
                receipt = drive(project, "task", run_dir=out, codex_bin=str(binary), max_turns=3)
            observations = [json.loads(line) for line in observe.read_text().splitlines()]
            self.assertGreaterEqual(len(observations), 2)
            self.assertTrue(all(not row["existed"] for row in observations))
            self.assertEqual("stalled", receipt["stop"]["code"])

    def test_output_directory_with_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            out = root / "out"
            out.mkdir()
            receipt = out / "run-driver-receipt.json"
            receipt.write_text("previous")
            binary, env = self._fake(root, [{"last":"answer"}])
            with patch.dict(os.environ, env):
                with self.assertRaisesRegex(FileExistsError, "run-driver-receipt.json.*new --out directory"):
                    drive(project, "task", run_dir=out, codex_bin=str(binary))
            self.assertEqual("previous", receipt.read_text())

    def test_codex_home_defaults_through_runner_helper_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "codex-home"
            home.mkdir()
            (home / "config.toml").write_text('[plugins."codex-science@codex-science"]\nenabled = true\n')
            binary, env = self._fake(root, [{"last":"answer"}])
            env["CODEX_HOME"] = str(home)
            with patch.dict(os.environ, env):
                receipt = drive(self._project(root), "task", run_dir=root / "out", codex_bin=str(binary), codex_home=None)
            self.assertTrue(receipt["preflight"]["codex_science_enabled"])

    def test_popen_oserror_is_recorded_in_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = drive(self._project(root), "task", run_dir=root / "out", codex_bin=str(root / "missing-codex"))
            self.assertEqual("turn_failed", receipt["stop"]["code"])
            self.assertEqual("launch_error", receipt["stop"]["reason"])
            self.assertIn("No such file", receipt["turns"][0]["launch_error"])
            saved = json.loads((root / "out" / "run-driver-receipt.json").read_text())
            self.assertEqual("turn_failed", saved["stop"]["code"])

    def test_post_kill_communicate_uses_bounded_timeouts(self):
        class StuckProcess:
            def __init__(self):
                self.stdout = io.BytesIO()
                self.returncode = None
                self.wait_timeouts = []
                self.communicate_timeouts = []

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                self.wait_timeouts.append(timeout)
                if self.returncode is None:
                    if len(self.wait_timeouts) == 1:
                        raise subprocess.TimeoutExpired(["fake"], timeout)
                    self.returncode = -9
                return self.returncode

            def communicate(self, timeout):
                self.communicate_timeouts.append(timeout)
                if len(self.communicate_timeouts) == 1:
                    raise subprocess.TimeoutExpired(["fake"], timeout, output=b"partial")
                return b"", None

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "turn-1"
            directory.mkdir()
            process = StuckProcess()
            with patch("codex_science.run_driver.subprocess.Popen", return_value=process), \
                 patch("codex_science.run_driver.runner._kill_process_group") as kill:
                _, _, timed_out, _, _, reader_abandoned = _run_turn(["fake"], Path(tmp), directory, 0.01)
            self.assertTrue(timed_out)
            self.assertFalse(reader_abandoned)
            self.assertEqual([0.25, 0.25, 0.25], process.wait_timeouts)
            self.assertEqual([0.25, 0.25], process.communicate_timeouts)
            self.assertEqual(3, kill.call_count)

    def test_keyboard_interrupt_kills_live_process_group(self):
        class InterruptQueue:
            def put(self, item):
                pass

            def get(self, timeout):
                raise KeyboardInterrupt()

        class LiveProcess:
            def __init__(self):
                self.stdout = io.BytesIO()
                self.returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                self.returncode = -9
                return self.returncode

            def communicate(self, timeout):
                return b"", None

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "turn-1"
            directory.mkdir()
            process = LiveProcess()
            with patch("codex_science.run_driver.subprocess.Popen", return_value=process), \
                 patch("codex_science.run_driver.queue.Queue", return_value=InterruptQueue()), \
                 patch("codex_science.run_driver.runner._kill_process_group") as kill:
                with self.assertRaises(KeyboardInterrupt):
                    _run_turn(["fake"], Path(tmp), directory, 10)
            kill.assert_called_once_with(process)

    def test_reader_blocked_on_open_pipe_is_abandoned_within_bound(self):
        read_fd, write_fd = os.pipe()

        class PipeProcess:
            def __init__(self):
                self.stdout = os.fdopen(read_fd, "rb", buffering=0)
                self.returncode = None
                self.pid = 1

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                self.returncode = -9
                return self.returncode

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "turn-1"
            directory.mkdir()
            process = PipeProcess()
            started = time.monotonic()
            try:
                with patch("codex_science.run_driver.subprocess.Popen", return_value=process), \
                     patch("codex_science.run_driver.runner._kill_process_group"):
                    _, _, timed_out, _, _, reader_abandoned = _run_turn(["fake"], Path(tmp), directory, 0.02)
            finally:
                os.close(write_fd)
                for reader in threading.enumerate():
                    if reader.name == "codex-driver-event-reader":
                        reader.join(timeout=1)
                self.assertFalse(process.stdout.closed)
                process.stdout.close()
            self.assertTrue(timed_out)
            self.assertTrue(reader_abandoned)
            self.assertLess(time.monotonic() - started, 2.0)

    def test_reader_abandonment_is_recorded_in_turn_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{}])
            events = [{"t":0.001, "event":{"type":"thread.started", "thread_id":"fixture"}},
                      {"t":0.002, "event":{"type":"turn.completed", "usage":{"input_tokens":1,"output_tokens":0}}}]
            with patch.dict(os.environ, env), patch("codex_science.run_driver._run_turn",
                                                    return_value=(events, 0, False, None, 0.01, True)):
                receipt = drive(project, "task", run_dir=root / "out", codex_bin=str(binary), max_turns=1)
            self.assertTrue(receipt["turns"][0]["reader_abandoned"])

    def test_keyboard_interrupt_writes_interrupted_receipt_before_reraising(self):
        cases = [
            (KeyboardInterrupt(), "interrupted", None),
            (OSError("disk full"), "driver_error", "OSError: disk full"),
        ]
        for exception, stop_code, error_text in cases:
            with self.subTest(stop_code=stop_code), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                project = self._project(root)
                binary, env = self._fake(root, [{}])
                with patch.dict(os.environ, env), patch("codex_science.run_driver._run_turn", side_effect=exception):
                    with self.assertRaises(type(exception)):
                        drive(project, "task", run_dir=root / "out", codex_bin=str(binary))
                saved = json.loads((root / "out" / "run-driver-receipt.json").read_text())
                self.assertEqual(stop_code, saved["stop"]["code"])
                if error_text is not None:
                    self.assertEqual(error_text, saved["stop"]["error"])

    def _cli(self, root: Path, steps: list[dict], *extra: str):
        project = self._project(root)
        binary, env = self._fake(root, steps)
        command = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task", "--out",
                   str(root / "out"), "--codex-bin", str(binary), "--execute", *extra]
        return subprocess.run(command, env=env, capture_output=True, text=True, check=False)

    def test_cli_dry_run_executes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{"last":"should not run"}])
            log = root / "args.jsonl"
            env["FAKE_ARG_LOG"] = str(log)
            command = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task",
                       "--out", str(root / "out"), "--codex-bin", str(binary)]
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads(result.stdout)
            self.assertFalse(plan["execute"])
            self.assertEqual(10, len(plan["stop_table"]))
            self.assertIn("driver_error", plan["stop_table"])
            self.assertNotIn("timeout", plan["stop_table"])
            self.assertFalse(log.exists())

    def test_cli_dry_run_validates_caps_receipts_and_dash_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{}])
            base = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task", "--out",
                    str(root / "out"), "--codex-bin", str(binary)]
            for extra in (("--max-turns", "0"), ("--wall-seconds", "nan"),
                          ("--max-total-tokens", "-1")):
                result = subprocess.run([*base, *extra], env=env, capture_output=True, text=True)
                self.assertEqual(2, result.returncode)
            (root / "out").mkdir()
            (root / "out" / "run-driver-receipt.json").write_text("{}")
            result = subprocess.run(base, env=env, capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("run-driver-receipt.json", result.stderr)
            dangling_out = root / "dangling-out"
            dangling_out.mkdir()
            dangling_receipt = dangling_out / "run-driver-receipt.json"
            dangling_receipt.symlink_to(root / "missing-receipt-target")
            dangling = [*base]
            dangling[dangling.index(str(root / "out"))] = str(dangling_out)
            result = subprocess.run(dangling, env=env, capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("run-driver-receipt.json", result.stderr)
            self.assertTrue(dangling_receipt.is_symlink())
            dash = [sys.executable, str(CLI), "--project", str(project), "--prompt", "-leading", "--out",
                    str(root / "dash"), "--codex-bin", str(binary)]
            result = subprocess.run(dash, env=env, capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertFalse((root / "dash").exists())

    def test_drive_refuses_dash_prompt_and_existing_receipt_before_turn_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            dash_out = root / "dash-out"
            with self.assertRaisesRegex(ValueError, "beginning with '-'"):
                drive(project, "-leading", run_dir=dash_out, codex_bin="not-launched")
            self.assertFalse(dash_out.exists())
            continuation_out = root / "continuation-out"
            with self.assertRaisesRegex(ValueError, "continuation_prompt.*beginning with '-'"):
                drive(project, "task", run_dir=continuation_out, continuation_prompt="-continue",
                      codex_bin="not-launched")
            self.assertFalse(continuation_out.exists())

            receipt_out = root / "receipt-out"
            receipt_out.mkdir()
            receipt_path = receipt_out / "run-driver-receipt.json"
            receipt_path.write_text("reserved\n")
            with self.assertRaisesRegex(FileExistsError, "run-driver-receipt.json"):
                drive(project, "task", run_dir=receipt_out, codex_bin="not-launched")
            self.assertEqual("reserved\n", receipt_path.read_text())
            self.assertFalse((receipt_out / "turn-1").exists())

    def test_atomic_receipt_mode_matches_write_text_umask(self):
        current_umask = os.umask(0)
        os.umask(current_umask)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            _write_receipt(path, {"ok": True})
            self.assertEqual(0o644 & ~current_umask, stat.S_IMODE(path.stat().st_mode))

    def test_cli_dry_run_uses_same_absolute_argv_as_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{"last":"answer"}])
            command = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task", "--out", "out",
                       "--codex-bin", str(binary)]
            planned = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(0, planned.returncode, planned.stderr)
            first_argv = json.loads(planned.stdout)["first_argv"]
            self.assertEqual(str((root / "out" / "turn-1" / "last.md").resolve()),
                             first_argv[first_argv.index("-o") + 1])
            executed = subprocess.run([*command, "--execute"], cwd=root, env=env, capture_output=True,
                                      text=True, check=False)
            self.assertEqual(0, executed.returncode, executed.stderr)
            receipt = json.loads(executed.stdout)
            self.assertEqual(first_argv, receipt["turns"][0]["argv"])

    def test_cli_exit_codes_and_help_documentation(self):
        cases = [
            ([{"last":"answer"}], (), 0),
            ([{"action":"complete"}], (), 0),
            ([{"action":"blocked"}], (), 3),
            ([{"action":"active"}], ("--max-turns", "1"), 4),
            ([{"terminal":"failed"}], (), 5),
            ([{"terminal":"interrupted"}], (), 5),
            ([{"sleep":1}], ("--wall-seconds", "0.05"), 4),
            ([{"interrupt_parent":True}], (), 5),
            ([{"last":"answer"}], ("--wall-seconds", "nan"), 2),
            ([{"last":"answer"}], ("--wall-seconds", "inf"), 2),
        ]
        for steps, extra, expected in cases:
            with self.subTest(expected=expected, steps=steps), tempfile.TemporaryDirectory() as tmp:
                result = self._cli(Path(tmp), steps, *extra)
                self.assertEqual(expected, result.returncode, result.stderr)
        help_result = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(0, help_result.returncode)
        self.assertIn("0 terminal or quick_answer", help_result.stdout)
        self.assertIn("3 needs_human", help_result.stdout)
        self.assertIn("4 caps or stalled (turn, wall, or token cap)", " ".join(help_result.stdout.split()))
        self.assertIn("5 turn_failed or interrupted", " ".join(help_result.stdout.split()))
        self.assertIn("2 usage errors and driver_error", " ".join(help_result.stdout.split()))
        self.assertIn("may overcount cumulative resume usage", " ".join(help_result.stdout.split()))
        self.assertIn("failure, timeout, turn failure/interruption, outcome", " ".join(help_result.stdout.split()))
        self.assertIn("completion report is always recorded", " ".join(help_result.stdout.split()))
        usage = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True, check=False)
        self.assertEqual(2, usage.returncode)

    def test_cli_refuses_reused_output_with_usage_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._cli(root, [{"last":"answer"}])
            self.assertEqual(0, first.returncode, first.stderr)
            second = self._cli(root, [{"last":"answer"}])
            self.assertEqual(2, second.returncode)
            self.assertIn("run-driver-receipt.json", second.stderr)
            self.assertIn("choose a new --out directory", second.stderr)

    def test_cli_driver_error_exits_two_and_receipt_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{"last":"answer"}])
            out = root / "out"
            (out / "turn-1" / "events.jsonl").mkdir(parents=True)
            command = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task", "--out",
                       str(out), "--codex-bin", str(binary), "--execute"]
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(2, result.returncode, result.stderr)
            receipt = json.loads((out / "run-driver-receipt.json").read_text())
            self.assertEqual("driver_error", receipt["stop"]["code"])
            self.assertTrue(receipt["stop"]["error"].startswith("IsADirectoryError:"))

    def test_cli_refuses_output_inside_project_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self._project(root)
            binary, env = self._fake(root, [{"last":"answer"}])
            command = [sys.executable, str(CLI), "--project", str(project), "--prompt", "task", "--out",
                       str(project / "artifacts" / "out"), "--codex-bin", str(binary)]
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(2, result.returncode)
            self.assertIn("inside project artifacts", result.stderr)


if __name__ == "__main__":
    unittest.main()
