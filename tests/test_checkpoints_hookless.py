import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from codex_science.checkpoints import (
    claim_checkpoint,
    create_checkpoint,
    find_active_checkpoint,
    _initialization_admission,
    load_checkpoint,
    validate_checkpoint,
    _write_checkpoint,
)
from codex_science.completion_report import report_completion
from datetime import datetime, timedelta, timezone


class HooklessCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def init(self, name, *, hookless=True, tier="standard", outer_goal="none", key=None):
        return create_checkpoint(
            self.root / "artifacts" / name,
            goal="goal", deliverable="result", done_criteria=["criterion"],
            steps=[("s", "step")], next_action="continue", session_key=key,
            hookless=hookless, rigor_tier=tier, outer_goal=outer_goal,
        )

    def create_at(self, run_dir):
        return create_checkpoint(
            run_dir, goal="goal", deliverable="result", done_criteria=["criterion"],
            steps=[("s", "step")], next_action="continue", hookless=True,
            rigor_tier="standard",
        )

    def test_key_binding_validation_and_uniqueness(self):
        first = self.init("one")
        with tempfile.TemporaryDirectory() as separate:
            second = create_checkpoint(
                Path(separate) / "artifacts" / "two", goal="goal", deliverable="result",
                done_criteria=["criterion"], steps=[("s", "step")], next_action="continue",
                hookless=True, rigor_tier="full",
            )
        self.assertRegex(first["session_key"], re.compile(r"^[0-9a-f]{64}$"))
        self.assertNotEqual(first["session_key"], second["session_key"])
        self.assertEqual({"mode": "hookless", "hook_bound": False, "key_source": "random_run_local", "created_at": first["created_at"]}, first["session_binding"])
        validate_checkpoint(first)
        for bad in (
            {**first["session_binding"], "extra": True},
            {**first["session_binding"], "hook_bound": 0},
            {**first["session_binding"], "created_at": "not-a-timeZ"},
        ):
            with self.subTest(bad=bad):
                checkpoint = dict(first, session_binding=bad)
                with self.assertRaises(ValueError):
                    validate_checkpoint(checkpoint)
        with self.assertRaisesRegex(ValueError, "only on schema-v4"):
            validate_checkpoint(dict(first, schema_version=3))
        legacy = dict(first)
        legacy.pop("session_binding")
        validate_checkpoint(legacy)
        for schema in (1, 2, 3, 4):
            fixture = dict(legacy, schema_version=schema)
            if schema < 3:
                fixture["done_criteria"] = [item["text"] for item in fixture["done_criteria"]]
            validate_checkpoint(fixture)

    def test_mutually_exclusive_native_and_quick_rejections(self):
        with self.assertRaisesRegex(ValueError, "cannot accept an explicit"):
            self.init("key", key="a" * 64)
        with self.assertRaisesRegex(ValueError, "standard or full"):
            self.init("quick", tier=None)
        with self.assertRaisesRegex(ValueError, "does not support native"):
            self.init("native", outer_goal="native")
        self.assertFalse((self.root / "artifacts").exists())

    def test_hookless_paths_must_be_visible_children_of_scanned_artifacts_roots(self):
        with self.assertRaisesRegex(ValueError, "visible run directory"):
            self.create_at(self.root / "runs" / "a")
        self.assertFalse((self.root / "runs").exists())
        with self.assertRaisesRegex(ValueError, "visible run directory"):
            self.create_at(self.root / "artifacts" / ".x")
        self.assertFalse((self.root / "artifacts").exists())
        with mock.patch(
            "codex_science.checkpoints._artifact_roots",
            return_value=[self.root / "different" / "artifacts"],
        ):
            with self.assertRaisesRegex(ValueError, "not covered"):
                self.create_at(self.root / "artifacts" / "run")
        self.assertFalse((self.root / "artifacts").exists())

    def test_cli_session_key_and_hookless_are_mutually_exclusive(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        result = subprocess.run(
            [sys.executable, str(script), "init", str(self.root / "bad"), "--goal", "g", "--deliverable", "d", "--done", "c", "--step", "s=step", "--next-action", "continue", "--session-key", "a" * 64, "--hookless", "--rigor-tier", "standard"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not allowed with argument", result.stderr)

    def test_cli_requires_one_session_mode_and_reports_os_errors_as_usage_errors(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        args = [str(script), "init", str(self.root / "artifacts" / "missing"), "--goal", "g", "--deliverable", "d", "--done", "c", "--step", "s=step", "--next-action", "continue"]
        missing = subprocess.run([sys.executable, *args], capture_output=True, text=True)
        self.assertEqual(2, missing.returncode)
        self.assertIn("--session-key", missing.stderr)
        self.assertIn("--hookless", missing.stderr)
        self.assertFalse((self.root / "artifacts").exists())

        spec = importlib.util.spec_from_file_location("science_checkpoint_cli_test", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for error_type in (OSError, TimeoutError):
            with self.subTest(error_type=error_type.__name__):
                stderr = io.StringIO()
                with mock.patch.object(module, "create_checkpoint", side_effect=error_type("lock failed")):
                    with mock.patch.object(sys, "argv", args + ["--session-key", "a" * 64]):
                        with mock.patch("sys.stderr", stderr):
                            with self.assertRaises(SystemExit) as raised:
                                module.main()
                self.assertEqual(2, raised.exception.code)
                self.assertIn("lock failed", stderr.getvalue())

    def test_hookless_and_existing_nonterminal_exclude_each_other(self):
        self.init("one")
        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint exists"):
            self.init("two")

    def test_refused_hookless_init_does_not_create_a_new_artifacts_root(self):
        self.init("first")
        second_artifacts = self.root / "nested" / "artifacts"
        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint exists"):
            self.create_at(second_artifacts / "second")
        self.assertFalse((self.root / "nested").exists())

    def test_hookless_init_rejected_when_hook_bound_run_exists(self):
        create_checkpoint(self.root / "artifacts" / "bound", goal="g", deliverable="d", done_criteria=["c"], steps=[("s", "s")], next_action="n", session_key="a" * 64)
        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint exists"):
            self.init("hookless")

    def test_bound_init_rejected_while_hookless_run_is_nonterminal(self):
        self.init("one")
        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint exists"):
            self.init("bound", hookless=False, key="a" * 64)

    def test_hook_bound_init_ignores_unrelated_corrupt_checkpoint(self):
        corrupt = self.root / "artifacts" / "broken"
        corrupt.mkdir(parents=True)
        (corrupt / "checkpoint.json").write_text("{", encoding="utf-8")
        checkpoint = self.init("bound", hookless=False, key="a" * 64)
        self.assertEqual("a" * 64, checkpoint["session_key"])

    def test_hook_bound_init_ignores_symlinked_run_directory(self):
        outside = self.root / "outside"
        outside.mkdir()
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        (artifacts / "linked").symlink_to(outside, target_is_directory=True)
        checkpoint = self.init("bound", hookless=False, key="a" * 64)
        self.assertEqual("a" * 64, checkpoint["session_key"])

    def test_hook_bound_init_preserves_symlinked_artifacts_root_without_lock_setup(self):
        from codex_science import checkpoints

        target = self.root / "external-artifacts"
        target.mkdir()
        (self.root / "artifacts").symlink_to(target, target_is_directory=True)
        original_open = checkpoints.os.open

        def refuse_root_lock(path, *args, **kwargs):
            if Path(path).name == ".checkpoint-init.lock":
                raise OSError("lock unavailable")
            return original_open(path, *args, **kwargs)

        with mock.patch("codex_science.checkpoints.os.open", side_effect=refuse_root_lock):
            checkpoint = self.init("bound", hookless=False, key="a" * 64)
        self.assertEqual("a" * 64, checkpoint["session_key"])
        self.assertTrue((target / "bound" / "checkpoint.json").is_file())

    def test_hookless_scan_fails_closed_on_symlink_and_run_limit(self):
        outside = self.root / "outside"
        outside.mkdir()
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        (artifacts / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink run directory"):
            self.init("hookless")
        (artifacts / "linked").unlink()
        (artifacts / "one").mkdir()
        (artifacts / "two").mkdir()
        with mock.patch("codex_science.checkpoints.MAX_AUTOCONTINUE_RUNS", 1):
            with self.assertRaisesRegex(ValueError, "scan limit"):
                self.init("hookless")

    def test_initialization_lock_timeout_is_actionable(self):
        run_dir = self.root / "artifacts" / "run"
        with mock.patch("codex_science.checkpoints.fcntl.flock", side_effect=BlockingIOError):
            with self.assertRaisesRegex(ValueError, "initialization is busy"):
                with _initialization_admission(run_dir, hookless=True, timeout=0):
                    self.fail("busy initialization lock unexpectedly admitted")

    def test_unlockable_related_artifact_root_releases_previously_taken_locks(self):
        from codex_science import checkpoints as checkpoints_module

        target_root = self.root / "artifacts"
        related_root = self.root / "sub" / "artifacts"
        related_root.mkdir(parents=True)
        run_dir = target_root / "run"
        target_lock = target_root / ".checkpoint-init.lock"
        related_lock = related_root / ".checkpoint-init.lock"
        original_open = checkpoints_module.os.open

        def fail_related_open(path, flags, mode=0o777):
            if Path(path) == related_lock:
                raise PermissionError("permission denied")
            return original_open(path, flags, mode)

        with mock.patch.object(
            checkpoints_module, "_related_artifact_roots", return_value=[related_root, target_root]
        ):
            with mock.patch.object(checkpoints_module.os, "open", side_effect=fail_related_open):
                with self.assertRaisesRegex(
                    ValueError,
                    f"related artifact root is not lockable.*{re.escape(str(related_root))}",
                ):
                    self.create_at(run_dir)

        self.assertFalse((run_dir / "checkpoint.json").exists())
        self.assertFalse(related_lock.exists())
        with target_lock.open("r+") as handle:
            checkpoints_module.fcntl.flock(handle, checkpoints_module.fcntl.LOCK_EX | checkpoints_module.fcntl.LOCK_NB)
            checkpoints_module.fcntl.flock(handle, checkpoints_module.fcntl.LOCK_UN)

    def _assert_concurrent_hookless_initializations_admit_only_one_writer(self, *, git_marker):
        first_writer_entered = threading.Event()
        release_first_writer = threading.Event()
        second_scan_passed = threading.Event()
        release_second_scan = threading.Event()
        second_lock_contended = threading.Event()
        progress = threading.Condition()
        results = []
        original_write = _write_checkpoint
        from codex_science import checkpoints as checkpoints_module
        from codex_science.checkpoints import _scan_init_admission

        original_scan = _scan_init_admission
        original_flock = checkpoints_module.fcntl.flock
        original_open = checkpoints_module.os.open
        second_scan_count = 0
        first_lock_inodes = set()
        opened_lock_paths = []

        def signal(event):
            with progress:
                event.set()
                progress.notify_all()

        def slow_write(run_dir, checkpoint):
            if threading.current_thread().name == "first-init":
                first_writer_entered.set()
                if not release_first_writer.wait(timeout=5):
                    raise TimeoutError("first initialization was not released")
            return original_write(run_dir, checkpoint)

        def synchronized_scan(run_dir, workspace, *, hookless):
            nonlocal second_scan_count
            original_scan(run_dir, workspace, hookless=hookless)
            if threading.current_thread().name == "second-init":
                second_scan_count += 1
                if second_scan_count == 2:
                    signal(second_scan_passed)
                    if not release_second_scan.wait(timeout=5):
                        raise TimeoutError("second admission scan was not released")

        def observed_flock(handle, operation):
            descriptor = handle if isinstance(handle, int) else handle.fileno()
            metadata = checkpoints_module.os.fstat(descriptor)
            inode = (metadata.st_dev, metadata.st_ino)
            if threading.current_thread().name == "first-init" and operation & checkpoints_module.fcntl.LOCK_EX:
                result = original_flock(handle, operation)
                first_lock_inodes.add(inode)
                return result
            if threading.current_thread().name == "second-init":
                try:
                    result = original_flock(handle, operation)
                except BlockingIOError:
                    if inode in first_lock_inodes:
                        signal(second_lock_contended)
                    raise
                return result
            return original_flock(handle, operation)

        def recorded_open(path, flags, mode=0o777):
            lock_path = Path(path)
            if lock_path.name == ".checkpoint-init.lock":
                opened_lock_paths.append(lock_path)
            return original_open(path, flags, mode)

        def initialize(run_dir):
            try:
                results.append(self.create_at(run_dir))
            except Exception as exc:
                results.append(exc)

        first_run = self.root / "artifacts" / "a"
        second_run = self.root / "sub" / "artifacts" / "b"
        if git_marker:
            (self.root / ".git").mkdir()
            (self.root / ".git" / "HEAD").write_text("ref: refs/heads/test\n", encoding="utf-8")
        else:
            self.assertEqual([], list(self.root.rglob(".git")))
            test_root = self.root.resolve()
            original_has_git_marker = checkpoints_module._has_git_marker

            def scoped_artifact_roots(workspace):
                current = Path(workspace).resolve()
                if current.is_file():
                    current = current.parent
                for directory in (current, *current.parents):
                    if not directory.is_relative_to(test_root):
                        break
                    yield directory / "artifacts"

            def scoped_has_git_marker(directory):
                resolved = Path(directory).resolve()
                return resolved.is_relative_to(test_root) and original_has_git_marker(resolved)

        first = threading.Thread(target=initialize, args=(first_run,), name="first-init")
        second = threading.Thread(target=initialize, args=(second_run,), name="second-init")
        with ExitStack() as patches:
            patches.enter_context(mock.patch("codex_science.checkpoints._write_checkpoint", side_effect=slow_write))
            patches.enter_context(
                mock.patch("codex_science.checkpoints._scan_init_admission", side_effect=synchronized_scan)
            )
            patches.enter_context(mock.patch("codex_science.checkpoints.fcntl.flock", side_effect=observed_flock))
            patches.enter_context(mock.patch.object(checkpoints_module.os, "open", side_effect=recorded_open))
            if not git_marker:
                patches.enter_context(
                    mock.patch.object(checkpoints_module, "_artifact_roots", side_effect=scoped_artifact_roots)
                )
                patches.enter_context(
                    mock.patch.object(checkpoints_module, "_has_git_marker", side_effect=scoped_has_git_marker)
                )
            first.start()
            self.assertTrue(first_writer_entered.wait(timeout=5))
            second.start()
            with progress:
                advanced = progress.wait_for(
                    lambda: second_lock_contended.is_set() or second_scan_passed.is_set(),
                    timeout=5,
                )
            self.assertTrue(advanced, "second initialization made no admission progress")
            release_first_writer.set()
            release_second_scan.set()
            first.join(timeout=5)
            second.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in (first, second)))
        self.assertEqual(1, sum(isinstance(result, dict) for result in results))
        self.assertTrue(second_lock_contended.is_set())
        failures = [result for result in results if isinstance(result, Exception)]
        self.assertEqual(1, len(failures))
        self.assertIsInstance(failures[0], ValueError)
        self.assertRegex(str(failures[0]), "nonterminal checkpoint exists")
        lock_files = list(self.root.rglob(".checkpoint-init.lock"))
        self.assertEqual({first_run.parent, second_run.parent}, {path.parent for path in lock_files})
        self.assertTrue(all(path.parent.name == "artifacts" for path in lock_files))
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in lock_files))
        self.assertTrue(opened_lock_paths)
        self.assertTrue(all(path.parent.name == "artifacts" for path in opened_lock_paths))
        self.assertTrue(all(path.resolve().is_relative_to(self.root.resolve()) for path in opened_lock_paths))
        self.assertFalse((self.root / ".checkpoint-init.lock").exists())
        self.assertFalse((self.root / "sub" / ".checkpoint-init.lock").exists())
        if not git_marker:
            self.assertEqual([], list(self.root.rglob(".git")))

    def test_concurrent_hookless_initializations_admit_only_one_writer(self):
        self._assert_concurrent_hookless_initializations_admit_only_one_writer(git_marker=True)

    def test_concurrent_hookless_initializations_admit_only_one_writer_without_git_marker(self):
        self._assert_concurrent_hookless_initializations_admit_only_one_writer(git_marker=False)

    def test_corrupt_scan_fails_closed_and_claim_is_rejected(self):
        corrupt = self.root / "artifacts" / "broken"
        corrupt.mkdir(parents=True)
        (corrupt / "checkpoint.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot safely scan checkpoint"):
            self.init("new")
        (corrupt / "checkpoint.json").unlink()
        checkpoint = self.init("hookless")
        with self.assertRaisesRegex(ValueError, "do not support claim or key rotation"):
            claim_checkpoint(self.root / "artifacts" / "hookless", session_key=checkpoint["session_key"])

    def test_cli_round_trip_and_reporter(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        run = self.root / "artifacts" / "cli"
        result = subprocess.run(
            [sys.executable, str(script), "init", str(run), "--goal", "g", "--deliverable", "d", "--done", "c", "--step", "s=step", "--next-action", "continue", "--hookless", "--rigor-tier", "standard"],
            capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        record = json.loads(result.stdout)
        self.assertRegex(record["session_key"], r"^[0-9a-f]{64}$")
        self.assertEqual(record, load_checkpoint(run))
        self.assertTrue((self.root / "artifacts" / ".checkpoint-init.lock").is_file())
        self.assertEqual(0o600, (self.root / "artifacts" / ".checkpoint-init.lock").stat().st_mode & 0o777)
        self.assertFalse((self.root / ".checkpoint-init.lock").exists())
        hidden = self.root / "artifacts" / ".hidden-run"
        hidden.mkdir()
        (hidden / "checkpoint.json").write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(run, find_active_checkpoint(self.root, record["session_key"]))
        report = report_completion(self.root / "artifacts", now=datetime.now(timezone.utc), stale_after=timedelta(days=1))
        self.assertEqual(1, len(report["runs"]))
        self.assertEqual("hookless", report["runs"][0]["session_binding_mode"])


if __name__ == "__main__":
    unittest.main()
