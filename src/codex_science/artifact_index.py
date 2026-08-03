"""Render safe local views of a validated scientific artifact bundle."""

from __future__ import annotations

import html
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from codex_science.artifacts import validate_bundle


IMAGE_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
PRIMARY_KIND_TERMS = (
    "report",
    "result",
    "figure",
    "table",
    "metric",
    "notebook",
    "manuscript",
)
STATUS_LABELS = {
    "passed": "✅ Passed",
    "complete": "✅ Complete",
    "completed": "✅ Complete",
    "supported": "✅ Supported",
    "replicated": "✅ Replicated",
    "in_progress": "🟡 In progress",
    "pending": "⏳ Pending",
    "planned": "⏳ Planned",
    "findings": "⚠️ Needs attention",
    "conflicting": "⚠️ Conflicting",
    "inconclusive": "⚠️ Inconclusive",
    "failed": "❌ Failed",
    "unsupported": "❌ Unsupported",
    "withdrawn": "❌ Withdrawn",
}


def _text(value: Any) -> str:
    return " ".join(str(value).split())


def _markdown_text(value: Any) -> str:
    escaped = html.escape(_text(value), quote=False)
    # The same helper is used both inline and on standalone prose lines. Escape
    # inline delimiters everywhere, then neutralize the remaining constructs
    # that are special only at the start of a CommonMark block. ``_text`` has
    # already collapsed embedded newlines, so there is exactly one block start.
    for character in ("\\", "`", "[", "]", "*", "_", "|", "~"):
        escaped = escaped.replace(character, f"\\{character}")
    if escaped.startswith(("#", "-", "+")):
        escaped = "\\" + escaped
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


def _human_label(value: Any) -> str:
    text = _text(value).replace("_", " ").replace("-", " ")
    return text[:1].upper() + text[1:] if text else "Unknown"


def _status_label(value: Any, *, default: str = "Recorded") -> str:
    if value is None:
        return default
    normalized = _text(value).lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return default
    return STATUS_LABELS.get(normalized, _human_label(normalized))


def _count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def _primary_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def priority(record: dict[str, Any]) -> tuple[int, str]:
        kind = _text(record.get("kind", "artifact")).lower()
        rank = next(
            (index for index, term in enumerate(PRIMARY_KIND_TERMS) if term in kind),
            len(PRIMARY_KIND_TERMS),
        )
        return rank, _text(record.get("path", ""))

    selected = [
        record
        for record in artifacts
        if any(
            term in _text(record.get("kind", "")).lower()
            for term in PRIMARY_KIND_TERMS
        )
    ]
    return sorted(selected, key=priority)


def render_markdown(manifest: dict[str, Any], run_dir: Path) -> str:
    artifacts, sidecars = _validated_bundle(manifest, run_dir)
    claims = _claim_rows(manifest, sidecars)
    plan = list(manifest["plan"])
    completed_steps = sum(
        1 for step in plan if _text(step.get("status", "")).lower() in {"complete", "completed"}
    )
    review_status = _status_label(manifest["review"].get("status", "unknown"))
    plan_status = f"{completed_steps}/{len(plan)} complete" if plan else "No recorded plan"
    lines = [
        f"# {_markdown_text(manifest['question'])}",
        "",
        f"**Run:** {_markdown_text(manifest['run_id'])}",
        "",
        "## Status",
        "",
        "| Review | Plan | Claims | Files |",
        "| --- | --- | ---: | ---: |",
        (
            f"| {_markdown_text(review_status)} | {_markdown_text(plan_status)} | "
            f"{len(claims)} | {len(artifacts)} |"
        ),
        "",
        "## Results",
        "",
    ]
    runtime_history = manifest.get("runtime_history", [])
    if isinstance(runtime_history, list) and runtime_history:
        if manifest.get("runtime_span"):
            lines.extend(
                [
                    (
                        "> ⚠️ **Runtime changed during this run.** "
                        f"{len(runtime_history)} verified runtime identities wrote durable state; "
                        "compare steps cautiously and see `manifest.json` for the exact record."
                    ),
                    "",
                ]
            )
        else:
            identity = runtime_history[0]
            version = _text(
                identity.get("runtime_version", identity.get("plugin_version", "unknown"))
            )
            commit = _text(identity.get("commit", ""))
            short = commit[:8] if len(commit) == 40 else commit
            lines.extend(
                [f"**Runtime:** {_markdown_text(version)} ({_markdown_text(short)})", ""]
            )
    edge_counts = _claim_edge_counts(sidecars)
    if claims:
        for claim in claims:
            claim_id = str(claim.get("id", "claim"))
            evidence = ", ".join(_markdown_text(item) for item in claim.get("evidence", []))
            lines.extend(
                [
                    (
                        f"### {_markdown_text(_status_label(claim.get('status')))} · "
                        f"{_markdown_text(claim_id)}"
                    ),
                    "",
                    _markdown_text(claim.get("text", "")),
                ]
            )
            if claim.get("permitted_inference"):
                lines.append(
                    f"- **Inference boundary:** {_markdown_text(claim['permitted_inference'])}"
                )
            if evidence:
                lines.append(f"- **Evidence:** {evidence}")
            relationships = edge_counts.get(claim_id)
            if relationships:
                rendered = ", ".join(
                    f"{_human_label(relation)}: {count}"
                    for relation, count in sorted(relationships.items())
                )
                lines.append(f"- **Relationships:** {_markdown_text(rendered)}")
            lines.append("")
    else:
        lines.append("- No claims recorded.")

    images = [
        record
        for record in artifacts
        if Path(str(record["path"])).suffix.lower() in IMAGE_SUFFIXES
    ]
    if images:
        lines.extend(["### Visual results", ""])
        for record in images:
            path = str(record["path"])
            lines.extend(
                [
                    f"#### {_markdown_text(path)}",
                    "",
                    f"![{_markdown_text(path)}]({_href(path)})",
                    "",
                ]
            )

    lines.extend(["## Limitations and next steps", ""])
    claim_actions = [
        claim for claim in claims if claim.get("uncertainty") or claim.get("next_action")
    ]
    if claim_actions:
        for claim in claim_actions:
            lines.append(f"- **{_markdown_text(claim.get('id', 'claim'))}**")
            if claim.get("uncertainty"):
                lines.append(
                    f"  - **Limitation or uncertainty:** {_markdown_text(claim['uncertainty'])}"
                )
            if claim.get("next_action"):
                lines.append(f"  - **Next:** {_markdown_text(claim['next_action'])}")
    else:
        lines.append("No claim-specific limitations or next steps were recorded in the bundle.")

    lines.extend(["", "## Primary files", ""])
    primary = _primary_artifacts(artifacts)
    if primary:
        for record in primary:
            path = str(record["path"])
            lines.append(
                f"- **{_markdown_text(_human_label(record.get('kind', 'artifact')))}:** "
                f"[{_markdown_text(path)}]({_href(path)})"
            )
    else:
        lines.append(
            "No report, result, figure, table, metrics, notebook, or manuscript "
            "file was recorded."
        )

    lines.extend(["", "## Details", "", "### Plan", ""])
    if plan:
        for step in plan:
            lines.append(
                f"- **{_markdown_text(_status_label(step.get('status', 'unknown')))}:** "
                f"{_markdown_text(step.get('description', step.get('id', 'step')))}"
            )
    else:
        lines.append("- No plan steps recorded.")

    graph = sidecars.get("evidence_graph")
    if graph is not None:
        relation_counts = Counter(str(edge["relation"]) for edge in graph["edges"])
        lines.extend(["", "### Evidence graph", ""])
        lines.append(
            f"- {_count_phrase(len(graph['nodes']), 'node')} and "
            f"{_count_phrase(len(graph['edges']), 'relationship')}."
        )
        if relation_counts:
            rendered = ", ".join(
                f"{_human_label(relation)}: {count}"
                for relation, count in sorted(relation_counts.items())
            )
            lines.append(f"- **Relationship types:** {_markdown_text(rendered)}")
        graph_paths = sidecars.get("paths", {}).get("evidence-graph", [])
        if graph_paths:
            path = graph_paths[0]
            lines.append(f"- [Open the evidence graph]({_href(path)})")

    lanes = sidecars.get("lane_receipts", [])
    if lanes:
        lines.extend(["", "### Evidence and execution lanes", ""])
        lane_paths = sidecars.get("paths", {}).get("lane-receipt", [])
        for index, lane in enumerate(lanes):
            lane_id = str(lane["lane_id"])
            lines.append(
                f"- **{_markdown_text(lane_id)}** — "
                f"{_markdown_text(_human_label(lane['lane_type']))}; "
                f"{_markdown_text(_human_label(lane['confidence']))} confidence."
            )
            supported = ", ".join(map(str, lane["supported_claim_ids"])) or "None"
            contradicted = ", ".join(map(str, lane["contradicted_claim_ids"])) or "None"
            lines.append(f"  - **Supports:** {_markdown_text(supported)}")
            lines.append(f"  - **Contradicts:** {_markdown_text(contradicted)}")
            if index < len(lane_paths):
                path = lane_paths[index]
                lines.append(f"  - [Open receipt]({_href(path)})")

    query_records = sidecars.get("query_records", [])
    if query_records:
        lines.extend(["", "### Query ledger", ""])
        statuses = Counter(str(record["status"]) for record in query_records)
        rendered = ", ".join(
            f"{_human_label(key)}: {value}" for key, value in sorted(statuses.items())
        )
        lines.append(
            f"- {_count_phrase(len(query_records), 'query', 'queries')}. "
            f"{_markdown_text(rendered)}."
        )
        for path in sidecars.get("paths", {}).get("query-ledger", []):
            lines.append(f"- [{_markdown_text(path)}]({_href(path)})")

    model_receipts = sidecars.get("model_receipts", [])
    if model_receipts:
        lines.extend(["", "### Model receipts", ""])
        receipt_paths = sidecars.get("paths", {}).get("model-receipt", [])
        for index, receipt in enumerate(model_receipts):
            lines.append(
                f"- **{_markdown_text(receipt['model_id'])}** — "
                f"contract revision {_markdown_text(receipt['registry_contract_revision'])}."
            )
            if index < len(receipt_paths):
                path = receipt_paths[index]
                lines.append(f"  - [Open receipt]({_href(path)})")

    lines.extend(["", "### All files", ""])
    for record in artifacts:
        path = str(record["path"])
        lines.append(
            f"- [{_markdown_text(path)}]({_href(path)}) — "
            f"{_markdown_text(_human_label(record.get('kind', 'artifact')))}"
        )
    lines.extend(
        [
            "",
            "Full artifact metadata and SHA-256 checksums are in [manifest.json](manifest.json).",
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
    runtime_history = manifest.get("runtime_history", [])
    runtime_notice = ""
    if isinstance(runtime_history, list) and runtime_history:
        if manifest.get("runtime_span"):
            runtime_notice = (
                '<p class="warning"><strong>Runtime changed during this run.</strong> '
                f'{len(runtime_history)} verified runtime identities wrote durable state; '
                'see <code>manifest.json</code>.</p>'
            )
        else:
            identity = runtime_history[0]
            version = html.escape(
                _text(
                    identity.get(
                        "runtime_version", identity.get("plugin_version", "unknown")
                    )
                )
            )
            commit = _text(identity.get("commit", ""))
            short = html.escape(commit[:8] if len(commit) == 40 else commit)
            runtime_notice = f"<p><strong>Runtime:</strong> {version} ({short})</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scientific run {html.escape(_text(manifest['run_id']))}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#18202a}}img{{max-width:100%;height:auto;border:1px solid #ccd3db}}code{{background:#eef1f4;padding:.1rem .3rem}}section{{margin:2rem 0}}figcaption,small{{color:#52606d}}.warning{{border-left:.3rem solid #c97a00;background:#fff7e6;padding:.75rem 1rem}}</style></head>
<body><h1>Scientific run: {html.escape(_text(manifest['run_id']))}</h1>
<p><strong>Question:</strong> {html.escape(_text(manifest['question']))}</p>
<p><strong>Review:</strong> {html.escape(_text(manifest['review'].get('status', 'unknown')))}</p>
{runtime_notice}
<section><h2>Plan</h2><ul>{plan}</ul></section>
<section><h2>Claims</h2><ul>{claims}</ul></section>
{graph_section}{lanes_section}{query_section}
<section><h2>Visual results</h2>{images}</section>
<section><h2>Files</h2><ul>{files}</ul></section>
<p><em>Generated from <code>manifest.json</code> and validated hashed sidecars; this index is a derived view, not evidence.</em></p>
</body></html>\n"""
