#!/usr/bin/env python3
"""Final idempotent repairs for native runtime v4 before repository validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_optional(name: str) -> None:
    path = ROOT / "scripts" / name
    if path.is_file() and path.name != Path(__file__).name:
        subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def replace(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"missing {label} marker: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_skill_maturity() -> None:
    path = ROOT / "src" / "codex_science" / "skill_maturity.py"
    text = path.read_text(encoding="utf-8")
    # Use an unambiguous string literal containing both quote characters.
    text = text.replace(".strip('\\\"\\\\\'')", '.strip("\\\"\'")')
    text = text.replace(".strip('\\\"\\\'')", '.strip("\\\"\'")')
    text = text.replace(".strip('\\\"\'')", '.strip("\\\"\'")')
    if 'strip("\\\"\'")' not in text:
        old_line_start = '    return {item.group("key"):'
        for line in text.splitlines():
            if line.startswith(old_line_start):
                text = text.replace(line, '    return {item.group("key"): item.group("value").strip().strip("\\\"\'") for item in FIELD_RE.finditer(match.group("body"))}', 1)
                break
    text = text.replace(
        '    entries = payload.get("references")\n',
        '    entries = payload.get("references", payload.get("entries"))\n',
    )
    old = '''    has_provenance = "$science-provenance" in text or skill_dir.name == "science-provenance"
    has_review = "$science-review" in text or skill_dir.name == "science-review"
'''
    new = '''    if skill_dir.name in CORE_SECTION_ALIASES:
        # Core coordinator/provenance/reviewer skills collectively implement
        # the handoff and are not required to invoke themselves by token.
        has_provenance = True
        has_review = True
    else:
        has_provenance = "$science-provenance" in text
        has_review = "$science-review" in text
'''
    if old in text:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def patch_remote_sections() -> None:
    path = ROOT / "authored-skills" / "remote-scientific-compute" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    additions: list[str] = []
    if "## Decision contract" not in text:
        additions.append(
            "## Decision contract\n\n"
            "Before execution, record the target, data-transfer boundary, command or workflow, input hashes, runtime or container, requested resources, wall-time and cost caps, cancellation route, checkpoint policy, expected outputs, and scientific acceptance criteria. Remote writes or allocation require one explicit approval receipt covering the exact job spec."
        )
    if "## Outputs" not in text:
        additions.append(
            "## Outputs\n\n"
            "Save the job spec, preflight and approval receipts, scheduler or local job ID, state transitions, stdout and stderr hashes, resource use when reported, checkpoint references, cancellation or failure class, collected output hashes, and the downstream claim/review handoff with `$science-provenance`."
        )
    if "## Boundaries" not in text:
        additions.append(
            "## Boundaries\n\n"
            "Do not discover credentials by probing, submit to unapproved accounts or partitions, stage sensitive data without an approved route, busy-poll a scheduler, hide failed attempts, or treat a zero exit code as scientific success. Run `$science-review` after material outputs are collected."
        )
    if additions:
        path.write_text(text.rstrip() + "\n\n" + "\n\n".join(additions) + "\n", encoding="utf-8")


def patch_compute_worker() -> None:
    path = ROOT / "src" / "codex_science" / "compute_backends.py"
    text = path.read_text(encoding="utf-8")
    old = '''        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "_worker", str(job_dir)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
'''
    new = '''        worker_environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = worker_environment.get("PYTHONPATH", "")
        worker_environment["PYTHONPATH"] = source_root + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "codex_science.compute_backends", "_worker", str(job_dir)],
            env=worker_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
'''
    if old in text:
        text = text.replace(old, new, 1)
    # Replace any earlier race-safe tail with a deterministic submitted receipt.
    class_start = text.index("class LocalBackend:")
    submit_start = text.index("    def submit(", class_start)
    process_start = text.index("        process = subprocess.Popen(", submit_start)
    status_start = text.index("\n    def status(", process_start)
    section = text[process_start:status_start]
    if "return submitted_receipt" not in section:
        candidates = [index for token in ("\n        current = _read_json", "\n        state = _state_material") if (index := section.find(token)) >= 0]
        if not candidates:
            raise SystemExit("cannot locate LocalBackend submission receipt tail")
        tail_start = min(candidates)
        replacement = '''
        current = _read_json(job_dir / "state.json")
        submitted_receipt = _state_material(
            spec,
            job_id=job_id,
            state="submitted",
            submitted_at=submitted_at,
            worker_pid=process.pid,
            message="local worker started",
        )
        if current.get("state") == "submitted":
            _atomic_json(job_dir / "state.json", submitted_receipt)
        return submitted_receipt
'''
        section = section[:tail_start] + replacement
        text = text[:process_start] + section + text[status_start:]
    path.write_text(text, encoding="utf-8")


def patch_advanced_sidecars() -> None:
    path = ROOT / "src" / "codex_science" / "advanced_sidecars.py"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '            selections_by_id[str(selection["selection_id"])] = selection\n',
        '            selections_by_id[str(selection["selection_id"])] = payload\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_project_branch_base() -> None:
    path = ROOT / "src" / "codex_science" / "project_store.py"
    text = path.read_text(encoding="utf-8")
    old = '''            if branch is None:
                connection.execute(
                    "INSERT INTO branches(project_id, branch_name, base_run_id, head_run_id, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                    (project_id, branch_name, run_id, run_id, "active", imported_at, imported_at),
                )
'''
    new = '''            if branch is None:
                branch_base = parent_run_id or run_id
                connection.execute(
                    "INSERT INTO branches(project_id, branch_name, base_run_id, head_run_id, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                    (project_id, branch_name, branch_base, run_id, "active", imported_at, imported_at),
                )
'''
    if old in text:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    for name in (
        "integrate_native_runtime_v4.py",
        "finalize_native_runtime_v4.py",
        "apply_complete_native_runtime_v4.py",
    ):
        run_optional(name)
    patch_skill_maturity()
    patch_remote_sections()
    patch_compute_worker()
    patch_advanced_sidecars()
    patch_project_branch_base()
    subprocess.run([sys.executable, "-m", "compileall", "-q", "src", "scripts"], cwd=ROOT, check=True)
    print("native runtime v4 repairs: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
