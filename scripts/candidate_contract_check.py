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


def validate_review(path: Path, label: str) -> None:
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("status") != "passed":
        raise SystemExit(f"candidate {label} acceptance review did not pass")


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
    run([python, "scripts/audit_skill_references.py", "--root", str(root), "--require-clean"], cwd=root)
    run([python, "-m", "compileall", "-q", "src", "scripts"], cwd=root)

    with tempfile.TemporaryDirectory() as tempdir:
        temporary = Path(tempdir)
        inventory = temporary / "inventory.json"
        maturity_json = temporary / "native-skill-quality.json"
        maturity_markdown = temporary / "native-skill-quality.md"
        run([python, "scripts/audit_skills.py", "--output", str(inventory)], cwd=root)
        if inventory.read_bytes() != (root / "catalog" / "inventory.json").read_bytes():
            raise SystemExit("candidate inventory is stale")
        run([python, "scripts/generate_wrappers.py", "--check"], cwd=root)
        run(
            [
                python,
                "scripts/audit_native_skill_maturity.py",
                "--output",
                str(maturity_json),
                "--markdown",
                str(maturity_markdown),
                "--require-clean",
            ],
            cwd=root,
        )
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
        sbdd_review = temporary / "sbdd-review.json"
        run(
            [
                python,
                "scripts/validate_artifact.py",
                str(sbdd_run / "manifest.json"),
                "--review-output",
                str(sbdd_review),
                "--require-passed-review",
            ],
            cwd=root,
        )
        validate_review(sbdd_review, "SBDD")

        quantitative_run = temporary / "quantitative-run"
        run(
            [
                python,
                "scripts/run_quantitative_acceptance.py",
                "examples/quantitative-research/input.json",
                str(quantitative_run),
            ],
            cwd=root,
        )
        quantitative_review = temporary / "quantitative-review.json"
        run(
            [
                python,
                "scripts/validate_artifact.py",
                str(quantitative_run / "manifest.json"),
                "--review-output",
                str(quantitative_review),
                "--require-passed-review",
            ],
            cwd=root,
        )
        validate_review(quantitative_review, "quantitative research")

    print("candidate contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
