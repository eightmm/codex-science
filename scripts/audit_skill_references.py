#!/usr/bin/env python3
"""Audit progressive-disclosure reference contracts for first-party skills."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import write_text_atomic  # noqa: E402
from codex_science.reference_contract import audit_reference_roots  # noqa: E402

STRICT_SKILLS = {
    "codex-science",
    "science-provenance",
    "science-review",
    "literature-review",
    "docking-validation",
    "remote-scientific-compute",
    "statistical-decision-analysis",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="existing repository directory to audit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true", help="require at least one audited skill and no major findings")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError(f"root must be an existing directory: {args.root}")
        report = audit_reference_roots(
            [root / "runtime-skills", root / "authored-skills"],
            strict_names=STRICT_SKILLS,
        )
        if args.require_clean and report["summary"]["skills"] == 0:
            raise ValueError("no skills audited; --require-clean requires at least one skill")
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            write_text_atomic(args.output, text)
        else:
            print(text, end="")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    summary = report["summary"]
    print(
        "reference audit: "
        f"skills={summary['skills']} indexed={summary['indexed_skills']} "
        f"references={summary['references']} findings={summary['findings']} "
        f"major={summary['major_findings']}",
        file=sys.stderr,
    )
    return 1 if args.require_clean and summary["major_findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
