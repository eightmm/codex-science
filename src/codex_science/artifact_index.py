"""Render safe local views of a validated scientific artifact bundle."""

from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any
from urllib.parse import quote

from codex_science.artifacts import validate_manifest


IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}


def _text(value: Any) -> str:
    return " ".join(str(value).split())


def _markdown_text(value: Any) -> str:
    escaped = html.escape(_text(value), quote=False)
    for character in ("\\", "[", "]", "*", "_"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _href(path: str) -> str:
    return quote(path, safe="/._-")


def _verified_artifacts(manifest: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    validate_manifest(manifest)
    resolved_run = run_dir.resolve()
    artifacts: list[dict[str, Any]] = []
    for record in manifest["artifacts"]:
        relative = str(record["path"])
        path = run_dir / relative
        if not path.is_file():
            raise ValueError(f"Artifact file is missing: {relative}")
        if not path.resolve().is_relative_to(resolved_run):
            raise ValueError(f"Artifact resolves outside the run bundle: {relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(record["sha256"]).lower():
            raise ValueError(f"Artifact digest mismatch: {relative}")
        artifacts.append(record)
    return artifacts


def render_markdown(manifest: dict[str, Any], run_dir: Path) -> str:
    artifacts = _verified_artifacts(manifest, run_dir)
    lines = [
        f"# Scientific run: {_markdown_text(manifest['run_id'])}",
        "",
        f"**Question:** {_markdown_text(manifest['question'])}",
        f"**Review:** {_markdown_text(manifest['review'].get('status', 'unknown'))}",
        "",
        "## Plan",
        "",
    ]
    if manifest["plan"]:
        for step in manifest["plan"]:
            lines.append(
                f"- **{_markdown_text(step.get('status', 'unknown'))}:** "
                f"{_markdown_text(step.get('description', step.get('id', 'step')))}"
            )
    else:
        lines.append("- No plan steps recorded.")

    lines.extend(["", "## Claims", ""])
    if manifest["claims"]:
        for claim in manifest["claims"]:
            evidence = ", ".join(_markdown_text(item) for item in claim.get("evidence", []))
            suffix = f" — evidence: {evidence}" if evidence else ""
            lines.append(f"- **{_markdown_text(claim.get('id', 'claim'))}:** {_markdown_text(claim.get('text', ''))}{suffix}")
    else:
        lines.append("- No claims recorded.")

    lines.extend(["", "## Visual results", ""])
    images = [record for record in artifacts if Path(str(record["path"])).suffix.lower() in IMAGE_SUFFIXES]
    if images:
        for record in images:
            path = str(record["path"])
            lines.extend([f"### {_markdown_text(path)}", "", f"![{_markdown_text(path)}]({_href(path)})", ""])
    else:
        lines.append("No raster image artifacts recorded.")

    lines.extend(["", "## Files", ""])
    for record in artifacts:
        path = str(record["path"])
        lines.append(
            f"- [{_markdown_text(path)}]({_href(path)}) — "
            f"{_markdown_text(record.get('kind', 'artifact'))}; SHA-256 `{record['sha256']}`"
        )
    lines.extend(["", "_Generated from `manifest.json`; this index is a derived view, not evidence._", ""])
    return "\n".join(lines)


def render_html(manifest: dict[str, Any], run_dir: Path) -> str:
    artifacts = _verified_artifacts(manifest, run_dir)
    plan = "".join(
        f"<li><strong>{html.escape(_text(step.get('status', 'unknown')))}</strong>: "
        f"{html.escape(_text(step.get('description', step.get('id', 'step'))))}</li>"
        for step in manifest["plan"]
    ) or "<li>No plan steps recorded.</li>"
    claims = "".join(
        f"<li><strong>{html.escape(_text(claim.get('id', 'claim')))}</strong>: "
        f"{html.escape(_text(claim.get('text', '')))}</li>"
        for claim in manifest["claims"]
    ) or "<li>No claims recorded.</li>"
    images = "".join(
        f'<figure><img src="{html.escape(_href(str(record["path"])), quote=True)}" '
        f'alt="{html.escape(_text(record["path"]), quote=True)}"><figcaption>'
        f'{html.escape(_text(record["path"]))}</figcaption></figure>'
        for record in artifacts
        if Path(str(record["path"])).suffix.lower() in IMAGE_SUFFIXES
    ) or "<p>No raster image artifacts recorded.</p>"
    files = "".join(
        f'<li><a href="{html.escape(_href(str(record["path"])), quote=True)}">'
        f'{html.escape(_text(record["path"]))}</a> — '
        f'{html.escape(_text(record.get("kind", "artifact")))}</li>'
        for record in artifacts
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scientific run {html.escape(_text(manifest['run_id']))}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#18202a}}img{{max-width:100%;height:auto;border:1px solid #ccd3db}}code{{background:#eef1f4;padding:.1rem .3rem}}section{{margin:2rem 0}}figcaption{{color:#52606d}}</style></head>
<body><h1>Scientific run: {html.escape(_text(manifest['run_id']))}</h1>
<p><strong>Question:</strong> {html.escape(_text(manifest['question']))}</p>
<p><strong>Review:</strong> {html.escape(_text(manifest['review'].get('status', 'unknown')))}</p>
<section><h2>Plan</h2><ul>{plan}</ul></section>
<section><h2>Claims</h2><ul>{claims}</ul></section>
<section><h2>Visual results</h2>{images}</section>
<section><h2>Files</h2><ul>{files}</ul></section>
<p><em>Generated from <code>manifest.json</code>; this index is a derived view, not evidence.</em></p>
</body></html>\n"""
