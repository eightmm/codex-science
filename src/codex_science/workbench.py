"""Offline, hash-validated scientific workbench views."""
from __future__ import annotations

import html
import json
import os
from collections import Counter
from pathlib import Path
from stat import S_ISREG
from typing import Any

from codex_science.artifacts import validate_bundle, validate_manifest
from codex_science.collaboration import fold_annotation_resolutions, load_resolution_events


def _text(value: Any) -> str:
    return html.escape(" ".join(str(value).split()))


def render_workbench(manifest: dict[str, Any], run_dir: Path) -> str:
    sidecars = validate_bundle(manifest, run_dir)
    annotations = fold_annotation_resolutions(
        sidecars.get("annotations", []), load_resolution_events(run_dir), sidecars.get("artifact_hashes", {})
    )
    artifacts = manifest.get("artifacts", [])
    claims = sidecars.get("claim_by_id", {})
    if not claims:
        claims = {str(item.get("id")): item for item in manifest.get("claims", [])}
    graph = sidecars.get("graph_v2") or sidecars.get("evidence_graph") or {}
    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    relation_counts = Counter(str(edge.get("relation")) for edge in edges)
    claim_rows = "".join(
        f"<tr><td>{_text(claim_id)}</td><td>{_text(claim.get('status', 'recorded'))}</td><td>{_text(claim.get('text', ''))}</td><td>{_text(claim.get('uncertainty', ''))}</td></tr>"
        for claim_id, claim in sorted(claims.items())
    ) or "<tr><td colspan='4'>No claims recorded.</td></tr>"
    artifact_rows = "".join(
        f"<tr><td><a href='{html.escape(str(item['path']), quote=True)}'>{_text(item['path'])}</a></td><td>{_text(item.get('kind', 'artifact'))}</td><td><code>{_text(item['sha256'])}</code></td></tr>"
        for item in artifacts
    )
    finding_rows: list[str] = []
    for receipt in sidecars.get("review_receipts", []):
        for finding in receipt.get("findings", []):
            finding_rows.append(f"<tr><td>{_text(finding.get('severity', ''))}</td><td>{_text(finding.get('code', finding.get('id', '')))}</td><td>{_text(finding.get('message', finding.get('rationale', '')))}</td><td>{_text(finding.get('resolution_status', 'open'))}</td></tr>")
    for finding in sidecars.get("advanced_findings", []):
        finding_rows.append(f"<tr><td>{_text(finding.get('severity', ''))}</td><td>{_text(finding.get('code', ''))}</td><td>{_text(finding.get('message', ''))}</td><td>open</td></tr>")
    annotation_rows = "".join(
        f"<li><strong>{_text(item['annotation_id'])}</strong> [{_text(item['status'])}] {_text(item['text'])}"
        f"{(' <span>(operator-recorded, not covered by the manifest)</span>') if item.get('latest_resolution') else ''} — "
        f"<code>{_text(item['anchor']['artifact_path'])}</code> @ <code>{_text(item['anchor']['artifact_sha256'][:12])}</code> "
        f"{_text(item['anchor'].get('json_pointer') or item['anchor'].get('claim_id') or item['anchor'].get('line_range'))}"
        f"{(' — resolution note (operator-recorded, not covered by the manifest): ' + _text(item['latest_resolution'].get('note', ''))) if item.get('latest_resolution') else ''}</li>"
        for item in annotations
    ) or "<li>No annotations recorded.</li>"
    relations = ", ".join(f"{_text(key)}={value}" for key, value in sorted(relation_counts.items())) or "none"
    findings = "".join(finding_rows) or "<tr><td colspan='4'>No review findings recorded.</td></tr>"
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Codex Science workbench — {_text(manifest.get('run_id'))}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#17202a}}table{{border-collapse:collapse;width:100%;margin:1rem 0 2rem}}th,td{{border:1px solid #ccd4dc;padding:.45rem;text-align:left;vertical-align:top}}th{{background:#eef2f5}}code{{font-size:.78rem;word-break:break-all}}.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.6rem}}.card{{border:1px solid #ccd4dc;padding:.8rem;border-radius:.4rem}}</style></head>
<body><h1>Scientific workbench: {_text(manifest.get('run_id'))}</h1>
<div class='meta'><div class='card'><strong>Question</strong><br>{_text(manifest.get('question'))}</div><div class='card'><strong>Review</strong><br>{_text(manifest.get('review', {}).get('status', 'unknown'))}</div><div class='card'><strong>Evidence graph</strong><br>{relations}</div></div>
<h2>Claims</h2><table><thead><tr><th>ID</th><th>Status</th><th>Claim</th><th>Uncertainty</th></tr></thead><tbody>{claim_rows}</tbody></table>
<h2>Findings</h2><table><thead><tr><th>Severity</th><th>Code</th><th>Finding</th><th>Resolution</th></tr></thead><tbody>{findings}</tbody></table>
<h2>Annotations</h2><ul>{annotation_rows}</ul>
<h2>Artifacts</h2><table><thead><tr><th>Path</th><th>Kind</th><th>SHA-256</th></tr></thead><tbody>{artifact_rows}</tbody></table>
<p><em>Offline derived view. Registered bundle artifacts and sidecars were validated against the manifest. Resolution events are operator-recorded and not covered by the manifest.</em></p></body></html>\n"""


def _referenced_paths(value: Any, kind: str | None = None):
    pending = [(value, kind)]
    while pending:
        value, kind = pending.pop()
        if kind is not None:
            yield kind, str(value)
        if isinstance(value, dict):
            for key, item in value.items():
                label = f"referenced input ({key})" if key in {"path", "evidence"} or key.endswith("_path") else kind
                pending.append((item, label))
        elif isinstance(value, list):
            pending.extend((item, kind) for item in value)


def _protect_workbench_output(manifest: dict[str, Any], manifest_path: Path, output: Path) -> None:
    validate_manifest(manifest)
    try:
        resolved_output = output.resolve()
        try:
            info = resolved_output.stat()
        except FileNotFoundError:
            output_identity = None
        else:
            output_identity = (info.st_dev, info.st_ino)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"workbench output cannot be resolved: {error}") from None

    run_dir = manifest_path.parent
    resolved_run = run_dir.resolve()
    protected: list[tuple[str, Path]] = [
        ("manifest", manifest_path),
        ("annotation resolution log", run_dir / "annotations/resolutions.jsonl"),
        ("annotation resolution lock", run_dir / "annotations/.resolutions.lock"),
        ("execution journal", run_dir / "execution-log.jsonl"),
    ]
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != "directory-tree":
            continue
        relative = str(artifact["path"])
        try:
            tree = (run_dir / relative).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if not tree.is_relative_to(resolved_run):
            continue
        if resolved_output.is_relative_to(tree):
            raise ValueError(f"workbench output cannot overwrite directory-tree artifact: {tree}")
        # Do not traverse directory symlinks into files outside the registered tree.
        for directory, _, files in os.walk(tree, followlinks=False):
            protected.extend(("directory-tree member", Path(directory) / name) for name in files)
    protected.extend((kind, run_dir / relative) for kind, relative in _referenced_paths(manifest))
    for kind, path in protected:
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if resolved_output == resolved:
            raise ValueError(f"workbench output cannot overwrite {kind}: {path}")
        if output_identity is None:
            continue
        try:
            info = resolved.stat()
        except (OSError, RuntimeError, ValueError):
            continue
        if S_ISREG(info.st_mode) and output_identity == (info.st_dev, info.st_ino):
            raise ValueError(f"workbench output cannot overwrite {kind}: {path}")


def write_workbench(manifest_path: Path, output: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _protect_workbench_output(manifest, manifest_path, output)
    output.write_text(render_workbench(manifest, manifest_path.parent), encoding="utf-8")
