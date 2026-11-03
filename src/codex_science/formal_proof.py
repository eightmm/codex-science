"""Bounded Lean proof verification and kernel-check receipts."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from codex_science.safe_expression import (
    _integer,
    _required_text,
    canonical_sha256,
)
from codex_science.math_contracts import build_proof_receipt, statement_sha256

# A word boundary cannot follow '?', so those alternatives end at the next non-word character.
ADMITTED_RE = re.compile(r"\b(sorry\b|sorryAx\b|admit\b|by_contra'\s*\?(?!\w)|exact\s*\?(?!\w))")
# Same-line [ \t] runs keep the MULTILINE scans linear on long runs of blank or modifier-only
# lines; a declaration split across lines still matches at the start of its keyword line.
DECLARATION_PREFIX = r"^[ \t]*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|nonrec)[ \t]+)*"
THEOREM_RE = re.compile(DECLARATION_PREFIX + r"(?:theorem|lemma|example)\b", re.MULTILINE)
AXIOM_RE = re.compile(DECLARATION_PREFIX + r"(axiom|opaque)\s+([A-Za-z0-9_'.]+)", re.MULTILINE)
UNSAFE_RE = re.compile(DECLARATION_PREFIX + r"unsafe\s+", re.MULTILINE)
MODULE_COMPONENT = r"(?:[^\W\d][\w']*|«[^»/\\\n]+»)"
IMPORT_RE = re.compile(r"(?<![\w.])import\s+(?:all\s+)?(" + MODULE_COMPONENT + r"(?:\." + MODULE_COMPONENT + r")*)")
# Lean reports admitted proofs elaborated from macros or tactics that the source scan cannot see.
OUTPUT_SORRY_RE = re.compile(r"declaration uses 'sorry'")
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 600
MAX_CAPTURE_CHARS = 16_000
# _version records these when the probe fails or prints nothing; neither identifies the checker.
UNKNOWN_VERSIONS = frozenset({"unavailable", "unknown"})

Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    killpg = getattr(os, "killpg", None)
    try:
        if killpg is not None:
            killpg(process.pid, signal.SIGKILL)
            return
    except ProcessLookupError:
        return
    except PermissionError:
        # macOS can refuse killpg for a group of zombies; still stop the direct child.
        pass
    process.kill()


def _default_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    # A separate session lets a timeout kill helper processes that the checker spawned.
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as drained:
                # A descendant that left the group can hold the pipes open; keep the bytes read so far.
                raise subprocess.TimeoutExpired(command, timeout, output=drained.output, stderr=drained.stderr) from None
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from None
        except BaseException:
            _kill_process_group(process)
            raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _safe_path(workspace: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("theorem_file must be a safe workspace-relative path")
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError("theorem_file escapes the workspace")
    if path.suffix != ".lean":
        raise ValueError("theorem_file must end in .lean")
    if not path.is_file():
        raise ValueError(f"theorem file is missing: {value}")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("theorem file exceeds the source-size limit")
    return path


def _command(workspace: Path, theorem_path: Path, mode: str) -> tuple[list[str], str]:
    relative = theorem_path.relative_to(workspace).as_posix()
    if mode not in {"auto", "lean", "lake"}:
        raise ValueError("command_mode must be auto, lean, or lake")
    has_lake = any((workspace / name).is_file() for name in ("lakefile.lean", "lakefile.toml", "lake-manifest.json"))
    selected = "lake" if mode == "auto" and has_lake else ("lean" if mode == "auto" else mode)
    if selected == "lake":
        return ["lake", "env", "lean", relative], selected
    return ["lean", relative], selected


def _version(command_mode: str, workspace: Path, runner: Runner) -> str:
    executable = "lake" if command_mode == "lake" else "lean"
    try:
        result = runner([executable, "--version"], workspace, 30)
    except (subprocess.TimeoutExpired, OSError):
        return "unavailable"
    text = (_text(result.stdout) or _text(result.stderr)).strip().splitlines()
    return text[0][:500] if text else "unknown"


def _assumptions(payload: Mapping[str, Any]) -> list[str]:
    value = payload.get("assumptions", [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("assumptions must be a list of non-empty strings")
    return list(value)


def _scan_workspace_imports(workspace: Path, theorem_path: Path, source: str) -> tuple[set[str], list[str], list[str]]:
    """Scan workspace-local modules imported by the theorem file, transitively.

    Returns admitted constructs found, files that contain them, and files that could
    not be scanned, including workspace entries that resolve outside the workspace.
    Imports with no .lean entry under the workspace root (for example Mathlib or Std)
    are not scanned.
    """
    admitted: set[str] = set()
    flagged: list[str] = []
    unscanned: list[str] = []
    visited = {theorem_path}
    pending = [source]
    while pending:
        for match in IMPORT_RE.finditer(pending.pop()):
            # Split on component boundaries, not raw dots: «a.b» names the single file a.b.lean.
            parts = [part[1:-1] if part.startswith("«") else part for part in re.findall(MODULE_COMPONENT, match.group(1))]
            if any(part in {"", ".", ".."} for part in parts):
                continue
            candidate = workspace.joinpath(*parts[:-1], parts[-1] + ".lean")
            if not os.path.lexists(candidate):
                continue
            relative = candidate.relative_to(workspace).as_posix()
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):
                resolved = None
            if resolved is None or not resolved.is_relative_to(workspace):
                # The workspace entry Lean would load leaves the workspace through a symlink.
                if relative not in unscanned:
                    unscanned.append(relative)
                continue
            if resolved in visited or not resolved.is_file():
                continue
            visited.add(resolved)
            relative = resolved.relative_to(workspace).as_posix()
            try:
                with resolved.open("rb") as handle:
                    data = handle.read(MAX_SOURCE_BYTES + 1)
            except OSError:
                unscanned.append(relative)
                continue
            if len(data) > MAX_SOURCE_BYTES:
                unscanned.append(relative)
                continue
            text = data.decode("utf-8", errors="replace")
            found = set(match.group(1) for match in ADMITTED_RE.finditer(text))
            if found:
                admitted |= found
                flagged.append(relative)
            pending.append(text)
    return admitted, sorted(flagged), sorted(unscanned)


def run_formal_proof_check(
    payload: Mapping[str, Any],
    *,
    workspace: Path,
    execute: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        raise ValueError("unsupported formal-proof-check input schema")
    check_id = _required_text(payload.get("check_id"), "check_id", error="check_id, receipt_id, claim_id, statement, and theorem_file are required")
    receipt_id = _required_text(payload.get("receipt_id"), "receipt_id", error="check_id, receipt_id, claim_id, statement, and theorem_file are required")
    claim_id = _required_text(payload.get("claim_id"), "claim_id", error="check_id, receipt_id, claim_id, statement, and theorem_file are required")
    statement = _required_text(payload.get("statement"), "statement", error="check_id, receipt_id, claim_id, statement, and theorem_file are required")
    theorem_file = _required_text(payload.get("theorem_file"), "theorem_file", error="check_id, receipt_id, claim_id, statement, and theorem_file are required")
    timeout = _integer(payload.get("timeout_seconds", 120), "timeout_seconds")
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    assumptions = _assumptions(payload)
    workspace = workspace.resolve()
    theorem_path = _safe_path(workspace, theorem_file)
    source_bytes = theorem_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source = source_bytes.decode("utf-8")
    source_admitted = set(match.group(1) for match in ADMITTED_RE.finditer(source))
    import_admitted, flagged_imports, unscanned_imports = _scan_workspace_imports(workspace, theorem_path, source)
    admitted = sorted(source_admitted | import_admitted)
    has_theorem = THEOREM_RE.search(source) is not None
    # Keep declaration trust-boundary checks conservative on the original source.
    axioms = sorted(set(match.group(2) for match in AXIOM_RE.finditer(source)))
    unsafe_declarations = len(UNSAFE_RE.findall(source))
    command, selected_mode = _command(workspace, theorem_path, str(payload.get("command_mode", "auto")))
    executable = command[0]
    available = shutil.which(executable) is not None
    preview: dict[str, Any] = {
        "schema_version": 1,
        "check_id": check_id,
        "claim_id": claim_id,
        "statement": statement,
        "statement_sha256": statement_sha256(statement),
        "theorem_file": theorem_path.relative_to(workspace).as_posix(),
        "theorem_file_sha256": source_sha256,
        "command": command,
        "command_mode": selected_mode,
        "timeout_seconds": timeout,
        "admitted_constructs": admitted,
        "declared_axioms": axioms,
        "unsafe_declaration_count": unsafe_declarations,
        "execute_requested": execute,
        "tool_available": available,
    }
    preview["preview_fingerprint"] = canonical_sha256(preview)
    if not execute:
        preview["status"] = "preview"
        return preview
    if not available:
        checker = {
            "tool": executable,
            "tool_version": "unavailable",
            "kernel_checked": False,
            "command": command,
            "exit_code": None,
            "stdout_sha256": None,
            "stderr_sha256": None,
        }
        receipt = build_proof_receipt(
            receipt_id=receipt_id,
            claim_id=claim_id,
            statement=statement,
            kind="formal-kernel",
            status="unavailable",
            assumptions=assumptions,
            checker=checker,
            evidence=[{"path": preview["theorem_file"], "sha256": source_sha256}],
            axioms=axioms,
            admitted_constructs=admitted,
            limitations=["Lean executable is unavailable in the selected workspace environment."],
        )
        return {**preview, "status": "unavailable", "proof_receipt": receipt}
    active_runner = runner or _default_runner
    tool_version = _version(selected_mode, workspace, active_runner)
    timed_out = False
    start_error = None
    try:
        completed = active_runner(command, workspace, timeout)
    except subprocess.TimeoutExpired as error:
        completed = subprocess.CompletedProcess(command, 124, error.stdout, error.stderr)
        timed_out = True
    except OSError as error:
        completed = subprocess.CompletedProcess(command, None, "", "")
        start_error = error
    stdout = _text(completed.stdout)
    stderr = _text(completed.stderr)
    try:
        source_unchanged = hashlib.sha256(theorem_path.read_bytes()).hexdigest() == source_sha256
    except OSError:
        source_unchanged = False
    output_admitted = OUTPUT_SORRY_RE.search(stdout) is not None or OUTPUT_SORRY_RE.search(stderr) is not None
    receipt_admitted = sorted(set(admitted) | ({"sorry"} if output_admitted else set()))
    passed = (
        completed.returncode == 0 and tool_version not in UNKNOWN_VERSIONS and not receipt_admitted and not unscanned_imports
        and source_unchanged and unsafe_declarations == 0 and has_theorem
    )
    checker = {
        "tool": executable,
        "tool_version": tool_version,
        "kernel_checked": passed,
        "command": command,
        "exit_code": completed.returncode,
        "timed_out": timed_out,
        "source_unchanged": source_unchanged,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_excerpt": stdout[-MAX_CAPTURE_CHARS:],
        "stderr_excerpt": stderr[-MAX_CAPTURE_CHARS:],
    }
    limitations: list[str] = []
    if not has_theorem:
        limitations.append("No theorem declaration was found (theorem, lemma, or example required).")
    if source_admitted:
        limitations.append("The source contains admitted or placeholder proof constructs.")
    for path in flagged_imports:
        limitations.append(f"The imported workspace module {path} contains admitted or placeholder proof constructs.")
    for path in unscanned_imports:
        limitations.append(f"The imported workspace module {path} could not be scanned (unreadable, over the source-size limit, or resolving outside the workspace).")
    if output_admitted:
        limitations.append("The checker output reports a declaration that uses 'sorry'.")
    if axioms:
        limitations.append("The source declares axioms or opaque constants that require an explicit trust-boundary review.")
    if unsafe_declarations:
        limitations.append("The source contains unsafe declarations.")
    if not source_unchanged:
        limitations.append("The theorem source changed during checking.")
    if timed_out:
        limitations.append("The checker exceeded the declared timeout.")
    if tool_version in UNKNOWN_VERSIONS:
        limitations.append("The checker version could not be determined.")
    if start_error is not None:
        limitations.append(f"The checker could not be started: {start_error}")
    receipt = build_proof_receipt(
        receipt_id=receipt_id,
        claim_id=claim_id,
        statement=statement,
        kind="formal-kernel",
        status="passed" if passed else "failed",
        assumptions=assumptions,
        checker=checker,
        evidence=[{"path": preview["theorem_file"], "sha256": source_sha256}],
        axioms=axioms,
        admitted_constructs=receipt_admitted,
        limitations=limitations,
    )
    return {**preview, "status": "passed" if passed else "failed", "proof_receipt": receipt}
