#!/usr/bin/env python3
"""Apply all native runtime v4 integrations and correctness patches idempotently."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_optional(path: Path) -> None:
    if path.is_file():
        subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def patch_compute_submission() -> None:
    path = ROOT / "src" / "codex_science" / "compute_backends.py"
    text = path.read_text(encoding="utf-8")
    class_start = text.index("class LocalBackend:")
    submit_start = text.index("    def submit(", class_start)
    process_start = text.index("        process = subprocess.Popen(", submit_start)
    status_start = text.index("\n    def status(", process_start)
    section = text[process_start:status_start]
    if "return submitted_receipt" in section:
        return
    candidates = [index for token in ("\n        current = _read_json", "\n        state = _state_material") if (index := section.find(token)) >= 0]
    if not candidates:
        raise SystemExit("cannot locate LocalBackend submission receipt tail")
    tail_start = min(candidates)
    replacement = '''
        current = _read_json(job_dir / "state.json")
        # A short command may already have written running or terminal state.
        # Persist the PID only while the original submitted state is current,
        # but always return the historical submission receipt to the caller.
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
    new_section = section[:tail_start] + replacement
    path.write_text(text[:process_start] + new_section + text[status_start:], encoding="utf-8")


def patch_core_source() -> None:
    artifact = ROOT / "src" / "codex_science" / "artifact_runtime.py"
    text = artifact.read_text(encoding="utf-8")
    old = "    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material), warnings=tuple(warnings))\n"
    new = "    material[\"warnings\"] = tuple(warnings)\n    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material))\n"
    if old in text:
        artifact.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise SystemExit("artifact runtime descriptor construction marker is missing")

    cli = ROOT / "scripts" / "science_project.py"
    text = cli.read_text(encoding="utf-8")
    if "import sqlite3\n" not in text:
        text = text.replace("import json\n", "import json\nimport sqlite3\n", 1)
    text = text.replace(
        "    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]\n",
        "    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:\n",
    )
    cli.write_text(text, encoding="utf-8")

    maturity = ROOT / "src" / "codex_science" / "skill_maturity.py"
    text = maturity.read_text(encoding="utf-8")
    text = text.replace('    entries = payload.get("references")\n', '    entries = payload.get("references", payload.get("entries"))\n')
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
        raise SystemExit("skill maturity core handoff marker is missing")
    maturity.write_text(text, encoding="utf-8")


def main() -> int:
    run_optional(ROOT / "scripts" / "integrate_native_runtime_v4.py")
    run_optional(ROOT / "scripts" / "finalize_native_runtime_v4.py")
    patch_core_source()
    patch_compute_submission()
    print("complete native runtime v4 source: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
