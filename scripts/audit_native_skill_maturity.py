#!/usr/bin/env python3
"""Audit first-party skills against machine-readable L0-L4 maturity policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.skill_maturity import audit_native_skills, render_maturity_markdown  # noqa: E402
from codex_science.cli_io import preflight_output_paths, resolve_input_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        root = resolve_input_path(args.root)
        policy = resolve_input_path(args.policy or root / "catalog" / "native-skill-policy.json")
        parents = [root / "runtime-skills", root / "authored-skills"]
        trees = []
        inputs = [policy]
        for parent in parents:
            if not parent.is_dir():
                continue
            for skill in parent.iterdir():
                if skill.is_dir() and (skill / "SKILL.md").is_file():
                    trees.append(skill)
                    inputs.extend([skill / "SKILL.md", skill / "quality.json", skill / "references" / "index.json"])
        preflight_output_paths(args.output, args.markdown, inputs=inputs, protected_dirs=trees)
        for skill in trees:
            quality = skill / "quality.json"
            if not quality.is_file():
                continue
            try:
                declaration = json.loads(quality.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(declaration, dict):
                continue
            for field in ("acceptance_fixtures", "test_files"):
                values = declaration.get(field, [])
                if not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, str) or not value.strip():
                        continue
                    relative = PurePosixPath(value.strip())
                    if not relative.is_absolute() and ".." not in relative.parts:
                        inputs.append(root / relative)
        preflight_output_paths(args.output, args.markdown, inputs=inputs, protected_dirs=trees)
        report = audit_native_skills(root, policy_path=policy)
        markdown = render_maturity_markdown(report) if args.markdown else None
        rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        output_label = resolve_input_path(args.output) if args.output else None
        markdown_label = resolve_input_path(args.markdown) if args.markdown else None
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        if args.markdown:
            args.markdown.parent.mkdir(parents=True, exist_ok=True)
            args.markdown.write_text(markdown, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.output:
        print(f"Success! Data written to: {output_label}")
    else:
        print(rendered, end="")
    if args.markdown:
        print(f"Success! Report written to: {markdown_label}")
    if args.require_clean and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
