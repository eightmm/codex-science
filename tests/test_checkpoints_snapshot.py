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
        self.enterContext(mock.patch.object(tempfile, "gettempdir", return_value=str(self.root)))
        self.lock_dir = self.root / f"codex-science-checkpoint-locks-{os.getuid()}"
        digest = hashlib.sha256(os.fsencode(self.run.resolve())).hexdigest()
        self.lock_path = self.lock_dir / f"{digest}.lock"

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
            self.assertTrue(stat.S_ISREG(os.fstat(descriptor).st_mode))
            access = checkpoints.fcntl.fcntl(descriptor, checkpoints.fcntl.F_GETFL) & os.O_ACCMODE
            self.assertEqual(os.O_RDWR, access)
            return original_flock(descriptor, operation)

        with mock.patch.object(os, "open", side_effect=checked_open), \
                mock.patch.object(checkpoints.fcntl, "flock", side_effect=nfs_flock):
            with checkpoints._checkpoint_lock(self.run):
                self.assertEqual([], list(self.run.iterdir()))

    def test_lock_file_is_private_external_and_shared_by_realpath_aliases(self):
        previous_mask = os.umask(0)
        try:
            with checkpoints._checkpoint_lock(self.run):
                self.assertEqual(0o700, stat.S_IMODE(self.lock_dir.stat().st_mode))
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
        self.assertEqual([self.lock_path], list(self.lock_dir.iterdir()))
        other = self.root / "other"
        other.mkdir()
        with checkpoints._checkpoint_lock(other):
            self.assertEqual(2, len(list(self.lock_dir.iterdir())))

    def test_unsafe_lock_directories_are_refused(self):
        for kind in ("file", "symlink", "dangling", "group-writable", "other-writable", "wrong-owner"):
            with self.subTest(kind=kind):
                parent = self.root / kind
                parent.mkdir()
                lock_dir = parent / self.lock_dir.name
                if kind == "file":
                    lock_dir.write_bytes(b"")
                elif kind in {"symlink", "dangling"}:
                    target = parent / "target"
                    if kind == "symlink":
                        target.mkdir(mode=0o700)
                    lock_dir.symlink_to(target, target_is_directory=True)
                else:
                    lock_dir.mkdir(mode=0o700)
                    lock_dir.chmod({"group-writable": 0o720, "other-writable": 0o702}.get(kind, 0o700))
                original_fstat = os.fstat

                def metadata(descriptor):
                    result = original_fstat(descriptor)
                    if kind == "wrong-owner" and result.st_ino == lock_dir.stat().st_ino:
                        fields = list(result)
                        fields[4] = os.getuid() + 1
                        return os.stat_result(fields)
                    return result

                with mock.patch.object(tempfile, "gettempdir", return_value=str(parent)), \
                        mock.patch.object(os, "fstat", side_effect=metadata), \
                        mock.patch.object(checkpoints.fcntl, "flock") as flock:
                    with self.assertRaises((OSError, ValueError)):
                        with checkpoints._checkpoint_lock(self.run):
                            self.fail("unsafe lock directory was accepted")
                    flock.assert_not_called()
                self.assertEqual([], list(self.run.iterdir()))

    def test_safe_existing_directory_permissions_are_accepted(self):
        self.lock_dir.mkdir(mode=0o700)
        for mode in (0o700, 0o750, 0o755):
            with self.subTest(mode=oct(mode)):
                self.lock_dir.chmod(mode)
                with checkpoints._checkpoint_lock(self.run):
                    self.assertEqual(0o600, stat.S_IMODE(self.lock_path.stat().st_mode))

    def test_unsafe_lock_files_are_refused_without_changing_targets(self):
        self.lock_dir.mkdir(mode=0o700)
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
                            mock.patch.object(checkpoints.fcntl, "flock") as flock:
                        with self.assertRaises((OSError, ValueError)):
                            with checkpoints._checkpoint_lock(self.run):
                                self.fail("unsafe lock file was accepted")
                        flock.assert_not_called()
                    self.assertEqual(b"unchanged", target.read_bytes())
                finally:
                    if kind == "directory":
                        self.lock_path.rmdir()
                    else:
                        self.lock_path.unlink()

    def test_lock_failure_and_body_exception_close_descriptors_and_allow_retry(self):
        original_close = os.close
        with mock.patch.object(os, "close", wraps=original_close) as close, \
                mock.patch.object(checkpoints.fcntl, "flock", side_effect=OSError("lock unavailable")):
            with self.assertRaisesRegex(OSError, "lock unavailable"):
                with checkpoints._checkpoint_lock(self.run):
                    self.fail("failed lock was acquired")
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
        self.ready()
        revision = checkpoints.load_checkpoint(self.run)["revision"]
        ctx = multiprocessing.get_context("fork")
        gate_loaded, completion_observed, gate_written = (ctx.Event() for _ in range(3))
        receive, send = ctx.Pipe(duplex=False)

        def wait(event):
            if not event.wait(CALL_TIMEOUT):
                raise TimeoutError("concurrent checkpoint operation did not reach its barrier")

        def gate():
            original = checkpoints._write_checkpoint

            def paused_write(*args):
                gate_loaded.set()
                wait(completion_observed)
                result = original(*args)
                gate_written.set()
                return result

            with mock.patch.object(checkpoints, "_write_checkpoint", side_effect=paused_write):
                checkpoints.request_decision(self.run, questions=["Approve?"], reason="Owner decision")

        def completion():
            original_load, original_flock = checkpoints.load_checkpoint, checkpoints.fcntl.flock

            def observed_load(*args):
                result = original_load(*args)
                completion_observed.set()
                wait(gate_written)
                return result

            def observed_flock(handle, operation):
                if operation == checkpoints.fcntl.LOCK_EX:
                    try:
                        return original_flock(handle, operation | checkpoints.fcntl.LOCK_NB)
                    except BlockingIOError:
                        completion_observed.set()
                return original_flock(handle, operation)

            with mock.patch.object(checkpoints, "load_checkpoint", side_effect=observed_load), \
                    mock.patch.object(checkpoints.fcntl, "flock", side_effect=observed_flock):
                try:
                    checkpoints.complete_checkpoint(self.run)
                except ValueError as error:
                    send.send(str(error))
                else:
                    send.send("completion unexpectedly succeeded")

        processes = [ctx.Process(target=gate), ctx.Process(target=completion)]
        try:
            processes[0].start()
            wait(gate_loaded)
            processes[1].start()
            for process in processes:
                process.join(CALL_TIMEOUT)
                self.assertEqual(0, process.exitcode)
            self.assertTrue(receive.poll(CALL_TIMEOUT))
            self.assertIn("only an active checkpoint", receive.recv())
            checkpoint = checkpoints.load_checkpoint(self.run)
            self.assertEqual("approval_required", checkpoint["state"])
            self.assertEqual([{"question": "Approve?", "reason": "Owner decision"}], checkpoint["pending_decisions"])
            self.assertEqual(revision + 1, checkpoint["revision"])
        finally:
            completion_observed.set()
            gate_written.set()
            for process in processes:
                if process.pid is not None:
                    if process.is_alive():
                        process.terminate()
                    process.join(CALL_TIMEOUT)
                    process.close()
            receive.close()
            send.close()
