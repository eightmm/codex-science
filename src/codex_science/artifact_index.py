"""Render safe local views of a validated scientific artifact bundle."""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from codex_science.artifacts import validate_bundle


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


def _validated_bundle(
    manifest: dict[str, Any], run_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sidecars = validate_bundle(manifest, run_dir)
    return list(manifest["artifacts"]), sidecars


def _claim_rows(manifest: dict[str, Any], sidecars: dict[str, Any]) -> list[dict[str, Any]]:
    claim_register = sidecars.get("claim_register")
    if claim_register is not None:
        return list(claim_register["claims"])
    return list(manifest["claims"])


def _claim_edge_counts(sidecars: dict[str, Any]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for edge in sidecars.get("edges", []):
        if edge["relation"] in {"supports", "contradicts", "depends_on"}:
            counts[str(edge["target"])][str(edge["relation"])] += 1
    return counts


def render_markdown(manifest: dict[str, Any], run_dir: Path) -> str:
    artifacts, sidecars = _validated_bundle(manifest, run_dir)
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
    edge_counts = _claim_edge_counts(sidecars)
    claims = _claim_rows(manifest, sidecars)
    if claims:
        for claim in claims:
            claim_id = str(claim.get("id", "claim"))
            evidence = ", ".join(_markdown_text(item) for item in claim.get("evidence", []))
            details: list[str] = []
            if claim.get("status"):
                details.append(f"status={_markdown_text(claim['status'])}")
            if claim.get("permitted_inference"):
                details.append(f"inference={_markdown_text(claim['permitted_inference'])}")
            if edge_counts.get(claim_id):
                details.extend(
                    f"{relation}={count}"
                    for relation, count in sorted(edge_counts[claim_id].items())
                )
            if evidence:
                details.append(f"evidence={evidence}")
            suffix = f" — {'; '.join(details)}" if details else ""
            lines.append(
                f"- **{_markdown_text(claim_id)}:** "
                f"{_markdown_text(claim.get('text', ''))}{suffix}"
            )
            if claim.get("uncertainty"):
                lines.append(f"  - Uncertainty: {_markdown_text(claim['uncertainty'])}")
            if claim.get("next_action"):
                lines.append(f"  - Next action: {_markdown_text(claim['next_action'])}")
    else:
        lines.append("- No claims recorded.")

    graph = sidecars.get("evidence_graph")
    if graph is not None:
        relation_counts = Counter(str(edge["relation"]) for edge in graph["edges"])
        lines.extend(["", "## Evidence graph", ""])
        lines.append(
            f"- Nodes: {len(graph['nodes'])}; edges: {len(graph['edges'])}; "
            + ", ".join(
                f"{_markdown_text(relation)}={count}"
                for relation, count in sorted(relation_counts.items())
            )
        )
        graph_paths = sidecars.get("paths", {}).get("evidence-graph", [])
        if graph_paths:
            path = graph_paths[0]
            lines.append(f"- Graph file: [{_markdown_text(path)}]({_href(path)})")

    lanes = sidecars.get("lane_receipts", [])
    if lanes:
        lines.extend(["", "## Evidence and execution lanes", ""])
        lane_paths = sidecars.get("paths", {}).get("lane-receipt", [])
        for index, lane in enumerate(lanes):
            lane_id = str(lane["lane_id"])
            path_suffix = ""
            if index < len(lane_paths):
                path = lane_paths[index]
                path_suffix = f" ([receipt]({_href(path)}))"
            supported = ", ".join(map(str, lane["supported_claim_ids"])) or "none"
            contradicted = ", ".join(map(str, lane["contradicted_claim_ids"])) or "none"
            lines.append(
                f"- **{_markdown_text(lane_id)}** — "
                f"{_markdown_text(lane['lane_type'])}; confidence={_markdown_text(lane['confidence'])}; "
                f"supports={_markdown_text(supported)}; contradicts={_markdown_text(contradicted)}"
                f"{path_suffix}"
            )

    query_records = sidecars.get("query_records", [])
    if query_records:
        lines.extend(["", "## Query ledger", ""])
        statuses = Counter(str(record["status"]) for record in query_records)
        lines.append(
            f"- Queries: {len(query_records)}; "
            + ", ".join(f"{_markdown_text(key)}={value}" for key, value in sorted(statuses.items()))
        )
        for path in sidecars.get("paths", {}).get("query-ledger", []):
            lines.append(f"- [{_markdown_text(path)}]({_href(path)})")

    model_receipts = sidecars.get("model_receipts", [])
    if model_receipts:
        lines.extend(["", "## Model receipts", ""])
        receipt_paths = sidecars.get("paths", {}).get("model-receipt", [])
        for index, receipt in enumerate(model_receipts):
            path_suffix = ""
            if index < len(receipt_paths):
                path = receipt_paths[index]
                path_suffix = f" ([receipt]({_href(path)}))"
            lines.append(
                f"- **{_markdown_text(receipt['model_id'])}** — "
                f"contract revision {_markdown_text(receipt['registry_contract_revision'])}; "
                f"fingerprint `{_markdown_text(receipt['fingerprint'])}`{path_suffix}"
            )

    lines.extend(["", "## Visual results", ""])
    images = [
        record
        for record in artifacts
        if Path(str(record["path"])).suffix.lower() in IMAGE_SUFFIXES
    ]
    if images:
        for record in images:
            path = str(record["path"])
            lines.extend(
                [
                    f"### {_markdown_text(path)}",
                    "",
                    f"![{_markdown_text(path)}]({_href(path)})",
                    "",
                ]
            )
    else:
        lines.append("No raster image artifacts recorded.")

    lines.extend(["", "## Files", ""])
    for record in artifacts:
        path = str(record["path"])
        lines.append(
            f"- [{_markdown_text(path)}]({_href(path)}) — "
            f"{_markdown_text(record.get('kind', 'artifact'))}; SHA-256 `{record['sha256']}`"
        )
    lines.extend(
        [
            "",
            "_Generated from `manifest.json` and validated hashed sidecars; this index is a derived view, not evidence._",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(manifest: dict[str, Any], run_dir: Path) -> str:
    artifacts, sidecars = _validated_bundle(manifest, run_dir)
    plan = "".join(
        f"<li><strong>{html.escape(_text(step.get('status', 'unknown')))}</strong>: "
        f"{html.escape(_text(step.get('description', step.get('id', 'step'))))}</li>"
        for step in manifest["plan"]
    ) or "<li>No plan steps recorded.</li>"

    edge_counts = _claim_edge_counts(sidecars)
    claim_items: list[str] = []
    for claim in _claim_rows(manifest, sidecars):
        claim_id = str(claim.get("id", "claim"))
        detail_parts: list[str] = []
        if claim.get("status"):
            detail_parts.append(f"status={_text(claim['status'])}")
        if claim.get("permitted_inference"):
            detail_parts.append(f"inference={_text(claim['permitted_inference'])}")
        detail_parts.extend(
            f"{relation}={count}"
            for relation, count in sorted(edge_counts.get(claim_id, {}).items())
        )
        detail = f" <small>({' ; '.join(map(html.escape, detail_parts))})</small>" if detail_parts else ""
        claim_items.append(
            f"<li><strong>{html.escape(_text(claim_id))}</strong>: "
            f"{html.escape(_text(claim.get('text', '')))}{detail}</li>"
        )
    claims = "".join(claim_items) or "<li>No claims recorded.</li>"

    graph_section = ""
    graph = sidecars.get("evidence_graph")
    if graph is not None:
        relations = Counter(str(edge["relation"]) for edge in graph["edges"])
        summary = ", ".join(
            f"{html.escape(relation)}={count}" for relation, count in sorted(relations.items())
        )
        graph_section = (
            f"<section><h2>Evidence graph</h2><p>Nodes: {len(graph['nodes'])}; "
            f"edges: {len(graph['edges'])}; {summary}</p></section>"
        )

    lanes_section = ""
    lanes = sidecars.get("lane_receipts", [])
    if lanes:
        items = "".join(
            f"<li><strong>{html.escape(_text(lane['lane_id']))}</strong> — "
            f"{html.escape(_text(lane['lane_type']))}; confidence="
            f"{html.escape(_text(lane['confidence']))}</li>"
            for lane in lanes
        )
        lanes_section = f"<section><h2>Evidence and execution lanes</h2><ul>{items}</ul></section>"

    query_section = ""
    query_records = sidecars.get("query_records", [])
    if query_records:
        statuses = Counter(str(record["status"]) for record in query_records)
        summary = ", ".join(
            f"{html.escape(status)}={count}" for status, count in sorted(statuses.items())
        )
        query_section = (
            f"<section><h2>Query ledger</h2><p>Queries: {len(query_records)}; {summary}</p></section>"
        )

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
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#18202a}}img{{max-width:100%;height:auto;border:1px solid #ccd3db}}code{{background:#eef1f4;padding:.1rem .3rem}}section{{margin:2rem 0}}figcaption,small{{color:#52606d}}</style></head>
<body><h1>Scientific run: {html.escape(_text(manifest['run_id']))}</h1>
<p><strong>Question:</strong> {html.escape(_text(manifest['question']))}</p>
<p><strong>Review:</strong> {html.escape(_text(manifest['review'].get('status', 'unknown')))}</p>
<section><h2>Plan</h2><ul>{plan}</ul></section>
<section><h2>Claims</h2><ul>{claims}</ul></section>
{graph_section}{lanes_section}{query_section}
<section><h2>Visual results</h2>{images}</section>
<section><h2>Files</h2><ul>{files}</ul></section>
<p><em>Generated from <code>manifest.json</code> and validated hashed sidecars; this index is a derived view, not evidence.</em></p>
</body></html>\n"""
