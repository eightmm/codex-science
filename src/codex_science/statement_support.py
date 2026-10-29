"""Compare cited report statements with verified run-local support excerpts."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from codex_science.artifacts import validate_bundle
from codex_science.citation_trace import _safe_file, extract_identifiers
from codex_science.literature_v2 import normalize_identifier

STOPWORDS = frozenset({"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "with"})
_TOKEN = re.compile(r"[a-z0-9]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
EVIDENCE_BOUNDARY = (
    "Checks only that saved verbatim excerpts exist and lexically relate to cited statements; "
    "semantic support needs independent review."
)


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if token not in STOPWORDS}


def _overlap(statement: str, excerpt: str) -> float:
    left, right = _tokens(statement), _tokens(excerpt)
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _units(text: str):
    """Split non-table lines at sentence punctuation followed by whitespace."""
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        chunks = [stripped] if stripped.startswith("|") or stripped.endswith("|") else _SENTENCE_END.split(stripped)
        for chunk in chunks:
            if chunk.strip():
                yield line_number, chunk.strip()


def check_statement_support(run_dir: str | Path, report_paths: list[str | Path] | None = None) -> dict[str, Any]:
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
    manifest_path = _safe_file(root, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, root)
    declarations = manifest.get("artifacts", [])
    reports = report_paths
    if reports is None:
        reports = [item["path"] for item in declarations if item.get("kind") == "report"]

    by_identifier: dict[str, list[dict[str, Any]]] = {}
    for study in sidecars.get("study_by_id", {}).values():
        identifier = normalize_identifier(str(study["persistent_id"]))
        by_identifier.setdefault(identifier, []).append(study)

    rows: list[dict[str, Any]] = []
    for requested in reports:
        relative = str(requested)
        path = _safe_file(root, relative)
        report_bytes = path.read_bytes()
        report_sha256 = hashlib.sha256(report_bytes).hexdigest()
        for line_number, statement in _units(report_bytes.decode("utf-8")):
            identifiers = [item["identifier"] for item in extract_identifiers(statement)]
            if not identifiers:
                continue
            pairs = []
            overlaps: list[float] = []
            for identifier in identifiers:
                studies = by_identifier.get(identifier, [])
                excerpts = [excerpt["text"] for study in studies for excerpt in study.get("support_excerpts", [])
                            if not (root / str(excerpt["source_artifact"]).strip()).samefile(path)
                            and str(excerpt["source_sha256"]).strip().lower() != report_sha256]
                status = "excerpt_available" if excerpts else "no_excerpt" if studies else "untraced"
                pair: dict[str, Any] = {"identifier": identifier, "status": status}
                if excerpts:
                    best = max(_overlap(statement, excerpt) for excerpt in excerpts)
                    pair["best_overlap"] = round(best, 6)
                    pair["low_overlap"] = best < 0.1
                    overlaps.append(best)
                pairs.append(pair)
            rows.append({"report": relative, "line": line_number, "statement": statement[:400],
                         "identifiers": identifiers, "pair_statuses": pairs,
                         "best_overlap": round(max(overlaps), 6) if overlaps else None})

    counts = {"statements": len(rows), "cited_pairs": sum(len(row["pair_statuses"]) for row in rows),
              "excerpt_available": 0, "no_excerpt": 0, "untraced": 0, "low_overlap": 0}
    for row in rows:
        for pair in row["pair_statuses"]:
            counts[pair["status"]] += 1
            counts["low_overlap"] += int(pair.get("low_overlap", False))
    return {"schema": "statement-support-v1", "statements": rows, "counts": counts,
            "reports_examined": len(reports), "evidence_boundary": EVIDENCE_BOUNDARY}
