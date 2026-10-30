import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest import mock

import codex_science.compute_backends as compute_backends_module
import codex_science.source_snapshot as source_snapshot_module
from codex_science.artifact_store import describe_directory
from codex_science.compute_backends import (
    JobSpec,
    LocalBackend,
    SlurmBackend,
    build_approval_receipt,
    validate_approval_receipt,
)
from codex_science.source_snapshot import (
    SOURCE_ARCHIVE_NAME,
    SOURCE_RECEIPT_NAME,
    SourceSnapshotError,
    create_git_source_bundle,
    materialize_source_bundle,
)


def refingerprint(payload: dict) -> dict:
    material = dict(payload)
    material.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {**material, "fingerprint": fingerprint}


def git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def initialize_repo(root: Path) -> tuple[Path, str]:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "fixture@example.test")
    git(repo, "config", "user.name", "Fixture")
    (repo / "source.txt").write_text("committed\n", encoding="utf-8")
    (repo / "run.py").write_text(
        "from pathlib import Path\n"
        "Path('result.txt').write_text(Path('source.txt').read_text() + Path('input.txt').read_text())\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text("input.txt\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "fixture")
    return repo, git(repo, "rev-parse", "HEAD")


def local_spec(working: Path, *, command: list[str], outputs: list[str], timeout: int = 10) -> JobSpec:
    return JobSpec.from_payload(
        {
            "schema_version": 1,
            "backend": "local",
            "name": "fixture-job",
            "command": command,
            "working_directory": str(working),
            "environment": {"OMP_NUM_THREADS": "1"},
            "inherit_environment": True,
            "inputs": [],
            "outputs": outputs,
            "resources": {"cpus": 1, "memory_mb": 256, "gpus": 0, "wall_time_seconds": timeout},
            "timeout_seconds": timeout,
            "cost_cap": None,
            "approval_required": False,
            "scientific_run_id": "run-fixture",
            "checkpoint_paths": [],
        }
    )


class ComputeBackendTests(unittest.TestCase):
    def test_submit_preserves_worker_completion_during_stale_read(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(
                root, command=[sys.executable, "-c", "from pathlib import Path; Path('result.txt').write_text('ok')"],
                outputs=["result.txt"],
            )
            read_json = compute_backends_module._read_json
            popen = subprocess.Popen
            intercepted = False
            call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))

            def finish_worker_before_read_returns(path: Path) -> dict:
                nonlocal intercepted
                state = read_json(path)
                if path.name == "state.json" and not intercepted:
                    intercepted = True
                    with popen(
                        [sys.executable, "-m", "codex_science.compute_backends", "_worker", str(path.parent)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    ) as worker:
                        _, stderr = worker.communicate(timeout=call_timeout)
                        self.assertEqual(0, worker.returncode, stderr.decode())
                    self.assertEqual("completed", read_json(path)["state"])
                return state

            try:
                with mock.patch.object(compute_backends_module.subprocess, "Popen") as launch, mock.patch.object(
                    compute_backends_module, "_read_json", side_effect=finish_worker_before_read_returns
                ):
                    launch.return_value.pid = 99999999
                    submitted = backend.submit(spec)
                with mock.patch.object(compute_backends_module, "_process_alive", return_value=False):
                    self.assertEqual("completed", backend.status(submitted["job_id"])["state"])
                    self.assertEqual("completed", backend.status(submitted["job_id"])["state"])
                self.assertEqual("ok", (root / "result.txt").read_text())
            finally:
                compute_backends_module._LOCAL_PROCESSES.pop(99999999, None)

    def test_lost_promotion_preserves_concurrent_worker_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            job_dir = backend._job_dir("racing-worker")
            job_dir.mkdir(parents=True)
            compute_backends_module._atomic_json(job_dir / "spec.json", spec.to_dict())
            state_material = compute_backends_module._state_material
            initial = state_material(
                spec, job_id=job_dir.name, state="running", submitted_at="2026-01-01T00:00:00Z",
                worker_pid=99999999,
            )
            compute_backends_module._atomic_json(job_dir / "state.json", initial)
            call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))

            def finish_worker_before_lost_receipt(*args: object, **kwargs: object) -> dict:
                if kwargs.get("state") == "lost":
                    worker = subprocess.run(
                        [sys.executable, "-m", "codex_science.compute_backends", "_worker", str(job_dir)],
                        capture_output=True, timeout=call_timeout,
                    )
                    self.assertEqual(0, worker.returncode, worker.stderr.decode())
                return state_material(*args, **kwargs)

            with mock.patch.object(compute_backends_module, "_state_material", side_effect=finish_worker_before_lost_receipt), mock.patch.object(
                compute_backends_module, "_process_alive", return_value=False
            ), mock.patch.object(compute_backends_module.time, "sleep"):
                self.assertEqual("completed", backend.status(job_dir.name)["state"])
            self.assertEqual("completed", backend.status(job_dir.name)["state"])

    def test_slurm_missing_receipt_reports_recovery_without_scheduler_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = SlurmBackend(root / "state")
            spec = replace(local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[]), backend="slurm")
            atomic_json = compute_backends_module._atomic_json

            def crash_before_receipt(path: Path, payload: dict) -> None:
                if path.name == "state.json":
                    raise RuntimeError("interrupted after sbatch")
                atomic_json(path, payload)

            with mock.patch.object(backend, "preflight", return_value={"ready": True}), mock.patch.object(
                compute_backends_module.subprocess, "run",
                return_value=subprocess.CompletedProcess(["sbatch"], 0, "42;fixture-cluster\n", ""),
            ) as submit, mock.patch.object(compute_backends_module, "_atomic_json", side_effect=crash_before_receipt):
                with self.assertRaisesRegex(RuntimeError, "interrupted after sbatch"):
                    backend.submit(spec, approval=build_approval_receipt(spec, approved_by="fixture", target="fixture"))
                self.assertEqual("sbatch", submit.call_args.args[0][0])
                self.assertEqual(1, submit.call_count)
            job_dir, = backend.jobs_dir.iterdir()
            local = LocalBackend(backend.state_dir)
            with mock.patch.object(compute_backends_module.subprocess, "run") as scheduler:
                for operation in (
                    lambda: backend.status(job_dir.name), lambda: backend.cancel(job_dir.name),
                    lambda: local.wait(job_dir.name, timeout_seconds=1),
                ):
                    with self.subTest(operation=operation):
                        with self.assertRaises(ValueError) as raised:
                            operation()
                        message = str(raised.exception)
                        for detail in (str(job_dir), "#SBATCH --job-name=fixture-job", "squeue", "sacct"):
                            self.assertIn(detail, message)
                scheduler.assert_not_called()
            self.assertFalse((job_dir / "state.json").exists())

    def test_state_publications_hold_one_stable_lock_and_preserve_terminal_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            atomic_json = compute_backends_module._atomic_json
            lock_inode = None

            def assert_locked_publication(path: Path, payload: dict) -> None:
                nonlocal lock_inode
                lock_path = root / ".state.lock"
                with lock_path.open("a") as contender:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                inode = lock_path.stat().st_ino
                if lock_inode is None:
                    lock_inode = inode
                self.assertEqual(lock_inode, inode)
                atomic_json(path, payload)

            def receipt(state: str, **updates: object) -> dict:
                return compute_backends_module._state_material(
                    spec, job_id="publication", state=state, submitted_at="2026-01-01T00:00:00Z", **updates,
                )

            with mock.patch.object(compute_backends_module, "_atomic_json", side_effect=assert_locked_publication):
                compute_backends_module._publish_job_state(root, receipt("submitted"))
                self.assertEqual("", (root / ".state.lock").read_text())
                (root / ".state.lock").write_text("preserve lock contents")
                running = compute_backends_module._publish_job_state(root, receipt("running", worker_pid=123))
                self.assertEqual(running, compute_backends_module._publish_job_state(root, receipt("submitted")))
                for current in sorted(compute_backends_module.TERMINAL_STATES):
                    original = receipt(current, message="original terminal receipt")
                    atomic_json(root / "state.json", original)
                    before = (root / "state.json").read_bytes()
                    for incoming in sorted(compute_backends_module.ALL_STATES):
                        with self.subTest(current=current, incoming=incoming):
                            self.assertEqual(original, compute_backends_module._publish_job_state(root, receipt(incoming)))
                            self.assertEqual(before, (root / "state.json").read_bytes())
                stale = receipt("lost", message="stale", outputs=[{"path": "result.txt"}])
                collected = compute_backends_module._publish_job_state(root, stale, collection=True)
                self.assertEqual("original terminal receipt", collected["message"])
                self.assertEqual(original["state"], collected["state"])
                self.assertEqual(stale["outputs"], collected["outputs"])
                compute_backends_module.validate_job_state(collected)
                self.assertEqual("preserve lock contents", (root / ".state.lock").read_text())
            with (root / ".state.lock").open("a") as released:
                fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)

            call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
            for kind in ("symlink", "directory", "fifo"):
                with self.subTest(lock_type=kind):
                    job_dir = root / kind
                    job_dir.mkdir()
                    state_path = job_dir / "state.json"
                    atomic_json(state_path, receipt("submitted"))
                    before = state_path.read_bytes()
                    lock_path = job_dir / ".state.lock"
                    fifo_guard = None
                    if kind == "symlink":
                        lock_path.symlink_to("state.json")
                    elif kind == "directory":
                        lock_path.mkdir()
                    else:
                        os.mkfifo(lock_path)
                        fifo_guard = os.open(lock_path, os.O_RDWR | os.O_NONBLOCK)
                    try:
                        probe = subprocess.run(
                            [sys.executable, "-c", "\n".join((
                                "import sys",
                                "from pathlib import Path",
                                "import codex_science.compute_backends as module",
                                "job_dir = Path(sys.argv[1])",
                                "payload = module._read_json(job_dir / 'state.json')",
                                "try:",
                                "    module._publish_job_state(job_dir, payload)",
                                "except ValueError as error:",
                                "    assert 'job state lock' in str(error), str(error)",
                                "else:",
                                "    raise AssertionError('unsafe lock was accepted')",
                            )), str(job_dir)],
                            capture_output=True, text=True, timeout=call_timeout,
                        )
                        self.assertEqual(0, probe.returncode, probe.stderr)
                        self.assertEqual(before, state_path.read_bytes())
                    finally:
                        if fifo_guard is not None:
                            os.close(fifo_guard)

            state_path = root / "state.json"
            before = state_path.read_bytes()
            flock = fcntl.flock

            for change in ("replace", "remove"):
                with self.subTest(lock_change=change):
                    def change_lock_during_acquisition(descriptor: int, operation: int) -> None:
                        flock(descriptor, operation)
                        (root / ".state.lock").unlink()
                        if change == "replace":
                            (root / ".state.lock").touch()

                    with mock.patch.object(fcntl, "flock", side_effect=change_lock_during_acquisition):
                        with self.assertRaisesRegex(ValueError, "job state lock"):
                            compute_backends_module._publish_job_state(root, receipt("running"))
                    self.assertEqual(before, state_path.read_bytes())

    def test_cancel_signals_under_lock_before_publication_so_status_cannot_mark_worker_lost(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            job_dir = backend._job_dir("cancel-race")
            job_dir.mkdir(parents=True)
            compute_backends_module._atomic_json(job_dir / "spec.json", spec.to_dict())
            state = compute_backends_module._state_material(
                spec, job_id=job_dir.name, state="running", submitted_at="2026-01-01T00:00:00Z", worker_pid=123,
            )
            compute_backends_module._atomic_json(job_dir / "state.json", state)
            alive = True
            lost_attempted = threading.Event()
            worker_attempted = threading.Event()
            call_timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
            publish = compute_backends_module._publish_job_state
            contenders = []

            def attempt_publication(path: Path, payload: dict, **kwargs: object) -> dict:
                if payload["state"] == "lost":
                    lost_attempted.set()
                elif payload["state"] == "completed":
                    worker_attempted.set()
                return publish(path, payload, **kwargs)

            def signal_worker(pid: int, operation: int) -> None:
                nonlocal alive
                self.assertEqual(123, pid)
                self.assertEqual(compute_backends_module.signal.SIGTERM, operation)
                self.assertEqual("running", compute_backends_module._read_json(job_dir / "state.json")["state"])
                alive = False
                with (job_dir / ".state.lock").open("a") as contender:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                contenders.append(executor.submit(backend.status, job_dir.name))
                contenders.append(executor.submit(
                    compute_backends_module._publish_job_state, job_dir, refingerprint({**state, "state": "completed"})
                ))
                self.assertTrue(lost_attempted.wait(call_timeout))
                self.assertTrue(worker_attempted.wait(call_timeout))
                self.assertTrue(all(not future.done() for future in contenders))

            with ThreadPoolExecutor(max_workers=2) as executor, mock.patch.object(
                compute_backends_module, "_publish_job_state", side_effect=attempt_publication
            ), mock.patch.object(compute_backends_module, "_process_alive", side_effect=lambda pid: alive), mock.patch.object(
                compute_backends_module.os, "killpg", side_effect=signal_worker
            ) as signal_worker_call, mock.patch.object(compute_backends_module.time, "sleep") as sleep:
                cancelled = backend.cancel(job_dir.name)
                self.assertEqual("cancelled", cancelled["state"])
                for future in contenders:
                    self.assertEqual(cancelled, future.result(timeout=call_timeout))
                signal_worker_call.assert_called_once()
                sleep.assert_called_once_with(0.05)
            self.assertEqual("cancelled", backend.status(job_dir.name)["state"])

            compute_backends_module._atomic_json(job_dir / "state.json", state)
            completed = refingerprint({**state, "state": "completed"})
            read_state = compute_backends_module._read_job_state

            def complete_after_unlocked_read(path: Path) -> dict:
                current = read_state(path)
                if current["state"] == "running":
                    compute_backends_module._atomic_json(path / "state.json", completed)
                return current

            with mock.patch.object(compute_backends_module, "_read_job_state", side_effect=complete_after_unlocked_read), mock.patch.object(
                compute_backends_module, "_process_alive", return_value=True
            ), mock.patch.object(compute_backends_module.os, "killpg") as signal_worker_call:
                self.assertEqual(completed, backend.cancel(job_dir.name))
                signal_worker_call.assert_not_called()
            self.assertEqual(completed, backend.status(job_dir.name))

    def test_cancel_signal_failure_preserves_receipt_and_retry_signals_again(self) -> None:
        for error in (PermissionError("refused"), OSError("signal failed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                backend = LocalBackend(root / "state")
                spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
                job_dir = backend._job_dir("signal-failure")
                job_dir.mkdir(parents=True)
                compute_backends_module._atomic_json(job_dir / "spec.json", spec.to_dict())
                initial = compute_backends_module._state_material(
                    spec, job_id=job_dir.name, state="running", submitted_at="2026-01-01T00:00:00Z",
                    worker_pid=123,
                )
                state_path = job_dir / "state.json"
                compute_backends_module._atomic_json(state_path, initial)
                before = state_path.read_bytes()
                with mock.patch.object(compute_backends_module, "_process_alive", return_value=True), mock.patch.object(
                    compute_backends_module.os, "killpg", side_effect=error
                ) as send:
                    expected = KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else ValueError
                    with self.assertRaises(expected) as raised:
                        backend.cancel(job_dir.name)
                    if expected is ValueError:
                        self.assertIn("local cancellation failed:", str(raised.exception))
                    self.assertEqual(before, state_path.read_bytes())
                    send.assert_called_once_with(123, compute_backends_module.signal.SIGTERM)
                    send.side_effect = ProcessLookupError()
                    self.assertEqual("cancelled", backend.cancel(job_dir.name)["state"])
                    self.assertEqual(2, send.call_count)

    def test_terminal_cancel_retry_never_signals_or_rewrites_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            job_dir = backend._job_dir("cancelled-retry")
            job_dir.mkdir(parents=True)
            for state in sorted(compute_backends_module.TERMINAL_STATES):
                for pid in (None, "", 0, -1, 1, 123, "malformed"):
                    with self.subTest(state=state, pid=pid):
                        receipt = compute_backends_module._state_material(
                            spec, job_id=job_dir.name, state=state, submitted_at="2026-01-01T00:00:00Z",
                            worker_pid=pid,
                        )
                        state_path = job_dir / "state.json"
                        compute_backends_module._atomic_json(state_path, receipt)
                        before = state_path.read_bytes()
                        with mock.patch.object(compute_backends_module, "_process_alive", return_value=True) as alive, mock.patch.object(
                            compute_backends_module.os, "killpg"
                        ) as send, mock.patch.object(compute_backends_module, "_atomic_json") as write:
                            self.assertEqual(receipt, backend.cancel(job_dir.name))
                            self.assertEqual(receipt, backend.cancel(job_dir.name))
                            alive.assert_not_called()
                            send.assert_not_called()
                            write.assert_not_called()
                        self.assertEqual(before, state_path.read_bytes())

    def test_submit_requires_lock_before_launch_and_holds_it_through_publication(self) -> None:
        for backend_type in (LocalBackend, SlurmBackend):
            for locking in ("unavailable", "refused", "available"):
                with self.subTest(backend=backend_type.__name__, locking=locking), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    backend = backend_type(root / "state")
                    spec = replace(
                        local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[]),
                        backend="local" if backend_type is LocalBackend else "slurm",
                    )
                    approval = build_approval_receipt(spec, approved_by="fixture", target="fixture")
                    flock = fcntl.flock

                    def launch(command: list[str], **kwargs: object) -> object:
                        job_dir = Path(command[-1]).parent if backend_type is SlurmBackend else Path(command[-1])
                        with (job_dir / ".state.lock").open("a") as contender:
                            with self.assertRaises(BlockingIOError):
                                flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        if backend_type is SlurmBackend:
                            self.assertFalse((job_dir / "state.json").exists())
                            return subprocess.CompletedProcess(command, 0, "42;fixture\n", "")
                        self.assertEqual("submitted", compute_backends_module._read_json(job_dir / "state.json")["state"])
                        return mock.Mock(pid=99999999)

                    try:
                        with mock.patch.object(backend, "preflight", return_value={"ready": True}), mock.patch.object(
                            compute_backends_module, "fcntl", None if locking == "unavailable" else fcntl
                        ), mock.patch.object(
                            fcntl, "flock", side_effect=OSError("locking refused") if locking == "refused" else flock
                        ), mock.patch.object(compute_backends_module.subprocess, "run", side_effect=launch) as scheduler, mock.patch.object(
                            compute_backends_module.subprocess, "Popen", side_effect=launch
                        ) as worker:
                            if locking == "available":
                                submitted = backend.submit(spec, approval=approval)
                                self.assertEqual("submitted", submitted["state"])
                                saved = compute_backends_module._read_json(backend._job_dir(submitted["job_id"]) / "state.json")
                                self.assertEqual(submitted, saved)
                            else:
                                with self.assertRaisesRegex(ValueError, "POSIX file locking|cannot acquire job state lock"):
                                    backend.submit(spec, approval=approval)
                                scheduler.assert_not_called()
                                worker.assert_not_called()
                                self.assertFalse(list(backend.jobs_dir.glob("*/state.json")))
                    finally:
                        compute_backends_module._LOCAL_PROCESSES.pop(99999999, None)

    def test_import_without_fcntl_preserves_reads_and_refuses_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            job_dir = backend._job_dir("without-posix-locks")
            job_dir.mkdir(parents=True)
            compute_backends_module._atomic_json(job_dir / "spec.json", spec.to_dict())
            state = compute_backends_module._state_material(
                spec, job_id=job_dir.name, state="completed", submitted_at="2026-01-01T00:00:00Z",
            )
            compute_backends_module._atomic_json(job_dir / "state.json", state)
            before = (job_dir / "state.json").read_bytes()
            probe = subprocess.run(
                [sys.executable, "-c", "\n".join((
                    "import runpy, sys",
                    "from pathlib import Path",
                    "sys.modules['fcntl'] = None",
                    "import codex_science.compute_backends as module",
                    "assert module.fcntl is None",
                    "job_dir = Path(sys.argv[1])",
                    "script = sys.argv[2]",
                    "backend = module.LocalBackend(job_dir.parent.parent)",
                    "spec = module.load_spec(job_dir / 'spec.json')",
                    "assert backend.preflight(spec)['ready']",
                    "assert backend.status(job_dir.name)['state'] == 'completed'",
                    "assert backend.wait(job_dir.name, timeout_seconds=1)['state'] == 'completed'",
                    "assert backend.cancel(job_dir.name)['state'] == 'completed'",
                    "preview = module.SlurmBackend(backend.state_dir)",
                    "from dataclasses import replace",
                    "assert '#SBATCH --job-name=' in preview.render_script(replace(spec, backend='slurm'), job_id='preview')",
                    "try:",
                    "    module._publish_job_state(job_dir, backend.status(job_dir.name))",
                    "except ValueError as error:",
                    "    assert str(error) == 'job state publication requires POSIX file locking', str(error)",
                    "else:",
                    "    raise AssertionError('publication did not require locking')",
                    "sys.argv = [script, '--help']",
                    "try:",
                    "    runpy.run_path(script, run_name='__main__')",
                    "except SystemExit as error:",
                    "    assert error.code == 0, error.code",
                )), str(job_dir), str(Path(__file__).resolve().parents[1] / "scripts" / "science_job.py")],
                capture_output=True, text=True,
                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")),
            )
            self.assertEqual(0, probe.returncode, probe.stderr)
            self.assertIn("usage: science_job.py", probe.stdout)
            self.assertEqual(before, (job_dir / "state.json").read_bytes())
            self.assertFalse((job_dir / ".state.lock").exists())

    def test_lost_publication_rechecks_current_worker_and_rejects_invalid_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            lost = compute_backends_module._state_material(
                spec, job_id="recheck", state="lost", submitted_at="2026-01-01T00:00:00Z", worker_pid=99999999,
            )
            for pid, alive, expected in ((None, False, "running"), (0, False, "running"), (123, True, "running"), (123, False, "lost")):
                with self.subTest(pid=pid, alive=alive):
                    current = refingerprint({**lost, "state": "running", "worker_pid": pid})
                    compute_backends_module._atomic_json(root / "state.json", current)
                    with mock.patch.object(compute_backends_module, "_process_alive", return_value=alive) as probe:
                        result = compute_backends_module._publish_job_state(root, lost)
                    self.assertEqual(expected, result["state"])
                    if pid:
                        probe.assert_called_once_with(pid)
                    else:
                        probe.assert_not_called()
            before = (root / "state.json").read_bytes()
            for malformed in ({}, {**lost, "state": 0}, {**lost, "state": "unknown"}, {**lost, "fingerprint": ""}):
                with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                    compute_backends_module._publish_job_state(root, malformed)
                self.assertEqual(before, (root / "state.json").read_bytes())
            (root / "state.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "invalid job state record"):
                compute_backends_module._publish_job_state(root, lost)
            self.assertEqual("{}", (root / "state.json").read_text())
            with (root / ".state.lock").open("a") as released:
                fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_worker_preserves_terminal_receipts_before_and_during_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            backend = LocalBackend(root / "state")
            spec = local_spec(root, command=[sys.executable, "-c", "pass"], outputs=[])
            for terminal_state in sorted(compute_backends_module.TERMINAL_STATES):
                for phase in ("before", "during"):
                    with self.subTest(state=terminal_state, phase=phase):
                        job_dir = backend._job_dir(f"{terminal_state}-{phase}")
                        job_dir.mkdir(parents=True)
                        compute_backends_module._atomic_json(job_dir / "spec.json", spec.to_dict())
                        terminal = compute_backends_module._state_material(
                            spec, job_id=job_dir.name, state=terminal_state, submitted_at="2026-01-01T00:00:00Z",
                        )
                        initial = terminal if phase == "before" else refingerprint({**terminal, "state": "submitted"})
                        compute_backends_module._atomic_json(job_dir / "state.json", initial)

                        def finish_during_command(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
                            compute_backends_module._atomic_json(job_dir / "state.json", terminal)
                            return subprocess.CompletedProcess(spec.command, 0)

                        with mock.patch.object(compute_backends_module.subprocess, "run", side_effect=finish_during_command) as command:
                            result = compute_backends_module._worker(job_dir)
                        self.assertEqual(0 if terminal_state == "completed" else 1, result)
                        self.assertEqual(0 if phase == "before" else 1, command.call_count)
                        self.assertEqual(terminal, compute_backends_module._read_json(job_dir / "state.json"))

    def test_legacy_job_spec_serialization_and_fingerprint_remain_stable(self) -> None:
        spec = JobSpec.from_payload(
            {
                "backend": "local",
                "name": "legacy",
                "command": ["echo", "ok"],
                "working_directory": "/",
                "outputs": [],
            }
        )
        self.assertNotIn("source_snapshot", spec.to_dict())
        self.assertEqual(
            "91d571260e85dc215fc0cf6f149f794400cbc58449f54bc41728f34a64e40c71",
            spec.fingerprint,
        )

    def test_local_job_is_durable_and_outputs_are_hash_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "work"
            working.mkdir()
            state_dir = root / "state"
            spec = local_spec(
                working,
                command=[sys.executable, "-c", "from pathlib import Path; Path('result.json').write_text('{\\\"value\\\": 7}\\n')"],
                outputs=["result.json"],
            )
            backend = LocalBackend(state_dir)
            preflight = backend.preflight(spec)
            self.assertTrue(preflight["ready"])
            submitted = backend.submit(spec)
            self.assertEqual("submitted", submitted["state"])
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            self.assertEqual(0, terminal["exit_code"])
            collected = backend.collect(submitted["job_id"])
            self.assertEqual("file", collected["outputs"][0]["artifact_type"])
            self.assertEqual(64, len(collected["outputs"][0]["sha256"]))
            self.assertEqual(1, collected["outputs"][0]["entry_count"])
            self.assertTrue((state_dir / "jobs" / submitted["job_id"] / "stdout.log").is_file())
            self.assertTrue((state_dir / "jobs" / submitted["job_id"] / "stderr.log").is_file())

    def test_timeout_remains_a_distinct_terminal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "work"
            working.mkdir()
            backend = LocalBackend(root / "state")
            spec = local_spec(
                working,
                command=[sys.executable, "-c", "import time; time.sleep(2)"],
                outputs=[],
                timeout=1,
            )
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=10, poll_seconds=0.05)
            self.assertEqual("timed-out", terminal["state"])
            self.assertEqual("wall-time", terminal["failure_class"])

    def test_approval_is_bound_to_exact_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            working = Path(tempdir)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "approved-job",
                    "command": ["python", "analysis.py"],
                    "working_directory": str(working),
                    "environment": {},
                    "inputs": [],
                    "outputs": ["result.json"],
                    "resources": {"cpus": 2, "memory_mb": 1024, "gpus": 1, "gpu_type": "a100", "wall_time_seconds": 600, "partition": "gpu"},
                    "timeout_seconds": 600,
                    "approval_required": True,
                }
            )
            receipt = build_approval_receipt(spec, approved_by="reviewer", target="cluster-a", approved_at="2026-07-21T00:00:00Z")
            validate_approval_receipt(receipt, spec)
            changed = JobSpec.from_payload({**spec.to_dict(), "timeout_seconds": 601})
            with self.assertRaisesRegex(ValueError, "different job spec"):
                validate_approval_receipt(receipt, changed)

    def test_slurm_render_is_nonexecuting_and_resource_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "dock",
                    "command": ["python", "dock.py", "--input", "input.json"],
                    "working_directory": str(root),
                    "environment": {"OMP_NUM_THREADS": "4"},
                    "inputs": [],
                    "outputs": ["poses.sdf"],
                    "resources": {"cpus": 4, "memory_mb": 8192, "gpus": 1, "gpu_type": "a100", "wall_time_seconds": 7200, "partition": "gpu", "account": "science"},
                    "timeout_seconds": 7200,
                    "approval_required": True,
                }
            )
            backend = SlurmBackend(root / "state")
            script = backend.render_script(spec, job_id="preview")
            self.assertEqual("#!/usr/bin/env bash", script.splitlines()[0])
            self.assertIn("set -euo pipefail", script.splitlines())
            self.assertEqual(
                "timeout --signal=TERM 7200s python dock.py --input input.json",
                script.splitlines()[-1],
            )
            self.assertIn("#SBATCH --cpus-per-task=4", script)
            self.assertIn("#SBATCH --mem=8192M", script)
            self.assertIn("#SBATCH --gres=gpu:a100:1", script)
            self.assertIn("#SBATCH --partition=gpu", script)
            self.assertIn("#SBATCH --account=science", script)
            self.assertIn("timeout --signal=TERM 7200s", script)
            self.assertIn("python dock.py --input input.json", script)

    def test_slurm_directive_tokens_reject_control_and_option_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            base = {
                "backend": "slurm",
                "name": "safe-name",
                "command": ["python", "analysis.py"],
                "working_directory": tempdir,
                "outputs": [],
                "resources": {
                    "gpu_type": "a100",
                    "partition": "gpu",
                    "account": "science",
                    "qos": "normal",
                },
            }
            for label, payload in (
                ("name", {**base, "name": "safe\n#SBATCH --output=/tmp/injected"}),
                ("partition", {**base, "resources": {**base["resources"], "partition": "gpu --exclusive"}}),
                ("account", {**base, "resources": {**base["resources"], "account": "science\radmin"}}),
                ("qos", {**base, "resources": {**base["resources"], "qos": "normal\tdebug"}}),
                ("gpu_type", {**base, "resources": {**base["resources"], "gpu_type": "a100\n#SBATCH"}}),
            ):
                unsafe = JobSpec.from_payload(payload)
                with self.subTest(label), self.assertRaisesRegex(ValueError, "Slurm-safe token"):
                    SlurmBackend(Path(tempdir) / "state").render_script(unsafe, job_id="preview")
            valid = JobSpec.from_payload(base)
            bypassed = replace(valid, name="safe\n#SBATCH --exclusive")
            with self.assertRaisesRegex(ValueError, "Slurm-safe token"):
                SlurmBackend(Path(tempdir) / "state").render_script(bypassed, job_id="preview")

    def test_preexisting_legacy_slurm_spec_remains_collectable_but_cannot_be_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            (working / "result.txt").write_text("legacy result\n", encoding="utf-8")
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "run(v2)",
                    "command": ["python", "analysis.py"],
                    "working_directory": str(working),
                    "outputs": ["result.txt"],
                }
            )
            backend = SlurmBackend(root / "state")
            job_id = "legacy-job"
            job_dir = backend._job_dir(job_id)
            job_dir.mkdir(parents=True)
            (job_dir / "spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
            state = compute_backends_module._state_material(
                spec,
                job_id=job_id,
                state="completed",
                submitted_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:01:00Z",
                exit_code=0,
                scheduler_job_id="123",
            )
            (job_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

            collected = backend.collect(job_id)
            self.assertEqual("file", collected["outputs"][0]["artifact_type"])
            with self.assertRaisesRegex(ValueError, "Slurm-safe token"):
                backend.render_script(spec, job_id="new-attempt")

    def test_slurm_state_directory_rejects_directive_and_command_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            for payload in (
                "safe\n#SBATCH --exclusive",
                "safe\ntouch /tmp/unapproved",
                "safe\r#SBATCH --array=0-99",
                "safe\tpath",
            ):
                with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, "control characters"):
                    SlurmBackend(Path(tempdir) / payload)

    def test_secret_like_environment_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaisesRegex(ValueError, "secret-like"):
                JobSpec.from_payload(
                    {
                        "backend": "local",
                        "name": "bad",
                        "command": ["echo", "x"],
                        "working_directory": tempdir,
                        "environment": {"API_TOKEN": "secret"},
                        "outputs": [],
                    }
                )

    def test_git_snapshot_runs_and_collects_only_from_isolated_committed_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            input_path = working / "input.txt"
            input_path.write_text("bound input\n", encoding="utf-8")
            input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "strict-source",
                    "command": [sys.executable, "run.py"],
                    "working_directory": str(working),
                    "inputs": [{"id": "input", "path": "input.txt", "sha256": input_sha256}],
                    "outputs": ["result.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            self.assertTrue(backend.preflight(spec)["ready"])
            submitted = backend.submit(spec)
            (working / "source.txt").write_text("changed live\n", encoding="utf-8")
            input_path.write_text("changed input\n", encoding="utf-8")
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            job_dir = root / "state" / "jobs" / submitted["job_id"]
            result = job_dir / "source" / "result.txt"
            self.assertEqual("committed\nbound input\n", result.read_text(encoding="utf-8"))
            self.assertFalse((working / "result.txt").exists())
            collected = backend.collect(submitted["job_id"])
            self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), collected["outputs"][0]["sha256"])
            self.assertEqual("git-archive", collected["source_receipt"]["mode"])
            self.assertEqual(0o700, stat.S_IMODE(job_dir.stat().st_mode))
            self.assertEqual(0o600, stat.S_IMODE((job_dir / SOURCE_ARCHIVE_NAME).stat().st_mode))

    def test_git_local_attributes_cannot_transform_or_omit_committed_blobs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _commit = initialize_repo(root)
            (working / "omit.txt").write_bytes(b"exact committed bytes\n")
            git(working, "add", "omit.txt")
            git(working, "commit", "-qm", "committed blob")
            commit = git(working, "rev-parse", "HEAD")
            info_attributes = working / ".git" / "info" / "attributes"
            info_attributes.write_text("omit.txt export-ignore\nomit.txt export-subst\n", encoding="utf-8")
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "exact-blob",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('result.bin').write_bytes(Path('omit.txt').read_bytes())",
                    ],
                    "working_directory": str(working),
                    "outputs": ["result.bin"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            state_dir = working / "runtime-state"
            backend = LocalBackend(state_dir)
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            result = state_dir / "jobs" / submitted["job_id"] / "source" / "result.bin"
            self.assertEqual(b"exact committed bytes\n", result.read_bytes())

    def test_git_replace_refs_cannot_change_the_exact_commit_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, original_commit = initialize_repo(root)
            (working / "source.txt").write_text("replacement bytes\n", encoding="utf-8")
            git(working, "add", "source.txt")
            git(working, "commit", "-qm", "replacement commit")
            replacement_commit = git(working, "rev-parse", "HEAD")
            git(working, "replace", original_commit, replacement_commit)
            subprocess.run(
                ["git", "-C", str(working), "reset", "--hard", original_commit],
                env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"},
                text=True,
                capture_output=True,
                check=True,
            )
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "replace-ref",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('result.txt').write_text(Path('source.txt').read_text())",
                    ],
                    "working_directory": str(working),
                    "outputs": ["result.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": original_commit},
                }
            )
            backend = LocalBackend(root / "state")
            self.assertTrue(backend.preflight(spec)["ready"])
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            result = root / "state" / "jobs" / submitted["job_id"] / "source" / "result.txt"
            self.assertEqual("committed\n", result.read_text(encoding="utf-8"))

    def test_sha256_git_repository_uses_exact_64_hex_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "sha256-repo"
            completed = subprocess.run(
                ["git", "init", "-q", "--object-format=sha256", str(working)],
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                self.skipTest("installed Git does not support SHA-256 repositories")
            git(working, "config", "user.email", "fixture@example.test")
            git(working, "config", "user.name", "Fixture")
            (working / "value.txt").write_text("sha256 repository\n", encoding="utf-8")
            git(working, "add", ".")
            git(working, "commit", "-qm", "sha256 fixture")
            commit = git(working, "rev-parse", "HEAD")
            self.assertEqual(64, len(commit))
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "sha256-git",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('result.txt').write_text(Path('value.txt').read_text())",
                    ],
                    "working_directory": str(working),
                    "outputs": ["result.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            self.assertEqual(64, len(terminal["source_receipt"]["tree"]))

    def test_nested_working_directory_is_preserved_in_exact_tree_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _commit = initialize_repo(root)
            nested = working / "analysis" / "nested"
            nested.mkdir(parents=True)
            (nested / "value.txt").write_text("nested committed value\n", encoding="utf-8")
            git(working, "add", "analysis")
            git(working, "commit", "-qm", "nested cwd")
            commit = git(working, "rev-parse", "HEAD")
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "nested-cwd",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('result.txt').write_text(Path('value.txt').read_text())",
                    ],
                    "working_directory": str(nested),
                    "outputs": ["result.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            job_dir = root / "state" / "jobs" / submitted["job_id"]
            self.assertEqual(
                "nested committed value\n",
                (job_dir / "source" / "analysis" / "nested" / "result.txt").read_text(encoding="utf-8"),
            )

    def test_strict_inputs_reject_overlap_and_apply_aggregate_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _commit = initialize_repo(root)
            assets = working / "assets"
            assets.mkdir()
            asset = assets / "value.bin"
            asset.write_bytes(b"asset bytes\n")
            git(working, "add", "assets")
            git(working, "commit", "-qm", "assets")
            commit = git(working, "rev-parse", "HEAD")
            asset_sha256 = hashlib.sha256(asset.read_bytes()).hexdigest()
            assets_sha256 = describe_directory(assets).root_sha256
            overlap = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "overlap",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "inputs": [
                        {"id": "assets", "path": "assets", "root_sha256": assets_sha256},
                        {"id": "asset", "path": "assets/value.bin", "sha256": asset_sha256},
                    ],
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            overlap_result = LocalBackend(root / "overlap-state").preflight(overlap)
            self.assertFalse(overlap_result["ready"])
            self.assertIn(
                "overlap",
                next(item for item in overlap_result["checks"] if item["name"] == "source-snapshot")["detail"],
            )

            ignored = working / "input.txt"
            ignored.write_bytes(b"aggregate input bytes\n")
            input_sha256 = hashlib.sha256(ignored.read_bytes()).hexdigest()
            bounded = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "aggregate",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "inputs": [{"id": "input", "path": "input.txt", "sha256": input_sha256}],
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            listing = git(working, "ls-tree", "-r", "-l", "HEAD")
            tracked_bytes = sum(int(line.partition("\t")[0].split()[3]) for line in listing.splitlines())
            aggregate_cap = tracked_bytes + ignored.stat().st_size - 1
            with mock.patch.object(source_snapshot_module, "MAX_SOURCE_CONTENT_BYTES", aggregate_cap):
                bounded_result = LocalBackend(root / "bounded-state").preflight(bounded)
            self.assertFalse(bounded_result["ready"])
            self.assertIn(
                "committed source plus inputs",
                next(item for item in bounded_result["checks"] if item["name"] == "source-snapshot")["detail"],
            )

            (working / ".git" / "info" / "exclude").write_text("scratch/\n", encoding="utf-8")
            nested_input = working / "scratch" / "a" / "b" / "value.bin"
            nested_input.parent.mkdir(parents=True)
            nested_input.write_bytes(b"x")
            nested_sha256 = hashlib.sha256(nested_input.read_bytes()).hexdigest()
            entry_bounded = JobSpec.from_payload(
                {
                    **bounded.to_dict(),
                    "name": "entry-aggregate",
                    "inputs": [
                        {"id": "nested", "path": "scratch/a/b/value.bin", "sha256": nested_sha256}
                    ],
                }
            )
            tracked_paths = [line.partition("\t")[2] for line in listing.splitlines()]
            tracked_directories = {
                tuple(Path(path).parts[:index])
                for path in tracked_paths
                for index in range(1, len(Path(path).parts))
            }
            tracked_entries = len(tracked_paths) + len(tracked_directories)
            with mock.patch.object(source_snapshot_module, "MAX_SOURCE_ENTRIES", tracked_entries + 2):
                entry_result = LocalBackend(root / "entry-state").preflight(entry_bounded)
            self.assertFalse(entry_result["ready"])
            self.assertIn(
                "entry limit",
                next(item for item in entry_result["checks"] if item["name"] == "source-snapshot")["detail"],
            )

    def test_directory_input_snapshot_is_umask_independent_and_executes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            (working / ".git" / "info" / "exclude").write_text("scratch/\n", encoding="utf-8")
            input_path = working / "scratch" / "a" / "b" / "value.txt"
            input_path.parent.mkdir(parents=True)
            input_path.write_text("permission-independent input\n", encoding="utf-8")
            (working / "scratch" / "empty").mkdir()
            input_root = describe_directory(working / "scratch").root_sha256
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "mode-stability",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('result.txt').write_text(Path('scratch/a/b/value.txt').read_text())",
                    ],
                    "working_directory": str(working),
                    "inputs": [{"id": "scratch", "path": "scratch", "root_sha256": input_root}],
                    "outputs": ["result.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            original_umask = os.umask(0o022)
            try:
                first = create_git_source_bundle(
                    working_directory=working,
                    commit=commit,
                    inputs=spec.inputs,
                    job_spec_sha256=spec.fingerprint,
                    job_dir=root / "first",
                )
                os.umask(0o077)
                input_path.chmod(0o777)
                second = create_git_source_bundle(
                    working_directory=working,
                    commit=commit,
                    inputs=spec.inputs,
                    job_spec_sha256=spec.fingerprint,
                    job_dir=root / "second",
                )
                os.umask(0o177)
                third = create_git_source_bundle(
                    working_directory=working,
                    commit=commit,
                    inputs=spec.inputs,
                    job_spec_sha256=spec.fingerprint,
                    job_dir=root / "third",
                )
                without_inputs = create_git_source_bundle(
                    working_directory=working,
                    commit=commit,
                    inputs=[],
                    job_spec_sha256=spec.fingerprint,
                    job_dir=root / "without-inputs",
                )
            finally:
                os.umask(original_umask)
            self.assertEqual(first["archive"]["sha256"], second["archive"]["sha256"])
            self.assertEqual(first["archive"]["sha256"], third["archive"]["sha256"])
            self.assertEqual([], without_inputs["input_ids"])
            with tarfile.open(root / "first" / SOURCE_ARCHIVE_NAME, mode="r") as bundle:
                members = {item.name: item for item in bundle.getmembers()}
            for directory in ("scratch", "scratch/a", "scratch/a/b"):
                self.assertEqual(0o700, members[directory].mode)
            self.assertNotIn("scratch/empty", members)

            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            source = root / "state" / "jobs" / submitted["job_id"] / "source"
            self.assertEqual("permission-independent input\n", (source / "result.txt").read_text())
            self.assertFalse((source / "scratch" / "empty").exists())
            for directory in (source / "scratch", source / "scratch" / "a", source / "scratch" / "a" / "b"):
                self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))

    def test_strict_file_input_type_swap_cannot_block_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            input_path = working / "input.txt"
            input_path.write_bytes(b"bound input\n")
            input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "input-type-swap",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "inputs": [{"id": "input", "path": "input.txt", "sha256": input_sha256}],
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            regular_digest = source_snapshot_module._regular_file_sha256

            def replace_with_fifo(path: Path) -> tuple[str, int]:
                path.unlink()
                os.mkfifo(path)
                return regular_digest(path)

            with mock.patch.object(
                source_snapshot_module,
                "_regular_file_sha256",
                side_effect=replace_with_fifo,
            ):
                result = LocalBackend(root / "state").preflight(spec)
            self.assertFalse(result["ready"])
            self.assertIn(
                "regular file",
                next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"],
            )

    def test_strict_preflight_uses_only_the_nonblocking_source_input_route(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            input_path = working / "input.txt"
            input_path.write_bytes(b"bound input\n")
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "strict-preflight-route",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "inputs": [
                        {
                            "id": "input",
                            "path": "input.txt",
                            "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                        }
                    ],
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            with mock.patch.object(
                compute_backends_module,
                "_input_preflight",
                side_effect=AssertionError("generic input preflight must not run for strict source"),
            ):
                result = LocalBackend(root / "state").preflight(spec)
            self.assertTrue(result["ready"], json.dumps(result, indent=2))

    def test_strict_file_copy_rejects_growth_before_writing_the_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / "input.bin"
            target = root / "stage" / "input.bin"
            original = b"bounded bytes"
            source.write_bytes(original)
            expected_sha256 = hashlib.sha256(original).hexdigest()
            source.write_bytes(original + b"unexpected growth")
            with self.assertRaisesRegex(SourceSnapshotError, "changed size"):
                source_snapshot_module._copy_file(
                    source,
                    target,
                    expected_sha256=expected_sha256,
                    expected_size=len(original),
                )
            self.assertFalse(target.exists())

    def test_git_snapshot_preflight_rejects_unhashed_dirty_moved_and_unsafe_trees(self) -> None:
        def strict_spec(working: Path, commit: str, *, inputs: list[dict] | None = None) -> JobSpec:
            return JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "strict-negative",
                    "command": [sys.executable, "run.py"],
                    "working_directory": str(working),
                    "inputs": inputs or [],
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )

        with self.subTest("unhashed path input"), tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            result = LocalBackend(root / "state").preflight(
                strict_spec(working, commit, inputs=[{"id": "source", "path": "source.txt"}])
            )
            self.assertFalse(result["ready"])
            self.assertIn("requires sha256", next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"])

        with self.subTest("dirty worktree"), tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            (working / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            result = LocalBackend(root / "state").preflight(strict_spec(working, commit))
            self.assertFalse(result["ready"])
            self.assertIn("dirty", next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"])

        with self.subTest("moved head"), tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            (working / "source.txt").write_text("second\n", encoding="utf-8")
            git(working, "add", "source.txt")
            git(working, "commit", "-qm", "move head")
            result = LocalBackend(root / "state").preflight(strict_spec(working, commit))
            self.assertFalse(result["ready"])
            self.assertIn("HEAD moved", next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"])

        with self.subTest("tracked symlink"), tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _commit = initialize_repo(root)
            os.symlink("source.txt", working / "linked.txt")
            git(working, "add", "linked.txt")
            git(working, "commit", "-qm", "tracked link")
            commit = git(working, "rev-parse", "HEAD")
            result = LocalBackend(root / "state").preflight(strict_spec(working, commit))
            self.assertFalse(result["ready"])
            self.assertIn("symbolic links", next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"])

        with self.subTest("submodule"), tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _commit = initialize_repo(root)
            child = root / "child"
            child.mkdir()
            git(child, "init", "-q")
            git(child, "config", "user.email", "fixture@example.test")
            git(child, "config", "user.name", "Fixture")
            (child / "child.txt").write_text("child\n", encoding="utf-8")
            git(child, "add", ".")
            git(child, "commit", "-qm", "child")
            git(working, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(child), "vendor")
            git(working, "commit", "-qam", "submodule")
            commit = git(working, "rev-parse", "HEAD")
            result = LocalBackend(root / "state").preflight(strict_spec(working, commit))
            self.assertFalse(result["ready"])
            self.assertIn("submodules", next(item for item in result["checks"] if item["name"] == "source-snapshot")["detail"])

    def test_tampered_snapshot_fails_closed_and_slurm_never_uses_live_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "tamper",
                    "command": [sys.executable, "run.py"],
                    "working_directory": str(working),
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            job_dir = root / "bundle"
            receipt = create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=spec.inputs,
                job_spec_sha256=spec.fingerprint,
                job_dir=job_dir,
            )
            archive = job_dir / SOURCE_ARCHIVE_NAME
            archive.write_bytes(archive.read_bytes() + b"tampered")
            with self.assertRaisesRegex(SourceSnapshotError, "integrity"):
                materialize_source_bundle(job_dir, receipt, expected_job_spec_sha256=spec.fingerprint)
            archive.unlink()
            os.mkfifo(archive)
            with self.assertRaisesRegex(SourceSnapshotError, "regular file"):
                materialize_source_bundle(job_dir, receipt, expected_job_spec_sha256=spec.fingerprint)

            slurm_spec = JobSpec.from_payload({**spec.to_dict(), "backend": "slurm", "approval_required": True})
            slurm_bundle_dir = root / "slurm-bundle"
            slurm_receipt = create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=slurm_spec.inputs,
                job_spec_sha256=slurm_spec.fingerprint,
                job_dir=slurm_bundle_dir,
            )
            slurm_backend = SlurmBackend(root / "state")
            rendered = slurm_backend.render_script(
                slurm_spec,
                job_id="submitted",
                source_receipt=slurm_receipt,
            )
            self.assertIn(slurm_receipt["archive"]["sha256"], rendered)
            self.assertIn("source.tar", rendered)
            self.assertIn("sha256sum", rendered)
            self.assertNotIn(str(working), rendered)
            self.assertIn('"$stat_tool" -Lc %s -- "$source_archive"', rendered)
            self.assertIn('"$head_tool" -c "$expected_source_size" -- "$source_archive"', rendered)
            self.assertNotIn('cp -- "$source_archive"', rendered)
            self.assertIn('"$wc_tool" -c < "$source_fd_path"', rendered)
            self.assertIn('"$sha256sum_tool" "$source_fd_path"', rendered)
            self.assertIn('"$tar_tool" -xpf "$source_fd_path"', rendered)
            self.assertNotIn('sha256sum "$source_archive"', rendered)
            self.assertNotIn('tar -xf "$source_archive"', rendered)

            other_root = root / "other"
            other_root.mkdir()
            other_working, _other_commit = initialize_repo(other_root)
            (other_working / "source.txt").write_text("different commit\n", encoding="utf-8")
            git(other_working, "add", "source.txt")
            git(other_working, "commit", "-qm", "different source")
            other_commit = git(other_working, "rev-parse", "HEAD")
            mismatched_receipt = create_git_source_bundle(
                working_directory=other_working,
                commit=other_commit,
                inputs=slurm_spec.inputs,
                job_spec_sha256=slurm_spec.fingerprint,
                job_dir=root / "mismatched-bundle",
            )
            with self.assertRaisesRegex(SourceSnapshotError, "commit differs"):
                slurm_backend.render_script(
                    slurm_spec,
                    job_id="mismatched",
                    source_receipt=mismatched_receipt,
                )

            preview = slurm_backend.render_script(slurm_spec, job_id="preview")
            self.assertIn("source.tar", preview)
            self.assertIn("0" * 64, preview)
            self.assertIn("sha256sum", preview)
            self.assertNotIn(str(working), preview)
            self.assertIn("PREVIEW ONLY", preview)
            subprocess.run(["bash", "-n"], input=rendered, text=True, check=True)

    def test_rendered_slurm_snapshot_setup_executes_verified_fd_and_rejects_tampering(self) -> None:
        missing = [
            name
            for name in (
                "bash",
                "head",
                "mkdir",
                "mktemp",
                "rm",
                "sha256sum",
                "stat",
                "tar",
                "timeout",
                "wc",
            )
            if not shutil.which(name)
        ]
        if missing:
            self.skipTest(f"Slurm script probe tools unavailable: {', '.join(missing)}")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "slurm-probe",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; Path('probe.txt').write_text(Path('source.txt').read_text())",
                    ],
                    "working_directory": str(working),
                    "outputs": ["probe.txt"],
                    "approval_required": True,
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = SlurmBackend(root / "state")
            job_id = "verified-probe"
            job_dir = backend._job_dir(job_id)
            receipt = create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=spec.inputs,
                job_spec_sha256=spec.fingerprint,
                job_dir=job_dir,
            )
            script = backend.render_script(spec, job_id=job_id, source_receipt=receipt)
            script_path = job_dir / "job.sh"
            script_path.write_text(script, encoding="utf-8")
            script_path.chmod(0o700)
            bash_env = root / "inherited-bash-env.sh"
            bash_env.write_text(': > "${BASH_ENV}.ran"\n', encoding="utf-8")
            original_umask = os.umask(0o022)
            try:
                completed = subprocess.run(
                    [str(script_path)],
                    env={
                        **os.environ,
                        "BASH_ENV": str(bash_env),
                        "TAR_OPTIONS": "--exclude=source.txt",
                    },
                    text=True,
                    capture_output=True,
                    check=False,
                )
            finally:
                os.umask(original_umask)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertFalse(Path(f"{bash_env}.ran").exists())
            self.assertEqual("committed\n", (job_dir / "source" / "probe.txt").read_text(encoding="utf-8"))
            self.assertEqual(0o644, stat.S_IMODE((job_dir / "source" / "probe.txt").stat().st_mode))
            self.assertEqual(0o644, stat.S_IMODE((job_dir / "source" / "source.txt").stat().st_mode))
            self.assertEqual(0o644, stat.S_IMODE((job_dir / "source" / "run.py").stat().st_mode))
            first_source = (job_dir / "source" / "source.txt").read_bytes()
            second_attempt = subprocess.run(
                [str(script_path)], text=True, capture_output=True, check=False
            )
            self.assertNotEqual(0, second_attempt.returncode)
            self.assertEqual(first_source, (job_dir / "source" / "source.txt").read_bytes())

            tampered_id = "tampered-probe"
            tampered_dir = backend._job_dir(tampered_id)
            tampered_receipt = create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=spec.inputs,
                job_spec_sha256=spec.fingerprint,
                job_dir=tampered_dir,
            )
            archive = tampered_dir / SOURCE_ARCHIVE_NAME
            archive.write_bytes(archive.read_bytes() + b"tamper")
            tampered_script = backend.render_script(
                spec,
                job_id=tampered_id,
                source_receipt=tampered_receipt,
            )
            rejected = subprocess.run(
                ["bash"], input=tampered_script, text=True, capture_output=True, check=False
            )
            self.assertNotEqual(0, rejected.returncode)
            self.assertFalse((tampered_dir / "source").exists())

            fifo_id = "fifo-probe"
            fifo_dir = backend._job_dir(fifo_id)
            fifo_dir.mkdir(parents=True)
            os.mkfifo(fifo_dir / SOURCE_ARCHIVE_NAME)
            fifo_script = backend.render_script(spec, job_id=fifo_id, source_receipt=receipt)
            fifo_rejected = subprocess.run(
                ["bash"], input=fifo_script, text=True, capture_output=True, check=False, timeout=2
            )
            self.assertNotEqual(0, fifo_rejected.returncode)
            self.assertFalse((fifo_dir / "source").exists())

    def test_strict_slurm_submit_binds_saved_script_to_bundle_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            for name, body in (
                ("sbatch", "printf '12345;fixture-cluster\\n'\n"),
                ("scancel", "exit 0\n"),
                ("squeue", "exit 0\n"),
            ):
                executable = fake_bin / name
                executable.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
                executable.chmod(0o700)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "strict-submit",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "outputs": [],
                    "approval_required": True,
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            approval = build_approval_receipt(
                spec,
                approved_by="fixture-reviewer",
                target="fixture-cluster",
                approved_at="2026-01-01T00:00:00Z",
            )
            backend = SlurmBackend(root / "state")
            with mock.patch.dict(os.environ, {"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"}):
                submitted = backend.submit(spec, approval=approval)

            self.assertEqual("submitted", submitted["state"])
            self.assertEqual("12345", submitted["scheduler_job_id"])
            job_dir = backend._job_dir(submitted["job_id"])
            receipt = json.loads((job_dir / SOURCE_RECEIPT_NAME).read_text(encoding="utf-8"))
            self.assertEqual(receipt, submitted["source_receipt"])
            script = (job_dir / "job.sh").read_text(encoding="utf-8")
            self.assertIn(receipt["archive"]["sha256"], script)
            self.assertIn(f"expected_source_size={receipt['archive']['size_bytes']}", script)
            self.assertTrue((job_dir / SOURCE_ARCHIVE_NAME).is_file())

    def test_collection_rejects_replaced_materialized_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "replace-source",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "outputs": ["outside.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"])
            job_dir = root / "state" / "jobs" / submitted["job_id"]
            source = job_dir / "source"
            outside = root / "outside"
            outside.mkdir()
            (outside / "outside.txt").write_text("not a job output\n", encoding="utf-8")
            for path in sorted(source.rglob("*"), reverse=True):
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()
            source.rmdir()
            os.symlink(outside, source)
            with self.assertRaisesRegex(SourceSnapshotError, "real directory"):
                backend.collect(submitted["job_id"])

    def test_collection_rejects_self_refingerprinted_receipt_commit_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "receipt-commit",
                    "command": [sys.executable, "-c", "pass"],
                    "working_directory": str(working),
                    "outputs": [],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"])
            job_dir = root / "state" / "jobs" / submitted["job_id"]
            receipt_path = job_dir / SOURCE_RECEIPT_NAME
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["commit"] = "0" * len(commit)
            receipt = refingerprint(receipt)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            state_path = job_dir / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["source_receipt"] = receipt
            state = refingerprint(state)
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(SourceSnapshotError, "differs from the job spec"):
                backend.collect(submitted["job_id"])

            second = backend.submit(spec)
            second_terminal = backend.wait(second["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", second_terminal["state"])
            second_dir = root / "state" / "jobs" / second["job_id"]
            second_receipt_path = second_dir / SOURCE_RECEIPT_NAME
            second_receipt = json.loads(second_receipt_path.read_text(encoding="utf-8"))
            second_receipt["input_ids"] = ["undeclared-input"]
            second_receipt = refingerprint(second_receipt)
            second_receipt_path.write_text(json.dumps(second_receipt), encoding="utf-8")
            second_state_path = second_dir / "state.json"
            second_state = json.loads(second_state_path.read_text(encoding="utf-8"))
            second_state["source_receipt"] = second_receipt
            second_state = refingerprint(second_state)
            second_state_path.write_text(json.dumps(second_state), encoding="utf-8")
            with self.assertRaisesRegex(SourceSnapshotError, "inputs differ"):
                backend.collect(second["job_id"])

    def test_cancelled_strict_attempt_collects_explicit_missing_outputs_without_source(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "cancelled-source",
                    "command": [sys.executable, "-c", "import time; time.sleep(5)"],
                    "working_directory": str(working),
                    "outputs": ["never-created.txt"],
                    "source_snapshot": {"mode": "git-archive", "commit": commit},
                }
            )
            backend = LocalBackend(root / "state")
            submitted = backend.submit(spec)
            cancelled = backend.cancel(submitted["job_id"])
            self.assertEqual("cancelled", cancelled["state"])
            job_dir = root / "state" / "jobs" / submitted["job_id"]
            source = job_dir / "source"
            if source.exists():
                for path in sorted(source.rglob("*"), key=lambda item: len(item.parts), reverse=True):
                    path.rmdir() if path.is_dir() else path.unlink()
                source.rmdir()
            collected = backend.collect(submitted["job_id"])
            self.assertEqual("missing", collected["outputs"][0]["artifact_type"])
            self.assertIn("materialized source directory is missing", collected["source_collection_error"])

    def test_input_preflight_reports_external_missing_digest_and_unsupported_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            (working / "good.txt").write_text("bound input", encoding="utf-8")
            (working / "bundle").mkdir()
            (working / "bundle" / "item.txt").write_text("nested input", encoding="utf-8")
            os.mkfifo(working / "pipe")
            good_digest = hashlib.sha256(b"bound input").hexdigest()
            bundle_digest = describe_directory(working / "bundle").root_sha256
            spec = local_spec(working, command=[sys.executable, "-c", "pass"], outputs=[])
            spec = replace(
                spec,
                inputs=(
                    {"id": "external", "identifier": "record-only"},
                    {"id": "missing", "path": "absent.txt"},
                    {"id": "good", "path": "good.txt", "sha256": good_digest},
                    {"id": "bundle", "path": "bundle", "root_sha256": bundle_digest},
                    {"id": "bad", "path": "good.txt", "sha256": "0" * 64},
                    {"id": "pipe", "path": "pipe", "sha256": good_digest},
                ),
            )

            result = LocalBackend(root / "state").preflight(spec)

            checks = {item["name"]: item for item in result["checks"]}
            self.assertFalse(result["ready"])
            self.assertTrue(checks["input:external"]["ready"])
            self.assertIn("external identifier", checks["input:external"]["detail"])
            self.assertFalse(checks["input:missing"]["ready"])
            self.assertEqual("missing", checks["input:missing"]["detail"])
            self.assertTrue(checks["input:good"]["ready"])
            self.assertTrue(checks["input:bundle"]["ready"])
            self.assertIn("digest mismatch", checks["input:bad"]["detail"])
            self.assertIn("unsupported filesystem object", checks["input:pipe"]["detail"])
            self.assertFalse((root / "state").exists())

    def test_worker_writes_success_and_nonzero_terminal_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            backend = LocalBackend(root / "state")
            outcomes = (
                ("successful", [sys.executable, "-c", "print('worker output')"], "completed", 0),
                ("nonzero", [sys.executable, "-c", "raise SystemExit(7)"], "failed", 7),
            )
            for job_id, command, expected_state, expected_code in outcomes:
                with self.subTest(job_id=job_id):
                    spec = local_spec(working, command=command, outputs=[])
                    job_dir = backend._job_dir(job_id)
                    job_dir.mkdir(parents=True)
                    (job_dir / "spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
                    state = compute_backends_module._state_material(
                        spec,
                        job_id=job_id,
                        state="submitted",
                        submitted_at="2026-01-01T00:00:00Z",
                    )
                    (job_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

                    result = compute_backends_module._worker(job_dir)

                    terminal = json.loads((job_dir / "state.json").read_text(encoding="utf-8"))
                    self.assertEqual(0 if expected_state == "completed" else 1, result)
                    self.assertEqual(expected_state, terminal["state"])
                    self.assertEqual(expected_code, terminal["exit_code"])
                    if expected_state == "completed":
                        self.assertEqual("worker output\n", (job_dir / "stdout.log").read_text(encoding="utf-8"))
                    else:
                        self.assertEqual("nonzero-exit", terminal["failure_class"])

    def test_local_wait_rejects_nonpositive_limits_and_collect_refuses_nonterminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            backend = LocalBackend(root / "state")
            spec = local_spec(working, command=[sys.executable, "-c", "pass"], outputs=[])
            job_id = "pending-job"
            job_dir = backend._job_dir(job_id)
            job_dir.mkdir(parents=True)
            (job_dir / "spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
            initial = compute_backends_module._state_material(
                spec,
                job_id=job_id,
                state="submitted",
                submitted_at="2026-01-01T00:00:00Z",
            )
            state_path = job_dir / "state.json"
            state_path.write_text(json.dumps(initial), encoding="utf-8")
            before = state_path.read_bytes()

            for timeout_seconds, poll_seconds in ((0, 0.2), (1, 0), (-1, 0.2)):
                with self.subTest(timeout=timeout_seconds, poll=poll_seconds), self.assertRaisesRegex(
                    ValueError, "must be positive"
                ):
                    backend.wait(job_id, timeout_seconds=timeout_seconds, poll_seconds=poll_seconds)
            with self.assertRaisesRegex(ValueError, "nonterminal"):
                backend.collect(job_id)
            self.assertEqual(before, state_path.read_bytes())
            backend.cancel(job_id)
            self.assertEqual("cancelled", backend.status(job_id)["state"])

    def test_local_status_records_dead_worker_without_terminal_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            backend = LocalBackend(root / "state")
            spec = local_spec(working, command=[sys.executable, "-c", "pass"], outputs=[])
            job_id = "lost-worker"
            job_dir = backend._job_dir(job_id)
            job_dir.mkdir(parents=True)
            (job_dir / "spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
            state = compute_backends_module._state_material(
                spec,
                job_id=job_id,
                state="running",
                submitted_at="2026-01-01T00:00:00Z",
                worker_pid=99999999,
            )
            (job_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

            with mock.patch.object(compute_backends_module, "_process_alive", return_value=False), mock.patch.object(
                compute_backends_module.time, "sleep"
            ) as sleep:
                lost = backend.status(job_id)

            self.assertEqual("lost", lost["state"])
            self.assertEqual("worker-lost", lost["failure_class"])
            sleep.assert_called_once_with(0.05)

    def test_slurm_status_cancel_and_collection_refusals_preserve_state_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            backend = SlurmBackend(root / "state")
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "scheduler-state",
                    "command": ["python", "analysis.py"],
                    "working_directory": str(working),
                    "outputs": [],
                }
            )
            job_id = "scheduler-job"
            job_dir = backend._job_dir(job_id)
            job_dir.mkdir(parents=True)
            (job_dir / "spec.json").write_text(json.dumps(spec.to_dict()), encoding="utf-8")
            state = compute_backends_module._state_material(
                spec,
                job_id=job_id,
                state="submitted",
                submitted_at="2026-01-01T00:00:00Z",
                scheduler_job_id="42",
            )
            state_path = job_dir / "state.json"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            tools_available = {"sacct": False, "squeue": False}
            cancel_outcome = {"returncode": 1}

            def scheduler_tool(name: str) -> str | None:
                return name if tools_available.get(name, False) else None

            def scheduler_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
                if command[0] == "scancel":
                    status = cancel_outcome["returncode"]
                    error = "scheduler refused" if status else ""
                    return subprocess.CompletedProcess(command, status, "", error)
                if command[0] == "sacct":
                    return subprocess.CompletedProcess(
                        command, 0, "COMPLETED|0:0|00:01|10K\n", ""
                    )
                raise AssertionError(f"unexpected scheduler command: {command[0]}")

            with mock.patch.object(
                compute_backends_module.shutil, "which", side_effect=scheduler_tool
            ) as which, mock.patch.object(
                compute_backends_module.subprocess, "run", side_effect=scheduler_command
            ) as run:
                self.assertEqual("submitted", backend.status(job_id)["state"])
                before = state_path.read_bytes()
                with self.assertRaisesRegex(ValueError, "scancel failed: scheduler refused"):
                    backend.cancel(job_id)
                expected_cancel = mock.call(
                    ["scancel", "42"], text=True, capture_output=True, check=False
                )
                self.assertEqual([expected_cancel], run.call_args_list)
                self.assertEqual(before, state_path.read_bytes())
                with self.assertRaisesRegex(ValueError, "nonterminal Slurm job"):
                    backend.collect(job_id)
                self.assertEqual([expected_cancel], run.call_args_list)
                self.assertEqual(before, state_path.read_bytes())

                tools_available["sacct"] = True
                terminal = backend.status(job_id)
                self.assertEqual("completed", terminal["state"])
                self.assertEqual(0, terminal["exit_code"])
                collected = backend.collect(job_id)
                self.assertEqual([], collected["outputs"])
                self.assertEqual(
                    [expected_cancel, mock.call(
                        ["sacct", "-n", "-P", "-j", "42", "--format=State,ExitCode,Elapsed,MaxRSS"],
                        text=True,
                        capture_output=True,
                        check=False,
                    )],
                    run.call_args_list,
                )

                state_path.write_bytes(before)
                tools_available["sacct"] = False
                cancel_outcome["returncode"] = 0
                cancelled = backend.cancel(job_id)
                expected_accounting = mock.call(
                    ["sacct", "-n", "-P", "-j", "42", "--format=State,ExitCode,Elapsed,MaxRSS"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    [expected_cancel, expected_accounting, expected_cancel], run.call_args_list
                )
                self.assertEqual(
                    [expected_cancel, expected_cancel],
                    [call for call in run.call_args_list if call.args[0][0] == "scancel"],
                )
                self.assertEqual(
                    [
                        mock.call("sacct"),
                        mock.call("squeue"),
                        mock.call("sacct"),
                        mock.call("squeue"),
                        mock.call("sacct"),
                        mock.call("squeue"),
                        mock.call("sacct"),
                        mock.call("sacct"),
                        mock.call("squeue"),
                    ],
                    which.call_args_list,
                )
            self.assertEqual("cancelled", cancelled["state"])

    def test_load_spec_backend_factory_and_worker_invocation_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "working"
            working.mkdir()
            spec = local_spec(working, command=[sys.executable, "-c", "pass"], outputs=[])
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec.to_dict()), encoding="utf-8")

            self.assertEqual(spec.fingerprint, compute_backends_module.load_spec(spec_path).fingerprint)
            self.assertIsInstance(compute_backends_module.backend_for("local", root / "local"), LocalBackend)
            self.assertIsInstance(compute_backends_module.backend_for("slurm", root / "slurm"), SlurmBackend)
            with self.assertRaisesRegex(ValueError, "unsupported backend: remote"):
                compute_backends_module.backend_for("remote", root / "remote")
            with self.assertRaisesRegex(ValueError, "invalid worker invocation"):
                compute_backends_module._worker_main(["wrong", str(root)])
            with self.assertRaisesRegex(ValueError, "invalid worker invocation"):
                compute_backends_module._worker_main(["_worker"])


if __name__ == "__main__":
    unittest.main()
