#!/usr/bin/env python3
"""Generate a non-active skill draft from a currently passed scientific run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.pipeline_compiler import _validate_command, compile_pipeline_draft  # noqa: E402
from codex_science.artifacts import validate_manifest  # noqa: E402
from codex_science.cli_io import preflight_output_paths, resolve_input_path  # noqa: E402
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="run manifest JSON whose review.status is passed (and whose review re-checks as passed), with every plan step completed")
    parser.add_argument("output", type=Path, help="draft output directory; must be absent or empty; the draft is not activated")
    parser.add_argument("--name", required=True, help="lowercase kebab-case skill name")
    parser.add_argument("--description", required=True, help="one-line skill description")
    parser.add_argument(
        "--commands",
        type=Path,
        help=(
            'JSON array of argv arrays to record, e.g. [["python", "scripts/run.py", "--n", "5"]]; '
            'credential-bearing arguments are rejected'
        ),
    )
    parser.add_argument("--limitation", action="append", default=[], help="known limitation to record; repeatable")
    parser.add_argument("--receipt", type=Path, required=True, help="output path for the promotion receipt JSON")
    args = parser.parse_args()
    try:
        args.manifest = resolve_input_path(args.manifest)
        preflight_output_paths(args.receipt, protected_dirs=[args.output])
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        validate_manifest(manifest)
        inputs = [args.manifest]
        trees = []
        for record in manifest["inputs"]:
            if isinstance(record, dict) and "path" in record:
                relative = str(record["path"])
                if relative:
                    inputs.append(args.manifest.parent / relative)
        for record in manifest["artifacts"]:
            artifact = args.manifest.parent / str(record["path"])
            inputs.append(artifact)
            if str(record.get("artifact_type", "file")) == "directory-tree":
                if not resolve_input_path(artifact).is_relative_to(args.manifest.parent):
                    raise ValueError(f"Artifact resolves outside the run bundle: {record['path']}")
                trees.append(artifact)
            if record.get("descriptor_path") is not None:
                inputs.append(args.manifest.parent / str(record["descriptor_path"]))
        if args.commands:
            inputs.append(args.commands)
        draft_paths = [args.output / relative for relative in (
            "SKILL.md", "input.schema.json", "output.schema.json",
            "references/pipeline.md", "references/index.json", "promotion.json",
        )]
        preflight_output_paths(*draft_paths, args.receipt, inputs=inputs, protected_dirs=trees)
        output_label = resolve_input_path(args.output)
        receipt_label = resolve_input_path(args.receipt)
        commands = None
        if args.commands:
            payload = json.loads(args.commands.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("--commands must contain a JSON array")
            for index, command in enumerate(payload):
                if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
                    raise ValueError(f"command_contract[{index}] must be a non-empty argv list")
                _validate_command(command, index)
            commands = payload
        receipt = compile_pipeline_draft(
            manifest_path=args.manifest,
            output_dir=args.output,
            name=args.name,
            description=args.description,
            command_contract=commands,
            limitations=args.limitation or None,
        )
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}{digest_mismatch_hint(error, args.manifest.parent)}", file=sys.stderr)
        return 1
    print(f"Success! Draft written to: {output_label}")
    print(f"Success! Receipt written to: {receipt_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
