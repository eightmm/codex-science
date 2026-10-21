"""Bounded multi-turn driver for an active Codex Science checkpoint."""
from __future__ import annotations

import json
import math
import tempfile
import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import literature_evaluation_runner as runner

RECEIPT_SCHEMA = "run-driver-receipt-v1"
STOP_CODES = {"terminal", "needs_human", "quick_answer", "turn_failed", "driver_error", "interrupted",
              "turn_cap", "wall_cap", "token_cap", "stalled"}
DEFAULT_CONTINUATION = ("Continue the active Codex Science run from its checkpoint next_action. "
                        "Do not restart, re-plan, or ask non-blocking questions. Stop only at completion, "
                        "an approval gate, or a genuine blocker.")
_TERMINAL = {"completed", "terminal_inconclusive", "abandoned"}
_HUMAN = {"approval_required", "waiting_external", "blocked", "stale_active", "invalid"}
_KILL_WAIT_SECONDS = 0.25
_READER_JOIN_SECONDS = 0.25
_MAX_LINE_BYTES = 1 << 20
_MAX_OUTPUT_BYTES = 64 << 20
_OUTPUT_MARKER = b"\n[output truncated: line limit exceeded]\n"


def _report(project: Path) -> dict[str, Any]:
    return runner._completion_report(project / "artifacts", now=datetime.now(timezone.utc))


def _snapshot_runs(artifacts: Path) -> dict[str, dict[str, Any]]:
    """Capture direct run checkpoint identity without trusting report ordering."""
    snapshot: dict[str, dict[str, Any]] = {}
    if not artifacts.is_dir() or artifacts.is_symlink():
        return snapshot
    for run_dir in artifacts.iterdir():
        if run_dir.is_symlink() or not run_dir.is_dir():
            continue
        checkpoint_path = run_dir / "checkpoint.json"
        if checkpoint_path.is_symlink() or not checkpoint_path.is_file():
            continue
        try:
            record = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if isinstance(record, dict):
            relative_path = run_dir.relative_to(artifacts).as_posix()
            snapshot[relative_path] = {key: record.get(key) for key in ("revision", "updated_at", "state")}
    return snapshot


def _timestamp_key(value: Any) -> tuple[float, str]:
    if isinstance(value, str):
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            return stamp, value
        except (ValueError, OverflowError, OSError):
            return float("-inf"), value
    return float("-inf"), ""


def _selected_run(report: dict[str, Any], baseline: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    changed = [path for path, identity in current.items() if baseline.get(path) != identity]
    if not changed:
        return None
    run_path = max(changed, key=lambda path: (_timestamp_key(current[path].get("updated_at")), path))
    run_id = Path(run_path).name
    return next((row for row in report.get("runs", []) if row.get("run_id") == run_id),
                {"run_id": run_id, "outcome": "invalid", "stop_reason": {"code": "invalid_record"}})


def _signature(run: dict[str, Any] | None, artifacts: Path) -> tuple[Any, ...]:
    if run is None:
        return (None, None, None, None)
    run_id = run.get("run_id")
    record: dict[str, Any] = {}
    if isinstance(run_id, str):
        try:
            value = json.loads((artifacts / run_id / "checkpoint.json").read_text(encoding="utf-8"))
            if isinstance(value, dict):
                record = value
        except (OSError, UnicodeError, ValueError):
            pass
    return run_id, record.get("revision"), run.get("steps_completed"), run.get("steps_total")


def _argv(codex: str, project: Path, prompt: str, last: Path, thread_id: str | None = None) -> list[str]:
    if prompt.startswith("-"):
        raise ValueError("prompts beginning with '-' are unsupported by this Codex CLI; use a prompt file with a non-dash-leading prompt")
    args = [codex, "exec"]
    if thread_id:
        args += ["resume", thread_id]
    args += ["--json", "-o", str(last), "-c", 'sandbox_mode="workspace-write"',
             "-c", "sandbox_workspace_write.network_access=true", "-c", 'approval_policy="never"',
             "-c", 'approvals_reviewer="user"', prompt]
    # Resume does not accept -s or -C, so each process runs with cwd=project.
    return args


def _resolve_paths(project: Path, run_dir: Path) -> tuple[Path, Path]:
    project = Path(project).expanduser().resolve()
    requested = Path(os.path.abspath(Path(run_dir).expanduser()))
    if requested.is_symlink():
        raise ValueError("output directory is a symlink")
    run_dir = requested.resolve()
    artifact_roots = {Path(os.path.abspath(project / "artifacts")), (project / "artifacts").resolve()}
    for candidate in {requested, run_dir}:
        for artifacts in artifact_roots:
            try:
                candidate.relative_to(artifacts)
            except ValueError:
                continue
            raise ValueError("output directory cannot be inside project artifacts")
    return project, run_dir


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _create_private(path: Path, *, binary: bool = False):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    return os.fdopen(fd, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"}))


def _count_truncated_lines(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                count += json.loads(line).get("line_truncated") is True
            except (json.JSONDecodeError, AttributeError):
                continue
    return count


def _run_turn(argv: list[str], project: Path, directory: Path, timeout: float, *, event_stream=None,
              codex_home: Path | None = None) -> tuple[list[dict[str, Any]], int | None, bool, str | None, float, bool]:
    started = time.monotonic()
    timed_out = False
    launch_error = None
    events: list[dict[str, Any]] = []
    exit_code: int | None = None
    process = None
    reader = None
    reader_started = False
    reader_abandoned = False
    stdout_done = False
    kill_requested = False
    output_capped = threading.Event()
    stop_reader = threading.Event()
    total_bytes = [0]
    byte_lock = threading.Lock()

    def account(size: int) -> int:
        with byte_lock:
            available = max(0, _MAX_OUTPUT_BYTES - total_bytes[0])
            total_bytes[0] += size
            if size > available:
                output_capped.set()
            return available

    def kill_and_wait() -> None:
        nonlocal kill_requested
        if process is None:
            return
        kill_requested = True
        try:
            runner._kill_process_group(process)
        except OSError:
            pass
        try:
            process.wait(timeout=_KILL_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                runner._kill_process_group(process)
            except OSError:
                pass
            try:
                process.wait(timeout=_KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                pass

    try:
        stderr_path = directory / "stderr.log"
        if stderr_path.is_symlink() or stderr_path.exists():
            raise FileExistsError("turn stderr.log already exists or is a symlink")
        stderr_stream = _create_private(stderr_path, binary=True)
        if "-o" in argv:
            last_path = Path(argv[argv.index("-o") + 1])
            if last_path.is_symlink() or last_path.exists():
                raise FileExistsError("turn last-message file already exists or is a symlink")
            _create_private(last_path).close()
        try:
            child_env = os.environ.copy()
            if codex_home is not None:
                child_env["CODEX_HOME"] = str(codex_home.absolute())
            process = subprocess.Popen(argv, cwd=project, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True, env=child_env)
        except OSError as error:
            launch_error = str(error)
            stderr_stream.write((launch_error + "\n").encode("utf-8", errors="replace"))

        if process is not None:
            assert process.stdout is not None
            lines: queue.Queue[tuple[float, bytes | None, bool]] = queue.Queue(maxsize=16)

            def capture_stdout() -> None:
                try:
                    while not stop_reader.is_set():
                        line = process.stdout.readline(_MAX_LINE_BYTES + 1)
                        if not line:
                            break
                        available = account(len(line))
                        too_long = len(line) > _MAX_LINE_BYTES and not line.endswith(b"\n")
                        if too_long:
                            prefix = line[:_MAX_LINE_BYTES]
                            while line and not line.endswith(b"\n") and not output_capped.is_set():
                                line = process.stdout.readline(_MAX_LINE_BYTES + 1)
                                if line:
                                    account(len(line))
                            line = prefix + _OUTPUT_MARKER
                        payload = line[:min(len(line), available)]
                        if payload:
                            runner._queue_put_until_stopped(
                                lines, (time.monotonic(), payload, too_long), stop_reader)
                except (OSError, ValueError):
                    pass
                finally:
                    runner._queue_put_until_stopped(lines, (time.monotonic(), None, False), stop_reader)

            def capture_stderr() -> None:
                assert process is not None and process.stderr is not None
                while not stop_reader.is_set():
                    chunk = process.stderr.read(65536)
                    if not chunk:
                        break
                    available = account(len(chunk))
                    if available:
                        try:
                            stderr_stream.write(chunk[:available])
                        except (OSError, ValueError):
                            return

            reader = threading.Thread(target=capture_stdout, name="codex-driver-event-reader", daemon=True)
            reader.start()
            if getattr(process, "stderr", None) is not None:
                stderr_reader = threading.Thread(target=capture_stderr, name="codex-driver-stderr-reader", daemon=True)
                stderr_reader.start()
            reader_started = True
            deadline = started + timeout
            killed_at = None
            while not stdout_done or process.poll() is None:
                now = time.monotonic()
                if (output_capped.is_set() or (not timed_out and now >= deadline and (process.poll() is None or not stdout_done))) and killed_at is None:
                    if output_capped.is_set():
                        launch_error = "output_cap"
                    else:
                        timed_out = True
                    killed_at = now
                    kill_and_wait()
                if killed_at is not None and time.monotonic() >= killed_at + _READER_JOIN_SECONDS:
                    break
                try:
                    arrived, line, line_truncated = lines.get(timeout=0.05)
                except queue.Empty:
                    continue
                if line is None:
                    stdout_done = True
                    continue
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                try:
                    event: Any = json.loads(text)
                except json.JSONDecodeError:
                    event = text
                record = {"t": round(max(0.0, arrived - started), 6), "event": event,
                          "line_truncated": line_truncated}
                if event_stream is None:
                    events.append(record)
                else:
                    event_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    event_stream.flush()
            exit_code = process.returncode
    except BaseException:
        # A signal or parser/read error must not leave the Codex process group running.
        kill_and_wait()
        raise
    finally:
        if process is not None and process.poll() is None:
            kill_and_wait()
        if reader_started and reader is not None:
            reader.join(timeout=_READER_JOIN_SECONDS)
            reader_abandoned = reader.is_alive()
        stop_reader.set()
        stderr_thread = locals().get("stderr_reader")
        if stderr_thread is not None:
            stderr_thread.join(timeout=_READER_JOIN_SECONDS)
        if output_capped.is_set():
            launch_error = "output_cap"
        if kill_requested and process is not None and not reader_abandoned:
            try:
                process.communicate(timeout=_KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                kill_and_wait()
                try:
                    process.communicate(timeout=_KILL_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
        # Close only after the reader ended; closing a stream under a blocked readline can deadlock.
        if process is not None and process.stdout is not None and not reader_abandoned:
            try:
                process.stdout.close()
            except (OSError, ValueError):
                pass
        if process is not None and getattr(process, "stderr", None) is not None and stderr_thread is not None and not stderr_thread.is_alive():
            try:
                process.stderr.close()
            except (OSError, ValueError):
                pass
        if ('stderr_stream' in locals() and not stderr_stream.closed
                and (stderr_thread is None or not stderr_thread.is_alive())):
            stderr_stream.close()
    return events, exit_code, timed_out, launch_error, time.monotonic() - started, reader_abandoned


def _usage_total(metrics: dict[str, Any]) -> int:
    usage = metrics.get("usage", {})
    return sum(value for key, value in usage.items() if key in {"input_tokens", "output_tokens"}
               and isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def drive(project: Path, prompt: str, *, run_dir: Path, codex_bin: str = "codex", max_turns: int = 6,
          wall_seconds: float = 1800, max_total_tokens: int | None = None,
          continuation_prompt: str = DEFAULT_CONTINUATION, codex_home: Path | None = None) -> dict[str, Any]:
    project, run_dir = _resolve_paths(project, run_dir)
    _validate_caps(max_turns, wall_seconds, max_total_tokens)
    for name, value in (("prompt", prompt), ("continuation_prompt", continuation_prompt)):
        if value.startswith("-"):
            raise ValueError(f"{name} beginning with '-' is unsupported by this Codex CLI; use a non-dash-leading prompt")
    existing_turn = next((run_dir / f"turn-{number}" for number in range(1, max_turns + 1)
                          if (run_dir / f"turn-{number}").exists()
                          or (run_dir / f"turn-{number}").is_symlink()), None)
    if existing_turn is not None:
        raise FileExistsError(f"turn directory already exists or is a symlink: {existing_turn.name}")
    receipt_path = run_dir / "run-driver-receipt.json"
    if run_dir.is_symlink() or receipt_path.exists() or receipt_path.is_symlink():
        raise FileExistsError(
            f"output directory already contains run-driver-receipt.json; choose a new --out directory: {run_dir}"
        )
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        receipt_fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError as error:
        raise FileExistsError(
            f"output directory already contains run-driver-receipt.json; choose a new --out directory: {run_dir}"
        ) from error
    else:
        os.close(receipt_fd)

    artifacts = project / "artifacts"
    turns: list[dict[str, Any]] = []
    raw_token_totals: list[int] = []
    tokens_counted = 0
    thread_id = None
    previous_signature: tuple[Any, ...] | None = (None, None, None, None)
    no_progress_turns = 0
    stop = {"code": "turn_cap"}
    preflight: dict[str, Any] = {}
    report: dict[str, Any] = {"schema": "completion-report-v1", "runs": []}

    def make_receipt() -> dict[str, Any]:
        # Receipts/logs are 0600; output caps use launch_error/stop reason "output_cap"; child CODEX_HOME is absolute.
        # The receipt records only the home kind, not its path.
        return {"schema": RECEIPT_SCHEMA, "stop": stop, "turns": turns,
                "completion_report": report, "usage_mode_observed": "unverified",
                "raw_token_totals": raw_token_totals, "tokens_counted": tokens_counted,
                # Keep the original receipt field as a compatibility alias for the conservative sum.
                "token_total": tokens_counted, "preflight": preflight,
                "codex_home_kind": "explicit" if codex_home is not None else "ambient"}

    try:
        effective_home = runner._codex_home(codex_home)
        preflight = runner._preflight(codex_bin, effective_home)
        baseline_runs = _snapshot_runs(artifacts)
        initial_hashes = runner._artifact_hashes(artifacts)
        prior_hashes = initial_hashes
        report = _report(project)
        baseline_has_active_run = any(row.get("outcome") == "active" for row in report.get("runs", []))
        started = time.monotonic()

        for number in range(1, max_turns + 1):
            remaining = wall_seconds - (time.monotonic() - started)
            if remaining <= 0:
                stop = {"code": "wall_cap"}
                break
            directory = run_dir / f"turn-{number}"
            if directory.exists() or directory.is_symlink():
                raise FileExistsError(f"turn directory already exists or is a symlink: {directory.name}")
            directory.mkdir(mode=0o700)
            last = directory / "last.md"
            argv = _argv(codex_bin, project, prompt if number == 1 else continuation_prompt, last,
                         thread_id if number > 1 else None)
            events_path = directory / "events.jsonl"
            with _create_private(events_path) as event_stream:
                _, exit_code, timed_out, launch_error, wall, reader_abandoned = _run_turn(
                    argv, project, directory, remaining, event_stream=event_stream, codex_home=effective_home)
            if not last.exists():
                with _create_private(last):
                    pass
            with (directory / "events.jsonl").open(encoding="utf-8") as stream:
                metrics = runner.parse_exec_events(stream, exit_code=exit_code, timed_out=timed_out, wall_seconds=wall)
            if thread_id is None:
                thread_id = metrics.get("thread_id")

            reported_tokens = _usage_total(metrics)
            # Resume usage semantics are unverified, so summing every invocation total is conservative
            # and may overcount if Codex reports cumulative thread usage on resume.
            raw_token_totals.append(reported_tokens)
            tokens_counted += reported_tokens

            report = _report(project)
            current_runs = _snapshot_runs(artifacts)
            selected = _selected_run(report, baseline_runs, current_runs)
            changed_checkpoint_paths = {path for path in baseline_runs.keys() | current_runs.keys()
                                        if baseline_runs.get(path) != current_runs.get(path)}
            outcome = selected.get("outcome") if selected else None
            after_hashes = runner._artifact_hashes(artifacts)
            signature = _signature(selected, artifacts)
            progressed = signature != previous_signature or after_hashes != prior_hashes
            no_progress_turns = 0 if progressed else no_progress_turns + 1
            turns.append({"turn": number, "argv": argv, "exit_code": exit_code,
                          "stop_reason": metrics["terminal_stop_reason"], "metrics": metrics,
                          "truncated_lines": _count_truncated_lines(events_path),
                          "wall_seconds": wall, "token_delta": reported_tokens,
                          "raw_token_total": reported_tokens, "tokens_counted": tokens_counted,
                          "usage_mode_observed": "unverified", "reader_abandoned": reader_abandoned,
                          "launch_error": launch_error})
            prior_hashes = after_hashes

            if launch_error == "output_cap":
                stop = {"code": "turn_failed", "reason": "output_cap"}
                break
            if launch_error is not None:
                stop = {"code": "turn_failed", "reason": "launch_error"}
                break
            if timed_out:
                stop = {"code": "wall_cap"}
                break
            if metrics["terminal_stop_reason"] == "failed" or (number == 1 and thread_id is None):
                stop = {"code": "turn_failed"}
                break
            if metrics["terminal_stop_reason"] == "interrupted":
                stop = {"code": "interrupted"}
                break
            if outcome in _TERMINAL:
                stop = {"code": "terminal", "reason": outcome}
                break
            if outcome in _HUMAN:
                stop = {"code": "needs_human", "reason": "invalid_record" if outcome == "invalid" else selected.get("stop_reason", {}).get("code", outcome)}
                break
            if (not baseline_has_active_run and selected is None and not changed_checkpoint_paths
                    and after_hashes == initial_hashes and last.read_text(encoding="utf-8").strip()):
                stop = {"code": "quick_answer"}
                break
            if no_progress_turns >= 2:
                stop = {"code": "stalled"}
                break
            if max_total_tokens is not None and tokens_counted >= max_total_tokens:
                stop = {"code": "token_cap"}
                break
            if time.monotonic() - started >= wall_seconds:
                stop = {"code": "wall_cap"}
                break
            if number == max_turns:
                stop = {"code": "turn_cap"}
                break
            previous_signature = signature
        receipt = make_receipt()
        _write_receipt(receipt_path, receipt)
        return receipt
    except (KeyboardInterrupt, SystemExit):
        stop = {"code": "interrupted"}
        _write_receipt(receipt_path, make_receipt())
        raise
    except BaseException as error:
        stop = {"code": "driver_error", "error": f"{type(error).__name__}: {error}"}
        _write_receipt(receipt_path, make_receipt())
        raise


def _validate_caps(max_turns: int, wall_seconds: float, max_total_tokens: int | None) -> None:
    if (isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1
            or isinstance(wall_seconds, bool) or not isinstance(wall_seconds, (int, float))
            or not math.isfinite(wall_seconds) or wall_seconds <= 0
            or (max_total_tokens is not None and (isinstance(max_total_tokens, bool)
                or not isinstance(max_total_tokens, int) or max_total_tokens < 0))):
        raise ValueError("turn and wall caps must be positive; token cap must be non-negative")
