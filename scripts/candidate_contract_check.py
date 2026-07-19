#!/usr/bin/env python3
"""Run bounded deterministic checks required before installing a candidate release."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=os.environ.copy())
    if completed.returncode != 0:
        detail = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        raise SystemExit(f"candidate check failed: {' '.join(command)}\n{detail}")
    if completed.stdout.strip():
        print(completed.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    python = sys.executable
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(root / "src") + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    run([python, "scripts/validate_release.py", "--root", str(root)], cwd=root)
    run([python, "scripts/validate_connector_contracts.py", "--root", str(root)], cwd=root)
    run([python, "-m", "compileall", "-q", "src", "scripts"], cwd=root)

    with tempfile.TemporaryDirectory() as tempdir:
        temporary = Path(tempdir)
        inventory = temporary / "inventory.json"
        run([python, "scripts/audit_skills.py", "--output", str(inventory)], cwd=root)
        if inventory.read_bytes() != (root / "catalog" / "inventory.json").read_bytes():
            raise SystemExit("candidate inventory is stale")
        run([python, "scripts/generate_wrappers.py", "--check"], cwd=root)
        run([python, "scripts/validate_models.py"], cwd=root)
        run([python, "scripts/validate_model_registry_v2.py"], cwd=root)
        run([python, "scripts/run_reviewer_benchmark.py", "--require-safe"], cwd=root)

        sbdd_run = temporary / "sbdd-run"
        run(
            [
                python,
                "scripts/run_sbdd_acceptance.py",
                "examples/sbdd-executable/input.json",
                str(sbdd_run),
                "--registry",
                "models/registry-v2.json",
            ],
            cwd=root,
        )
        review_output = temporary / "sbdd-review.json"
        run(
            [
                python,
                "scripts/validate_artifact.py",
                str(sbdd_run / "manifest.json"),
                "--review-output",
                str(review_output),
                "--require-passed-review",
            ],
            cwd=root,
        )
        review = json.loads(review_output.read_text(encoding="utf-8"))
        if review.get("status") != "passed":
            raise SystemExit("candidate SBDD acceptance review did not pass")

    print("candidate contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
