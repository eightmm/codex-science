#!/usr/bin/env python3
"""Idempotent final correctness patches for native runtime v4."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_if_present(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected patch marker missing: {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    integration = ROOT / "scripts" / "integrate_native_runtime_v4.py"
    if integration.is_file():
        subprocess.run([sys.executable, str(integration)], cwd=ROOT, check=True)

    artifact_runtime = ROOT / "src" / "codex_science" / "artifact_runtime.py"
    replace_if_present(
        artifact_runtime,
        "    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material), warnings=tuple(warnings))\n",
        "    material[\"warnings\"] = tuple(warnings)\n    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material))\n",
    )

    project_cli = ROOT / "scripts" / "science_project.py"
    text = project_cli.read_text(encoding="utf-8")
    if "import sqlite3\n" not in text:
        text = text.replace("import json\n", "import json\nimport sqlite3\n", 1)
    text = text.replace(
        "    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]\n",
        "    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:\n",
    )
    project_cli.write_text(text, encoding="utf-8")

    maturity = ROOT / "src" / "codex_science" / "skill_maturity.py"
    text = maturity.read_text(encoding="utf-8")
    text = text.replace(
        '    entries = payload.get("references")\n',
        '    entries = payload.get("references", payload.get("entries"))\n',
    )
    old = '''    has_provenance = "$science-provenance" in text or skill_dir.name == "science-provenance"
    has_review = "$science-review" in text or skill_dir.name == "science-review"
'''
    new = '''    if skill_dir.name in CORE_SECTION_ALIASES:
        # The three core skills collectively implement the provenance/review
        # handoff; do not require them to invoke themselves by token.
        has_provenance = True
        has_review = True
    else:
        has_provenance = "$science-provenance" in text
        has_review = "$science-review" in text
'''
    if new not in text:
        if old not in text:
            raise SystemExit("skill maturity handoff marker is missing")
        text = text.replace(old, new, 1)
    maturity.write_text(text, encoding="utf-8")

    compute = ROOT / "src" / "codex_science" / "compute_backends.py"
    text = compute.read_text(encoding="utf-8")
    old = '''        state = _state_material(spec, job_id=job_id, state="submitted", submitted_at=submitted_at, worker_pid=process.pid, message="local worker started")
        _atomic_json(job_dir / "state.json", state)
        return state
'''
    new = '''        current = _read_json(job_dir / "state.json")
        # A short command may already have written running or terminal state.
        # Add the PID only while the original submitted state is still current;
        # never overwrite a newer worker receipt.
        if current.get("state") == "submitted":
            state = _state_material(
                spec,
                job_id=job_id,
                state="submitted",
                submitted_at=submitted_at,
                worker_pid=process.pid,
                message="local worker started",
            )
            _atomic_json(job_dir / "state.json", state)
        else:
            state = current
        return state
'''
    if new not in text:
        if old not in text:
            raise SystemExit("local submit race marker is missing")
        text = text.replace(old, new, 1)
    compute.write_text(text, encoding="utf-8")

    print("native runtime v4 finalization: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
