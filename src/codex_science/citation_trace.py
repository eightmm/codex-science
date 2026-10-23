"""Trace report citations to identifiers recorded in a literature run.

``report_paths`` (and CLI ``--report`` values) are relative to the run
directory. Any study-table record, included or excluded, counts as provenance
for tracing; inclusion affects only the ``uncited_included`` summary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from codex_science.literature_v2 import normalize_identifier

MAX_FILE_BYTES = 8 * 1024 * 1024
_ID = re.compile(
    r"(?i)(?:(?<!\w)(?:https?://(?:dx\.)?doi\.org/|doi:\s*)|(?<![\w/.\-]))(10\.\d{4,9}/[^\s<>\]\[\"'{}|]+)"
    r"|(?<!\w)(?:https?://pubmed\.ncbi\.nlm\.nih\.gov/|pmid:\s*)(\d{5,9})(?!\w)"
    r"|\b(PMC\d+)\b|(?<!\w)(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)([a-z][a-z0-9.-]*/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?(?!\w)",
)
_ID_FIELDS = {"persistent_id", "persistent_ids", "identifiers", "doi", "pmid", "pmcid", "arxiv", "returned_record_ids", "included_records"}
_FALLBACK = {
    "study-table": "studies.json", "query-ledger": "queries.jsonl",
    "lane-receipt": "lanes/pubmed-search.json",
}


def _id_from_match(match: re.Match[str]) -> str:
    doi, pmid, pmcid, arxiv = match.groups()
    if doi:
        doi = doi.rstrip(".,;:!?*_`>")
        while doi.endswith((")", "]")):
            closing = doi[-1]
            opening = "(" if closing == ")" else "["
            if doi.count(closing) <= doi.count(opening):
                break
            doi = doi[:-1]
        value = "doi:" + doi
    elif pmid:
        value = "pmid:" + pmid
    elif pmcid:
        value = pmcid
    else:
        value = "arxiv:" + arxiv.lower()
    return normalize_identifier(value)


def extract_identifiers(text: str) -> list[dict[str, Any]]:
    """Extract normalized literature IDs in first-occurrence order.

    Fenced code is scanned as ordinary text; citations in examples/code are not
    specially excluded. PMID digit runs must be 5-9 digits; arXiv new-style IDs
    must have 4 year digits and 4-5 sequence digits, and old-style IDs must
    have exactly 7 digits. Longer digit runs are rejected instead of truncated.
    """
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _ID.finditer(text):
        identifier = _id_from_match(match)
        if identifier not in seen:
            seen.add(identifier)
            found.append({"identifier": identifier, "offset": match.start()})
    return found


def _safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"path escapes run directory or is not a regular file: {relative}")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds size limit: {relative}")
    return resolved


def _walk_ids(value: Any, path: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()
            if key_lower in _ID_FIELDS:
                values = child if isinstance(child, list) else [child]
                for item in values:
                    if isinstance(item, (str, int)):
                        raw = str(item)
                        if key_lower in {"doi", "pmid", "pmcid", "arxiv"}:
                            raw = f"{key_lower}:{raw}"
                        normalized = normalize_identifier(raw)
                        if not normalized.startswith("unknown:"):
                            result.add(normalized)
            result.update(_walk_ids(child, path + "." + key_lower))
    elif isinstance(value, list):
        for item in value:
            result.update(_walk_ids(item, path))
    return result


def trace_citations(run_dir: str | Path, report_paths: list[str | Path] | None = None) -> dict[str, Any]:
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
    manifest_path = _safe_file(root, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("manifest artifacts must be a list")
    declarations: list[tuple[str, str]] = []
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            raise ValueError(f"manifest artifact {index} must be an object")
        kind, relative = item.get("kind"), item.get("path")
        if not isinstance(kind, str):
            raise ValueError(f"manifest artifact {index} kind must be a string")
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError(f"manifest artifact {index} path must be a non-empty string")
        declarations.append((kind, relative))
    sources: list[tuple[str, Any]] = []
    study_name = next((name for kind, name in declarations if kind == "study-table"), _FALLBACK["study-table"])
    study_path = _safe_file(root, study_name)
    study = json.loads(study_path.read_text(encoding="utf-8"))
    if not isinstance(study, dict):
        raise ValueError("study table must be an object")
    studies = study.get("studies", [])
    if not isinstance(studies, list):
        raise ValueError("study table studies must be a list")
    sources.append((study_name, study))
    manifest_refs = [(kind, name) for kind, name in declarations if kind in {"lane-receipt", "query-ledger", "connector-receipt"}]
    if not manifest_refs:
        manifest_refs = [("query-ledger", _FALLBACK["query-ledger"]), ("lane-receipt", _FALLBACK["lane-receipt"])]
    for kind, name in manifest_refs:
        path = _safe_file(root, name)
        if kind == "query-ledger":
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            sources.append((name, records))
        else:
            sources.append((name, json.loads(path.read_text(encoding="utf-8"))))
    known: set[str] = set()
    study_by_key: dict[str, set[str]] = {}
    included_study_keys: set[str] = set()
    for record in studies:
        if not isinstance(record, dict):
            continue
        ids = _walk_ids(record)
        sid = str(record.get("study_id", ""))
        study_by_key[sid] = ids
        known.update(ids)
        if record.get("included") is True:
            included_study_keys.add(sid)
    for name, payload in sources[1:]:
        ids = _walk_ids(payload)
        known.update(ids)
        if isinstance(payload, dict) and isinstance(payload.get("included_records"), list):
            for item in payload["included_records"]:
                identifier = normalize_identifier(str(item))
                for study_id, study_ids in study_by_key.items():
                    if str(item) == study_id or identifier in study_ids:
                        included_study_keys.add(study_id)
    reports = report_paths
    if reports is None:
        reports = [name for kind, name in declarations if kind == "report"]
    locations: dict[str, list[dict[str, Any]]] = {}
    reports_examined = 0
    for requested in reports:
        relative = str(requested)
        path = _safe_file(root, relative)
        reports_examined += 1
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for item in extract_identifiers(line):
                loc = {"file": relative, "line": line_no}
                bucket = locations.setdefault(item["identifier"], [])
                if loc not in bucket:
                    bucket.append(loc)
    cited = [{"identifier": key, "locations": locations[key]} for key in sorted(locations)]
    traced = [item for item in cited if item["identifier"] in known]
    orphans = [item for item in cited if item["identifier"] not in known]
    uncited = []
    for record in studies:
        if not isinstance(record, dict):
            continue
        study_id = str(record.get("study_id", ""))
        ids = sorted(study_by_key.get(study_id, set()))
        if study_id in included_study_keys and not set(ids).intersection(locations):
            uncited.append({"study_id": study_id, "ids": ids})
    return {"schema": "citation-trace-v1", "cited": cited, "traced": traced, "orphans": orphans,
            "uncited_included": uncited, "reports_examined": reports_examined,
            "counts": {"cited": len(cited), "traced": len(traced), "orphans": len(orphans), "uncited_included": len(uncited)},
            "evidence_boundary": "Checks internal traceability to this run's provenance only; it does not establish that a work exists or supports a claim."}
