"""Bounded Lean proof verification and kernel-check receipts."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from codex_science.math_contracts import build_proof_receipt, statement_sha256
from codex_science.safe_expression import canonical_sha256

ADMITTED_RE = re.compile(r"\b(sorry|admit|by_contra'\s*\?|exact\s*\?)\b")
AXIOM_RE = re.compile(r"^\s*(axiom|opaque)\s+([A-Za-z0-9_'.]+)", re.MULTILINE)
UNSAFE_RE = re.compile(r"^\s*unsafe\s+", re.MULTILINE)
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 600
MAX_CAPTURE_CHARS = 16_000

Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def _default_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


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
    result = runner([executable, "--version"], workspace, 30)
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0][:500] if text else "unknown"


def run_formal_proof_check(
    payload: Mapping[str, Any],
    *,
    workspace: Path,
    execute: bool = True,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported formal-proof-check input schema")
    check_id = str(payload.get("check_id", "")).strip()
    receipt_id = str(payload.get("receipt_id", "")).strip()
    claim_id = str(payload.get("claim_id", "")).strip()
    statement = str(payload.get("statement", "")).strip()
    theorem_file = str(payload.get("theorem_file", "")).strip()
    if not check_id or not receipt_id or not claim_id or not statement or not theorem_file:
        raise ValueError("check_id, receipt_id, claim_id, statement, and theorem_file are required")
    timeout = int(payload.get("timeout_seconds", 120))
    if isinstance(payload.get("timeout_seconds"), bool) or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    workspace = workspace.resolve()
    theorem_path = _safe_path(workspace, theorem_file)
    source = theorem_path.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    admitted = sorted(set(match.group(1) for match in ADMITTED_RE.finditer(source)))
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
            assumptions=list(map(str, payload.get("assumptions", []))),
            checker=checker,
            evidence=[{"path": preview["theorem_file"], "sha256": source_sha256}],
            axioms=axioms,
            admitted_constructs=admitted,
            limitations=["Lean executable is unavailable in the selected workspace environment."],
        )
        return {**preview, "status": "unavailable", "proof_receipt": receipt}
    active_runner = runner or _default_runner
    try:
        tool_version = _version(selected_mode, workspace, active_runner)
        completed = active_runner(command, workspace, timeout)
        timed_out = False
    except subprocess.TimeoutExpired as error:
        completed = subprocess.CompletedProcess(command, 124, error.stdout or "", error.stderr or "")
        tool_version = _version(selected_mode, workspace, active_runner)
        timed_out = True
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    current_sha256 = hashlib.sha256(theorem_path.read_bytes()).hexdigest()
    source_unchanged = current_sha256 == source_sha256
    passed = completed.returncode == 0 and not admitted and source_unchanged and unsafe_declarations == 0
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
    if admitted:
        limitations.append("The source contains admitted or placeholder proof constructs.")
    if axioms:
        limitations.append("The source declares axioms or opaque constants that require an explicit trust-boundary review.")
    if unsafe_declarations:
        limitations.append("The source contains unsafe declarations.")
    if not source_unchanged:
        limitations.append("The theorem source changed during checking.")
    if timed_out:
        limitations.append("The checker exceeded the declared timeout.")
    receipt = build_proof_receipt(
        receipt_id=receipt_id,
        claim_id=claim_id,
        statement=statement,
        kind="formal-kernel",
        status="passed" if passed else "failed",
        assumptions=list(map(str, payload.get("assumptions", []))),
        checker=checker,
        evidence=[{"path": preview["theorem_file"], "sha256": source_sha256}],
        axioms=axioms,
        admitted_constructs=admitted,
        limitations=limitations,
    )
    return {**preview, "status": "passed" if passed else "failed", "proof_receipt": receipt}
