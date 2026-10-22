"""Offline lexical retrieval of run-local sources for report statements."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_science.artifacts import validate_bundle
from codex_science.citation_trace import _safe_file, _walk_ids, extract_identifiers
from codex_science.statement_support import _tokens, _units

CLAIM_BOUNDARY = "Candidates are ranked by lexical overlap only; this list is not evidence that a source supports a statement."


def _candidate(identifier: str | None, url: str | None, source: str, text: str) -> dict[str, Any]:
    return {"identifier": identifier, "url": url, "source": source, "text": text}


def _source_url(identifier: str) -> str | None:
    if identifier.startswith("doi:"):
        return "https://doi.org/" + identifier[4:]
    if identifier.startswith("pmid:"):
        return "https://pubmed.ncbi.nlm.nih.gov/" + identifier[5:] + "/"
    if identifier.startswith("pmcid:"):
        return "https://pmc.ncbi.nlm.nih.gov/articles/" + identifier[6:] + "/"
    if identifier.startswith("PMC"):
        return "https://pmc.ncbi.nlm.nih.gov/articles/" + identifier + "/"
    if identifier.startswith("arxiv:"):
        return "https://arxiv.org/abs/" + identifier[6:]
    return None


def _records_from_value(value: Any) -> list[str]:
    found = _walk_ids(value)
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"url", "source_url"}:
                for raw in child if isinstance(child, list) else [child]:
                    if isinstance(raw, str):
                        found.update(item["identifier"] for item in extract_identifiers(raw))
            found.update(_records_from_value(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_records_from_value(child))
    return sorted(found)


def _ledger_source_identity(record: dict[str, Any]) -> tuple[str | None, str | None]:
    identifiers: list[str] = []
    for field in ("doi", "pmid", "pmcid"):
        if field in record:
            identifiers.extend(sorted(_walk_ids({field: record[field]})))
    url = record.get("url")
    if isinstance(url, str):
        identifiers.extend(item["identifier"] for item in extract_identifiers(url))
    identifier = next(iter(dict.fromkeys(identifiers)), None)
    return identifier, (url if isinstance(url, str) and url else _source_url(identifier) if identifier else None)


def _study_source_url(study: dict[str, Any], identifier: str, primary_id: str | None) -> str | None:
    url = study.get("url")
    if isinstance(url, str) and url and identifier == primary_id:
        return url
    return _source_url(identifier)


def _load_candidates(sidecars: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    study_path = next(iter(sidecars.get("paths", {}).get("study-table", ["studies.json"])))
    for study_id, study in sorted(sidecars.get("study_by_id", {}).items()):
        ids = _records_from_value(study)
        primary_ids = sorted(_walk_ids({"persistent_id": study.get("persistent_id")}))
        primary_id = next(iter(primary_ids), None)
        label = str(study.get("title", study_id))
        for identifier in ids:
            candidates.append(_candidate(identifier, _study_source_url(study, identifier, primary_id), study_path + "#" + study_id, label))
        for index, excerpt in enumerate(study.get("support_excerpts", [])):
            excerpt_ids = ids or [None]
            for identifier in excerpt_ids:
                url = _study_source_url(study, identifier, primary_id) if identifier else None
                candidates.append(_candidate(identifier, url,
                                             f"{study_path}#{study_id}/support_excerpts/{index}", str(excerpt["text"])))
    for ledger in sidecars.get("query_ledgers", []):
        for index, record in enumerate(ledger["records"]):
            identifier, url = _ledger_source_identity(record)
            text = " ".join(record[key] for key in ("source", "query", "title", "summary", "url")
                             if isinstance(record.get(key), str))
            candidates.append(_candidate(identifier, url, f"{ledger['path']}#{index}", text))
    # Keep source identity unique while retaining deterministic insertion order.
    unique = {(item["source"], item["identifier"]): item for item in candidates}
    return sorted(unique.values(), key=lambda item: (item["source"], item["identifier"] or "", item["url"] or ""))


def retrieve_statement_sources(run_dir: str | Path, report_paths: list[str | Path] | None = None,
                               top_k: int = 5) -> dict[str, Any]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
    manifest = json.loads(_safe_file(root, "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, root)
    declarations = manifest.get("artifacts", [])
    if not isinstance(declarations, list):
        raise ValueError("manifest artifacts must be a list")
    reports = report_paths if report_paths is not None else [item["path"] for item in declarations if isinstance(item, dict) and item.get("kind") == "report"]
    candidates = _load_candidates(sidecars)
    statements = []
    for requested in reports:
        relative = str(requested)
        for line, statement in _units(_safe_file(root, relative).read_text(encoding="utf-8")):
            identifiers = [item["identifier"] for item in extract_identifiers(statement)]
            query = _tokens(statement)
            ranked = []
            for candidate in candidates:
                words = _tokens(candidate["text"])
                matched = sorted(query & words)
                union = query | words
                score = len(matched) / len(union) if union else 0.0
                if score > 0:
                    ranked.append((score, matched, candidate))
            ranked.sort(key=lambda item: (-item[0], item[2]["source"], item[2]["identifier"] or "", item[2]["url"] or ""))
            cited_rank = next((rank for rank, (_, _, item) in enumerate(ranked, 1) if item["identifier"] in identifiers), None)
            statements.append({"report": relative, "line": line, "statement": statement[:400],
                               "cited_identifiers": identifiers, "cited_source_rank": cited_rank,
                               "candidates": [{"rank": rank, "identifier": item["identifier"], "url": item["url"],
                                               "source": item["source"], "score": round(score, 6), "matched_terms": matched}
                                              for rank, (score, matched, item) in enumerate(ranked[:top_k], 1)]})
    return {"schema": "statement-retrieval-v1", "claim_boundary": CLAIM_BOUNDARY,
            "statements": statements, "reports_examined": len(reports), "top_k": top_k}
