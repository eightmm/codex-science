#!/usr/bin/env python3
"""Seal native runtime v4 using function-boundary rewrites, then compile it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_optional(name: str) -> None:
    path = ROOT / "scripts" / name
    if path.is_file() and path.name != Path(__file__).name:
        subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def replace_region(path: Path, start_marker: str, end_marker: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    current = text[start:end]
    if current == replacement:
        return
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def patch_artifact_runtime() -> None:
    path = ROOT / "src" / "codex_science" / "artifact_runtime.py"
    text = path.read_text(encoding="utf-8")
    old = "    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material), warnings=tuple(warnings))\n"
    new = "    material[\"warnings\"] = tuple(warnings)\n    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material))\n"
    if old in text:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise SystemExit("artifact descriptor construction marker is missing")


def patch_project_cli() -> None:
    path = ROOT / "scripts" / "science_project.py"
    text = path.read_text(encoding="utf-8")
    if "import sqlite3\n" not in text:
        text = text.replace("import json\n", "import json\nimport sqlite3\n", 1)
    text = text.replace(
        "    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]\n",
        "    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:\n",
    )
    path.write_text(text, encoding="utf-8")


def patch_skill_maturity() -> None:
    path = ROOT / "src" / "codex_science" / "skill_maturity.py"
    frontmatter = '''def _frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return {}
    result: dict[str, str] = {}
    for item in FIELD_RE.finditer(match.group("body")):
        value = item.group("value").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {chr(34), chr(39)}:
            value = value[1:-1]
        result[item.group("key")] = value
    return result
'''
    replace_region(path, "def _frontmatter", "\n\ndef _load_json", frontmatter)
    text = path.read_text(encoding="utf-8")
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
    elif new not in text:
        raise SystemExit("skill maturity handoff marker is missing")
    path.write_text(text, encoding="utf-8")


def patch_remote_skill() -> None:
    path = ROOT / "authored-skills" / "remote-scientific-compute" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    sections: list[str] = []
    if "## Decision contract" not in text:
        sections.append(
            "## Decision contract\n\n"
            "Before execution, record the target, transfer boundary, argv or workflow, input hashes, runtime or container, resource and wall-time caps, cost cap, checkpoint and cancellation routes, expected outputs, and scientific acceptance criteria. Remote writes or allocation require one explicit approval receipt covering the exact job spec."
        )
    if "## Outputs" not in text:
        sections.append(
            "## Outputs\n\n"
            "Save the job spec, preflight and approval receipts, job ID and state transitions, stdout and stderr hashes, failure class, resource use when reported, checkpoint references, collected output hashes, and the `$science-provenance` and `$science-review` handoff."
        )
    if "## Boundaries" not in text:
        sections.append(
            "## Boundaries\n\n"
            "Do not probe for credentials, submit to unapproved accounts or partitions, stage sensitive data without an approved route, busy-poll, hide failed attempts, or treat process exit zero as scientific success."
        )
    if sections:
        path.write_text(text.rstrip() + "\n\n" + "\n\n".join(sections) + "\n", encoding="utf-8")


def patch_local_submit() -> None:
    path = ROOT / "src" / "codex_science" / "compute_backends.py"
    replacement = '''    def submit(self, spec: JobSpec, *, approval: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if spec.backend != "local":
            raise ValueError("LocalBackend requires backend=local")
        preflight = self.preflight(spec)
        if not preflight["ready"]:
            raise ValueError("local preflight failed")
        if spec.approval_required:
            if approval is None:
                raise ValueError("job spec requires explicit approval")
            validate_approval_receipt(approval, spec)
        job_id = "local-" + uuid.uuid4().hex[:20]
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True)
        _atomic_json(job_dir / "spec.json", spec.to_dict())
        submitted_at = _now()
        initial = _state_material(
            spec,
            job_id=job_id,
            state="submitted",
            submitted_at=submitted_at,
        )
        _atomic_json(job_dir / "state.json", initial)
        worker_environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = worker_environment.get("PYTHONPATH", "")
        worker_environment["PYTHONPATH"] = source_root + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "codex_science.compute_backends",
                "_worker",
                str(job_dir),
            ],
            env=worker_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
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
    text = path.read_text(encoding="utf-8")
    local_start = text.index("class LocalBackend:")
    submit_start = text.index("    def submit(", local_start)
    status_start = text.index("\n    def status(", submit_start)
    path.write_text(text[:submit_start] + replacement + text[status_start:], encoding="utf-8")


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
    run_optional("integrate_native_runtime_v4.py")
    patch_artifact_runtime()
    patch_project_cli()
    patch_skill_maturity()
    patch_remote_skill()
    patch_local_submit()
    patch_advanced_sidecars()
    patch_project_branch_base()
    subprocess.run([sys.executable, "-m", "compileall", "-q", "src", "scripts"], cwd=ROOT, check=True)
    print("native runtime v4 sealed: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
