#!/usr/bin/env python3
"""Audit progressive-disclosure reference contracts for first-party skills."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.reference_contract import audit_reference_roots  # noqa: E402

STRICT_SKILLS = {
    "codex-science",
    "science-provenance",
    "science-review",
    "literature-review",
    "docking-validation",
    "remote-scientific-compute",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    report = audit_reference_roots(
        [root / "skills", root / "authored-skills"],
        strict_names=STRICT_SKILLS,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
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
