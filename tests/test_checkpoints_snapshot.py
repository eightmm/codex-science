import errno
import hashlib
import json
import multiprocessing
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from checkpoint_fixtures import write_completion_manifest
from codex_science import checkpoints
from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest
from codex_science.review_receipts import build_review_receipt


CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
ROOT = Path(__file__).resolve().parents[1]


class CheckpointLockTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.run = self.root / "run"
        self.run.mkdir()
        self.lock_path = self.root / ".run.checkpoint.lock"

    def test_lock_uses_writable_regular_file_for_readonly_run(self):
        self.run.chmod(0o500)
        self.addCleanup(self.run.chmod, 0o700)
        original_open = os.open
        original_flock = checkpoints.fcntl.flock

        def checked_open(path, flags, *args, **kwargs):
            if Path(path) == self.run and flags & os.O_ACCMODE != os.O_RDONLY:
                raise PermissionError("run directory cannot be opened for writing")
            return original_open(path, flags, *args, **kwargs)

        def nfs_flock(descriptor, operation):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError(errno.ENOLCK, "NFS directory lock")
            self.assertTrue(stat.S_ISREG(os.fstat(descriptor).st_mode))
            access = checkpoints.fcntl.fcntl(descriptor, checkpoints.fcntl.F_GETFL) & os.O_ACCMODE
            self.assertEqual(os.O_RDWR, access)
            return original_flock(descriptor, operation)

        with mock.patch.object(os, "open", side_effect=checked_open), \
                mock.patch.object(checkpoints.fcntl, "flock", side_effect=nfs_flock) as flock:
            with checkpoints._checkpoint_lock(self.run):
                self.assertEqual([], list(self.run.iterdir()))
        self.assertEqual(3, flock.call_count)

    def test_lock_file_is_private_external_and_shared_by_realpath_aliases(self):
        previous_mask = os.umask(0)
        try:
            with checkpoints._checkpoint_lock(self.run):
                self.assertTrue(stat.S_ISREG(self.lock_path.stat().st_mode))
                metadata = self.lock_path.stat()
                self.assertEqual(0o600, stat.S_IMODE(metadata.st_mode))
                self.assertEqual(os.getuid(), metadata.st_uid)
                self.assertEqual(b"", self.lock_path.read_bytes())
                self.assertEqual([], list(self.run.iterdir()))
        finally:
            os.umask(previous_mask)
        alias = self.root / "alias"
        alias.symlink_to(self.run, target_is_directory=True)
        with checkpoints._checkpoint_lock(alias):
            self.assertEqual(metadata.st_ino, self.lock_path.stat().st_ino)
        self.assertEqual([self.lock_path], list(self.root.glob(".*.checkpoint.lock")))
        other = self.root / "other"
        other.mkdir()
        with checkpoints._checkpoint_lock(other):
            self.assertEqual({self.lock_path, self.root / ".other.checkpoint.lock"},
                             set(self.root.glob(".*.checkpoint.lock")))

    @unittest.skipIf(os.getuid() == 0, "root bypasses directory permissions")
    def test_safe_existing_parent_permissions_are_accepted(self):
        checkpoints.create_checkpoint(
            self.run, goal="Check permissions", deliverable="Report", done_criteria=["Checked"],
            steps=[("work", "Work")], next_action="Work",
            **{"session_key": "a" * 64},
        )
        (self.run / "progress.md").write_text("Progress evidence\n")
        self.addCleanup(self.root.chmod, 0o700)
        original_flock = checkpoints.fcntl.flock
        for existing in (False, True):
            for mode in (0o700, 0o750, 0o755, 0o555):
                with self.subTest(existing=existing, mode=oct(mode)):
                    self.root.chmod(0o700)
                    self.lock_path.unlink(missing_ok=True)
                    if existing:
                        self.lock_path.touch(mode=0o600)
                    self.root.chmod(mode)
                    parent_entries = set(self.root.iterdir())
                    run_entries = set(self.run.iterdir())
                    locked_modes = []

                    def observed_flock(descriptor, operation):
                        if operation == checkpoints.fcntl.LOCK_EX:
                            locked_modes.append(os.fstat(descriptor).st_mode)
                        return original_flock(descriptor, operation)

                    with mock.patch.object(checkpoints.fcntl, "flock", side_effect=observed_flock), \
                            mock.patch.object(os, "open", wraps=os.open) as opened:
                        action = f"Continue {existing} {mode}"
                        checkpoint = checkpoints.heartbeat_checkpoint(
                            self.run, next_action=action, progress_ref="progress.md",
                        )
                    self.assertEqual(action, checkpoint["next_action"])
                    self.assertEqual(run_entries, set(self.run.iterdir()))
                    self.assertTrue(stat.S_ISDIR(locked_modes[0]))
                    if existing or mode != 0o555:
                        self.assertEqual(0o600, stat.S_IMODE(self.lock_path.stat().st_mode))
                        self.assertEqual(parent_entries | {self.lock_path}, set(self.root.iterdir()))
                        self.assertEqual(2, len(locked_modes))
                        self.assertTrue(stat.S_ISREG(locked_modes[1]))
                    else:
                        self.assertEqual(parent_entries, set(self.root.iterdir()))
                        self.assertEqual(1, len(locked_modes))
                    if existing:
                        calls = [call for call in opened.call_args_list if Path(call.args[0]) == self.lock_path]
                        self.assertEqual(1, len(calls))
                        self.assertFalse(calls[0].args[1] & os.O_CREAT)

    def test_directory_fallback_failure_names_both_repairs(self):
        original_open = os.open
        for code in (errno.EACCES, errno.EPERM, errno.EROFS):
            with self.subTest(code=code):
                operations = []

                def denied_creation(path, flags, *args, **kwargs):
                    if Path(path) == self.lock_path and flags & os.O_CREAT:
                        operations.append("create")
                        raise OSError(code, "parent is not writable")
                    return original_open(path, flags, *args, **kwargs)

                def unsupported_directory(descriptor, operation):
                    operations.append("directory")
                    raise OSError(errno.ENOLCK, "NFS directory lock")

                with mock.patch.object(os, "open", side_effect=denied_creation), \
                        mock.patch.object(checkpoints.fcntl, "flock", side_effect=unsupported_directory):
                    with self.assertRaisesRegex(ValueError, "make the parent writable.*pre-create.*0600"):
                        with checkpoints._checkpoint_lock(self.run):
                            self.fail("unsupported directory lock was accepted")
                self.assertEqual(["directory", "create"], operations)
                self.assertEqual([self.run], list(self.root.iterdir()))
                self.assertEqual([], list(self.run.iterdir()))

    def test_unsupported_directory_flock_uses_sibling_in_order(self):
        original_flock = checkpoints.fcntl.flock
        for code in (errno.ENOLCK, errno.EOPNOTSUPP, errno.EBADF, errno.EINVAL):
            with self.subTest(code=code):
                operations = []

                def unsupported_directory(descriptor, operation):
                    directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
                    operations.append((directory, operation))
                    if directory:
                        raise OSError(code, "directory flock is unsupported")
                    return original_flock(descriptor, operation)

                with mock.patch.object(checkpoints.fcntl, "flock", side_effect=unsupported_directory):
                    with checkpoints._checkpoint_lock(self.run):
                        self.assertEqual([(True, checkpoints.fcntl.LOCK_EX),
                                          (False, checkpoints.fcntl.LOCK_EX)], operations)
                self.assertEqual((False, checkpoints.fcntl.LOCK_UN), operations[-1])

    def test_directory_flock_errors_outside_unsupported_set_are_propagated(self):
        for code in (errno.EIO, errno.EACCES, None):
            with self.subTest(code=code):
                with mock.patch.object(os, "close", wraps=os.close) as close, \
                        mock.patch.object(checkpoints.fcntl, "flock", side_effect=OSError(code, "failed")):
                    with self.assertRaises(OSError) as caught:
                        with checkpoints._checkpoint_lock(self.run):
                            self.fail("directory flock error was ignored")
                self.assertEqual(code, caught.exception.errno)
                self.assertFalse(self.lock_path.exists())
                self.assertEqual(1, close.call_count)
                with self.assertRaises(OSError):
                    os.fstat(close.call_args.args[0])

    def test_locks_acquire_directory_first_and_release_in_reverse(self):
        original_flock = checkpoints.fcntl.flock
        operations = []

        def observed_flock(descriptor, operation):
            operations.append((stat.S_ISDIR(os.fstat(descriptor).st_mode), operation))
            return original_flock(descriptor, operation)

        with mock.patch.object(checkpoints.fcntl, "flock", side_effect=observed_flock):
            with checkpoints._checkpoint_lock(self.run):
                pass
        self.assertEqual([(True, checkpoints.fcntl.LOCK_EX), (False, checkpoints.fcntl.LOCK_EX),
                          (False, checkpoints.fcntl.LOCK_UN), (True, checkpoints.fcntl.LOCK_UN)], operations)

    def test_lock_open_errors_do_not_switch_to_directory_lock(self):
        original_open = os.open
        for creating, code in ((False, errno.EACCES), (False, errno.EPERM), (False, errno.EROFS),
                               (True, errno.ENOSPC), (True, errno.EIO)):
            with self.subTest(creating=creating, code=code):
                def failed_open(path, flags, *args, **kwargs):
                    if Path(path) == self.lock_path and (not creating or flags & os.O_CREAT):
                        raise OSError(code, "lock unavailable")
                    return original_open(path, flags, *args, **kwargs)

                with mock.patch.object(os, "open", side_effect=failed_open), \
                        mock.patch.object(checkpoints.fcntl, "flock", wraps=checkpoints.fcntl.flock) as flock:
                    with self.assertRaises(OSError) as caught:
                        with checkpoints._checkpoint_lock(self.run):
                            self.fail("lock error was ignored")
                    self.assertEqual(code, caught.exception.errno)
                    self.assertEqual([checkpoints.fcntl.LOCK_EX, checkpoints.fcntl.LOCK_UN],
                                     [call.args[1] for call in flock.call_args_list])

    def test_failed_creation_retries_a_concurrently_created_sibling(self):
        original_open = os.open
        original_flock = checkpoints.fcntl.flock
        locked_modes = []

        def appeared_lock(path, flags, *args, **kwargs):
            if Path(path) == self.lock_path and flags & os.O_CREAT:
                os.close(original_open(path, flags, *args, **kwargs))
                raise PermissionError(errno.EACCES, "parent became read-only")
            return original_open(path, flags, *args, **kwargs)

        def observed_flock(descriptor, operation):
            if operation == checkpoints.fcntl.LOCK_EX:
                locked_modes.append(os.fstat(descriptor).st_mode)
            return original_flock(descriptor, operation)

        with mock.patch.object(os, "open", side_effect=appeared_lock), \
                mock.patch.object(checkpoints.fcntl, "flock", side_effect=observed_flock):
            with checkpoints._checkpoint_lock(self.run):
                self.assertTrue(self.lock_path.is_file())
        self.assertEqual(2, len(locked_modes))
        self.assertTrue(stat.S_ISDIR(locked_modes[0]))
        self.assertTrue(stat.S_ISREG(locked_modes[1]))

    def test_unsafe_lock_files_are_refused_without_changing_targets(self):
        target = self.root / "target"
        target.write_bytes(b"unchanged")
        for kind in ("symlink", "dangling", "directory", "fifo", "readable", "writable", "wrong-owner"):
            with self.subTest(kind=kind):
                if kind in {"symlink", "dangling"}:
                    self.lock_path.symlink_to(target if kind == "symlink" else self.root / "missing")
                elif kind == "directory":
                    self.lock_path.mkdir()
                elif kind == "fifo":
                    os.mkfifo(self.lock_path, 0o600)
                else:
                    self.lock_path.touch(mode=0o600)
                    self.lock_path.chmod({"readable": 0o640, "writable": 0o602}.get(kind, 0o600))
                original_fstat = os.fstat

                def metadata(descriptor):
                    result = original_fstat(descriptor)
                    if kind == "wrong-owner" and result.st_ino == self.lock_path.stat().st_ino:
                        fields = list(result)
                        fields[4] = os.getuid() + 1
                        return os.stat_result(fields)
                    return result

                try:
                    with mock.patch.object(os, "fstat", side_effect=metadata), \
                            mock.patch.object(checkpoints.fcntl, "flock", wraps=checkpoints.fcntl.flock) as flock:
                        with self.assertRaises((OSError, ValueError)):
                            with checkpoints._checkpoint_lock(self.run):
                                self.fail("unsafe lock file was accepted")
                        self.assertEqual([checkpoints.fcntl.LOCK_EX, checkpoints.fcntl.LOCK_UN],
                                         [call.args[1] for call in flock.call_args_list])
                    self.assertEqual(b"unchanged", target.read_bytes())
                finally:
                    if kind == "directory":
                        self.lock_path.rmdir()
                    else:
                        self.lock_path.unlink()

    def test_lock_failure_and_body_exception_close_descriptors_and_allow_retry(self):
        original_close = os.close
        original_flock = checkpoints.fcntl.flock
        locked_modes = []

        def failed_sibling_flock(descriptor, operation):
            if operation == checkpoints.fcntl.LOCK_EX:
                locked_modes.append(os.fstat(descriptor).st_mode)
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("lock unavailable")
            return original_flock(descriptor, operation)

        with mock.patch.object(os, "close", wraps=original_close) as close, \
                mock.patch.object(checkpoints.fcntl, "flock", side_effect=failed_sibling_flock):
            with self.assertRaisesRegex(OSError, "lock unavailable"):
                with checkpoints._checkpoint_lock(self.run):
                    self.fail("failed lock was acquired")
        self.assertEqual(2, len(locked_modes))
        self.assertTrue(stat.S_ISDIR(locked_modes[0]))
        self.assertTrue(stat.S_ISREG(locked_modes[1]))
        self.assertTrue(self.lock_path.exists())
        for call in close.call_args_list:
            with self.assertRaises(OSError):
                os.fstat(call.args[0])
        inode = self.lock_path.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with checkpoints._checkpoint_lock(self.run):
                raise RuntimeError("interrupted")
        with checkpoints._checkpoint_lock(self.run):
            self.assertEqual(inode, self.lock_path.stat().st_ino)


class CheckpointSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.run = Path(self.scratch.name) / "artifacts" / "run"

    def ready(self, *, native=False, budget=False):
        checkpoints.create_checkpoint(
            self.run, goal="Verify snapshot", deliverable="Report", done_criteria=["Checked"],
            steps=[("work", "Work")], next_action="Work",
            session_key=hashlib.sha256(str(self.run).encode()).hexdigest(),
            outer_goal="native" if native else "none",
            goal_task_key="b" * 64 if native else None,
            rigor_tier="full" if budget else None,
            budget_policy="tier-v1" if budget else None,
        )
        checkpoints.advance_checkpoint(
            self.run, completed_step="work", next_step=None, next_action="Verify",
        )
        (self.run / "report.md").write_text("Verified report\n")
        checkpoints.verify_criterion(self.run, "criterion-1", ["report.md"])
        self.manifest_path = write_completion_manifest(self.run, "report.md")
        self.receipt_path = self.run / "review.json"
        self.receipt_path.write_text(json.dumps({
            "status": "passed", "reviewer": "independent reviewer", "independent": True,
            "findings": [],
        }))
        checkpoints.record_review(self.run, artifact_ref="review.json")

    def snapshot(self):
        return {path.relative_to(self.run).as_posix(): path.read_bytes()
                for path in self.run.rglob("*") if path.is_file()}

    def test_completion_runs_the_final_gate_without_writes(self):
        for native in (False, True):
            for defect in ("missing", "empty", "malformed", "object", "array", "null", "zero",
                           "encoding", "malformed-plan", "malformed-review",
                           "pending-plan", "stale-review", "invalid-sidecar", "changed-artifact"):
                with self.subTest(native=native, defect=defect):
                    self.run = Path(self.scratch.name) / f"{native}-{defect}" / "artifacts" / "run"
                    self.ready(native=native)
                    manifest = json.loads(self.manifest_path.read_text())
                    expected = "manifest.json"
                    if defect == "missing":
                        self.manifest_path.unlink()
                    elif defect == "encoding":
                        self.manifest_path.write_bytes(b"\xff")
                    elif defect in {"empty", "malformed", "object", "array", "null", "zero"}:
                        self.manifest_path.write_text({
                            "empty": "", "malformed": "{", "object": "{}", "array": "[]", "null": "null", "zero": "0",
                        }[defect])
                    else:
                        if defect == "malformed-plan":
                            manifest["plan"] = [None]
                        elif defect == "malformed-review":
                            manifest["review"] = {"status": "findings", "findings": [None]}
                        elif defect == "pending-plan":
                            manifest["plan"][0]["status"] = "pending"
                            expected = "incomplete-plan"
                        elif defect == "stale-review":
                            self.receipt_path.write_text(json.dumps(build_review_receipt(
                                review_id="review-1", reviewer="reviewer", independent=True,
                                review_modes=["record"], status="passed",
                                covered_artifacts=[{"path": "report.md", "sha256": "0" * 64}],
                                covered_claim_ids=[], findings=[], limitations=["fixture"],
                            )))
                            checkpoints.record_review(self.run, artifact_ref="review.json")
                            manifest = json.loads(self.manifest_path.read_text())
                            expected = "stale-review-receipt"
                        elif defect == "invalid-sidecar":
                            (self.run / "claims.json").write_text("{}")
                            manifest["artifacts"].append({
                                "path": "claims.json", "kind": "claim-register",
                                "sha256": hashlib.sha256(b"{}").hexdigest(),
                            })
                            expected = "Sidecar validation failed"
                        else:
                            manifest["artifacts"][0]["sha256"] = "0" * 64
                            expected = "Artifact digest mismatch"
                        self.manifest_path.write_text(json.dumps(manifest))
                    before = self.snapshot()
                    with self.assertRaisesRegex(ValueError, expected) as caught:
                        checkpoints.complete_checkpoint(self.run)
                    self.assertIn("--require-passed-review", str(caught.exception))
                    self.assertEqual(before, self.snapshot())
                    output = self.run / "deterministic-review.json"
                    final_gate = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/validate_artifact.py"),
                         str(self.manifest_path), "--review-output", str(output), "--require-passed-review"],
                        capture_output=True, text=True, timeout=CALL_TIMEOUT,
                    )
                    self.assertEqual(1, final_gate.returncode, final_gate.stdout + final_gate.stderr)
                    output.unlink(missing_ok=True)
                    cli = subprocess.run(
                        [sys.executable, str(ROOT / "scripts/science_checkpoint.py"), "complete", str(self.run)],
                        capture_output=True, text=True, timeout=CALL_TIMEOUT,
                    )
                    self.assertEqual(2, cli.returncode, cli.stdout + cli.stderr)
                    self.assertIn("--require-passed-review", cli.stderr)
                    self.assertEqual(before, self.snapshot())

    def test_goal_confirmation_rechecks_the_final_gate(self):
        self.ready(native=True)
        checkpoints.complete_checkpoint(self.run)
        manifest = json.loads(self.manifest_path.read_text())
        manifest["plan"][0]["status"] = "pending"
        self.manifest_path.write_text(json.dumps(manifest))
        (self.run / "goal.json").write_text(json.dumps({"status": "complete", "task_key": "b" * 64}))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "incomplete-plan"):
            checkpoints.confirm_goal_complete(self.run, receipt_ref="goal.json")
        self.assertEqual(before, self.snapshot())

    def test_failed_gate_and_interrupted_registration_can_be_retried(self):
        self.ready()
        manifest = json.loads(self.manifest_path.read_text())
        manifest["plan"][0]["status"] = "pending"
        self.manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "incomplete-plan"):
            checkpoints.complete_checkpoint(self.run)

        (self.run / "report.md").write_text("Refreshed report\n")
        checkpoints.verify_criterion(self.run, "criterion-1", ["report.md"])
        write_completion_manifest(self.run, "report.md")
        receipt = json.loads(self.receipt_path.read_text())
        receipt["status"] = "failed"
        self.receipt_path.write_text(json.dumps(receipt))
        checkpoints.record_review(self.run, artifact_ref="review.json")
        with self.assertRaisesRegex(ValueError, "passed independent review"):
            checkpoints.complete_checkpoint(self.run)
        receipt["status"] = "passed"
        self.receipt_path.write_text(json.dumps(receipt))
        checkpoints.record_review(self.run, artifact_ref="review.json")
        receipt["reviewer"] = "second independent reviewer"
        self.receipt_path.write_text(json.dumps(receipt))
        with mock.patch.object(checkpoints, "write_text_atomic", side_effect=OSError("interrupted write")):
            recorded = checkpoints.record_review(self.run, artifact_ref="review.json")
        self.assertEqual("failed", recorded["manifest_registration"]["status"])
        self.assertEqual("active", checkpoints.load_checkpoint(self.run)["state"])
        with self.assertRaisesRegex(ValueError, "Artifact digest mismatch"):
            checkpoints.complete_checkpoint(self.run)
        recorded = checkpoints.record_review(self.run, artifact_ref="review.json")
        self.assertEqual("updated", recorded["manifest_registration"]["status"])
        manifest = json.loads(self.manifest_path.read_text())
        sidecars = validate_bundle(manifest, self.run)
        self.assertEqual("passed", review_manifest(manifest, self.run, sidecars=sidecars)["status"])
        self.assertEqual("complete", checkpoints.complete_checkpoint(self.run)["state"])

    def test_sibling_lock_is_excluded_from_run_discovery_and_recorded_by_inventory(self):
        from datetime import datetime, timezone

        from codex_science import literature_evaluation_runner, run_driver

        self.ready()
        before = self.snapshot()
        lock_path = self.run.parent / ".run.checkpoint.lock"
        self.assertTrue(lock_path.is_file())
        self.assertEqual([self.run], [run for run, _ in
                                    checkpoints._iter_checkpoints(self.run.parent, strict=True)])
        self.assertEqual({"run"}, set(run_driver._snapshot_runs(self.run.parent)))
        report = literature_evaluation_runner._completion_report(
            self.run.parent, now=datetime.now(timezone.utc),
        )
        self.assertEqual(["run"], [run["run_id"] for run in report["runs"]])
        inventory = literature_evaluation_runner._artifact_hashes(self.run.parent)
        self.assertIn({"path": lock_path.name, "sha256": hashlib.sha256(b"").hexdigest()}, inventory)
        self.assertEqual(before, self.snapshot())

    def test_run_lock_survives_failed_calls_without_adding_artifacts(self):
        self.ready()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "at least one decision"):
            checkpoints.request_decision(self.run, questions=[], reason="Decision")
        self.assertEqual(before, self.snapshot())
        self.assertEqual({"manifest.json", "checkpoint.json", "review.json", "report.md"}, set(before))
        for target in (self.run / "missing", self.run / "report.md"):
            with self.subTest(target=target.name), self.assertRaises(OSError):
                with checkpoints._checkpoint_lock(target):
                    self.fail("a non-directory was locked")
        with mock.patch.object(checkpoints.os, "O_DIRECTORY", 0):
            with self.assertRaisesRegex(ValueError, "run must be a directory"):
                with checkpoints._checkpoint_lock(self.run / "report.md"):
                    self.fail("a non-directory was locked without O_DIRECTORY")
        gated = checkpoints.request_decision(self.run, questions=["Approve?"], reason="Decision")
        self.assertEqual("approval_required", gated["state"])

    def test_killed_mutation_releases_the_run_lock_and_keeps_checkpoint(self):
        self.ready()
        before = self.snapshot()
        ctx = multiprocessing.get_context("fork")
        loaded = ctx.Event()

        def interrupted_gate():
            def interrupted_write(*args):
                loaded.set()
                if not ctx.Event().wait(CALL_TIMEOUT):
                    raise TimeoutError("interrupted mutation was not killed")

            with mock.patch.object(checkpoints, "_write_checkpoint", side_effect=interrupted_write):
                checkpoints.request_decision(self.run, questions=["First?"], reason="Decision")

        process = ctx.Process(target=interrupted_gate)
        try:
            process.start()
            self.assertTrue(loaded.wait(CALL_TIMEOUT))
            process.kill()
            process.join(CALL_TIMEOUT)
            self.assertLess(process.exitcode, 0)
            self.assertEqual(before, self.snapshot())
            gated = checkpoints.request_decision(self.run, questions=["Recovered?"], reason="Decision")
            self.assertEqual("Recovered?", gated["pending_decisions"][0]["question"])
        finally:
            if process.is_alive():
                process.terminate()
            process.join(CALL_TIMEOUT)
            process.close()

    def test_review_verdict_and_round_hash_bind_the_bytes_parsed(self):
        self.ready(budget=True)
        original_bytes = self.receipt_path.read_bytes()
        original = checkpoints._prepare_review_manifest

        def replace_after_parse(*args, **kwargs):
            self.receipt_path.write_text(json.dumps({
                "status": "failed", "reviewer": "reviewer", "independent": True, "findings": [],
            }))
            return original(*args, **kwargs)

        with mock.patch.object(checkpoints, "_prepare_review_manifest", side_effect=replace_after_parse):
            result = checkpoints.record_review(self.run, artifact_ref="review.json")
        expected = hashlib.sha256(original_bytes).hexdigest()
        self.assertEqual("passed", result["review_receipt"]["verdict"])
        self.assertEqual(expected, result["review_receipt"]["artifact_sha256"])
        self.assertEqual(expected, result["review_rounds"][-1]["receipt_sha256"])
        with self.assertRaisesRegex(ValueError, "review evidence changed"):
            checkpoints.complete_checkpoint(self.run)

    def test_goal_receipt_hash_binds_the_bytes_parsed(self):
        self.ready(native=True)
        checkpoints.complete_checkpoint(self.run)
        path = self.run / "goal.json"
        original_bytes = json.dumps({"status": "complete", "task_key": "b" * 64}).encode()
        path.write_bytes(original_bytes)
        original = json.loads

        def replace_after_parse(value, *args, **kwargs):
            parsed = original(value, *args, **kwargs)
            if isinstance(parsed, dict) and parsed.get("status") == "complete":
                path.write_text('{"status":"failed"}')
            return parsed

        with mock.patch.object(checkpoints.json, "loads", side_effect=replace_after_parse):
            result = checkpoints.confirm_goal_complete(self.run, receipt_ref="goal.json")
        self.assertEqual(hashlib.sha256(original_bytes).hexdigest(),
                         result["outer_goal"]["receipt"]["artifact_sha256"])

    def test_completion_cannot_overwrite_a_concurrent_decision_gate(self):
        self.assert_concurrent_decision_gate()

    @unittest.skipIf(os.getuid() == 0, "root bypasses directory permissions")
    def test_directory_fallback_serializes_a_concurrent_decision_gate(self):
        for restore_parent, completion_first in ((False, False), (True, False), (True, True)):
            with self.subTest(restore_parent=restore_parent, completion_first=completion_first):
                self.run = Path(self.scratch.name) / f"{restore_parent}-{completion_first}" / "artifacts" / "run"
                self.assert_concurrent_decision_gate(readonly_parent=True, restore_parent=restore_parent,
                                                    completion_first=completion_first)

    def test_sibling_lock_serializes_when_directory_flock_is_unavailable(self):
        self.assert_concurrent_decision_gate(unsupported_directory=True)

    def assert_concurrent_decision_gate(self, *, readonly_parent=False, restore_parent=False,
                                      unsupported_directory=False, completion_first=False):
        self.ready()
        if readonly_parent:
            (self.run.parent / ".run.checkpoint.lock").unlink()
            self.run.chmod(0o700)
            self.run.parent.chmod(0o555)
            self.addCleanup(self.run.parent.chmod, 0o700)
        revision = checkpoints.load_checkpoint(self.run)["revision"]
        ctx = multiprocessing.get_context("fork")
        first_loaded, second_observed, first_written = (ctx.Event() for _ in range(3))
        directory_attempted = ctx.Event()
        receive, send = ctx.Pipe(duplex=False)
        temp_roots = [self.run.parent.parent / name for name in ("first-tmp", "second-tmp")]
        for root in temp_roots:
            root.mkdir()

        original_flock = checkpoints.fcntl.flock

        def filesystem_flock(handle, operation):
            if unsupported_directory and stat.S_ISDIR(os.fstat(handle).st_mode):
                directory_attempted.set()
                raise OSError(errno.ENOLCK, "directory flock is unsupported")
            return original_flock(handle, operation)

        def separate_temp_root(index):
            os.environ["TMPDIR"] = str(temp_roots[index])
            tempfile.tempdir = None
            self.assertEqual(str(temp_roots[index]), tempfile.gettempdir())

        def wait(event):
            if not event.wait(CALL_TIMEOUT):
                raise TimeoutError("concurrent checkpoint operation did not reach its barrier")

        def first_mutation():
            separate_temp_root(0)
            original = checkpoints._write_checkpoint

            def paused_write(*args):
                first_loaded.set()
                wait(second_observed)
                result = original(*args)
                first_written.set()
                return result

            with mock.patch.object(checkpoints, "_write_checkpoint", side_effect=paused_write), \
                    mock.patch.object(checkpoints.fcntl, "flock", side_effect=filesystem_flock):
                if completion_first:
                    checkpoints.complete_checkpoint(self.run)
                else:
                    checkpoints.request_decision(self.run, questions=["Approve?"], reason="Owner decision")

        def second_mutation():
            separate_temp_root(1)
            original_load = checkpoints.load_checkpoint
            original_write = checkpoints._write_checkpoint

            def observed_load(*args):
                result = original_load(*args)
                if not completion_first:
                    second_observed.set()
                    wait(first_written)
                return result

            def observed_write(*args):
                result = original_write(*args)
                if completion_first:
                    second_observed.set()
                return result

            def observed_flock(handle, operation):
                if operation == checkpoints.fcntl.LOCK_EX:
                    try:
                        return filesystem_flock(handle, operation | checkpoints.fcntl.LOCK_NB)
                    except BlockingIOError:
                        second_observed.set()
                return filesystem_flock(handle, operation)

            with mock.patch.object(checkpoints, "load_checkpoint", side_effect=observed_load), \
                    mock.patch.object(checkpoints, "_write_checkpoint", side_effect=observed_write), \
                    mock.patch.object(checkpoints.fcntl, "flock", side_effect=observed_flock):
                try:
                    if completion_first:
                        result = checkpoints.request_decision(self.run, questions=["Approve?"], reason="Owner decision")
                    else:
                        result = checkpoints.complete_checkpoint(self.run)
                except ValueError as error:
                    send.send(str(error))
                else:
                    send.send(result["state"])

        processes = [ctx.Process(target=first_mutation), ctx.Process(target=second_mutation)]
        try:
            processes[0].start()
            wait(first_loaded)
            if restore_parent:
                self.run.parent.chmod(0o755)
            processes[1].start()
            for process in processes:
                process.join(CALL_TIMEOUT)
                self.assertEqual(0, process.exitcode)
            self.assertTrue(receive.poll(CALL_TIMEOUT))
            self.assertIn("only an active checkpoint", receive.recv())
            checkpoint = checkpoints.load_checkpoint(self.run)
            self.assertEqual("complete" if completion_first else "approval_required", checkpoint["state"])
            decisions = [] if completion_first else [{"question": "Approve?", "reason": "Owner decision"}]
            self.assertEqual(decisions, checkpoint["pending_decisions"])
            self.assertEqual(revision + 1, checkpoint["revision"])
            if restore_parent or unsupported_directory:
                self.assertTrue((self.run.parent / ".run.checkpoint.lock").is_file())
            if unsupported_directory:
                self.assertTrue(directory_attempted.is_set())
        finally:
            second_observed.set()
            first_written.set()
            for process in processes:
                if process.pid is not None:
                    if process.is_alive():
                        process.terminate()
                    process.join(CALL_TIMEOUT)
                    process.close()
            receive.close()
            send.close()
