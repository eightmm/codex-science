#!/usr/bin/env python3
"""Render local Markdown and optional offline HTML views of an artifact manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifact_index import render_html, render_markdown  # noqa: E402
from codex_science.artifacts import validate_manifest  # noqa: E402
from codex_science.cli_io import preflight_output_paths, resolve_input_path  # noqa: E402
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402


def _write(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.chmod(0o600)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="run manifest JSON; index.md (and index.html) are written next to it")
    parser.add_argument("--html", action="store_true", help="also write an offline index.html")
    args = parser.parse_args()
    run_dir = args.manifest.parent
    try:
        manifest_path = resolve_input_path(args.manifest)
        run_dir = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_manifest(manifest)
        markdown_path = run_dir / "index.md"
        html_path = run_dir / "index.html" if args.html else None
        inputs = [manifest_path]
        trees = []
        for record in manifest["inputs"]:
            if isinstance(record, dict) and "path" in record:
                relative = str(record["path"])
                if relative:
                    inputs.append(run_dir / relative)
        for record in manifest["artifacts"]:
            artifact = run_dir / str(record["path"])
            inputs.append(artifact)
            if str(record.get("artifact_type", "file")) == "directory-tree":
                if not resolve_input_path(artifact).is_relative_to(run_dir):
                    raise ValueError(f"Artifact resolves outside the run bundle: {record['path']}")
                trees.append(artifact)
            if record.get("descriptor_path") is not None:
                inputs.append(run_dir / str(record["descriptor_path"]))
        preflight_output_paths(markdown_path, html_path, inputs=inputs, protected_dirs=trees)
        markdown = render_markdown(manifest, run_dir)
        html = render_html(manifest, run_dir) if args.html else None
        _write(markdown_path, markdown)
        outputs = [f"Markdown: {markdown_path}"]
        if html_path is not None:
            _write(html_path, html)
            outputs.append(f"offline HTML: {html_path}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}{digest_mismatch_hint(error, run_dir)}", file=sys.stderr)
        return 1
    print("Codex Science report ready — " + " · ".join(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
