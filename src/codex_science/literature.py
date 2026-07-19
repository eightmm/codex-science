"""Protocol-driven literature review snapshots and deterministic diffs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any


QUESTION_FRAMEWORKS = {"PICO", "PECO", "PICOT", "SPIDER", "custom"}
ELIGIBILITY_DECISIONS = {"include", "exclude", "awaiting-full-text"}


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def normalize_persistent_id(value: str) -> str:
    """Normalize DOI, PMID, PMCID, and arXiv identifiers for deduplication."""

    text = value.strip().lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "doi:",
        "https://pubmed.ncbi.nlm.nih.gov/",
        "pmid:",
        "pmcid:",
        "arxiv:",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.rstrip("/.")


def _fallback_study_key(study: dict[str, Any]) -> str:
    material = "|".join(
        [
            str(study.get("title", "")).strip().lower(),
            str(study.get("year", "")).strip(),
            str(study.get("first_author", "")).strip().lower(),
        ]
    )
    return "fallback:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def study_key(study: dict[str, Any]) -> str:
    identifiers = study.get("persistent_ids", [])
    if isinstance(identifiers, list):
        normalized = sorted(
            normalized
            for item in identifiers
            if (normalized := normalize_persistent_id(str(item)))
        )
        if normalized:
            return normalized[0]
    persistent_id = normalize_persistent_id(str(study.get("persistent_id", "")))
    return persistent_id or _fallback_study_key(study)


def deduplicate_studies(
    studies: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return canonical studies plus explicit duplicate groups.

    The first record is retained as canonical; callers must preserve the duplicate
    group rather than silently dropping study provenance.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for study in studies:
        if not isinstance(study, dict):
            raise ValueError("Study records must be objects")
        grouped[study_key(study)].append(study)

    canonical: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = grouped[key]
        canonical.append(group[0])
        if len(group) > 1:
            duplicates.append(
                {
                    "canonical_key": key,
                    "study_ids": [str(record.get("study_id", "")) for record in group],
                }
            )
    return canonical, duplicates


def validate_review_snapshot(snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("Literature snapshot must be an object")
    if snapshot.get("schema_version") != 1:
        raise ValueError("Unsupported literature snapshot schema version")
    _text(snapshot.get("protocol_id"), "literature snapshot protocol_id")
    _text(snapshot.get("evidence_cutoff"), "literature snapshot evidence_cutoff")
    framework = _text(snapshot.get("question_framework"), "question_framework")
    if framework not in QUESTION_FRAMEWORKS:
        raise ValueError(f"Unsupported literature question framework: {framework}")
    _text(snapshot.get("question"), "literature snapshot question")

    query_ids: set[str] = set()
    for index, raw in enumerate(_list(snapshot.get("queries"), "literature snapshot queries")):
        if not isinstance(raw, dict):
            raise ValueError(f"literature snapshot query {index} must be an object")
        query_id = _text(raw.get("query_id"), f"literature query {index} query_id")
        if query_id in query_ids:
            raise ValueError(f"Duplicate literature query id: {query_id}")
        query_ids.add(query_id)
        _text(raw.get("source"), f"literature query {query_id} source")
        _text(raw.get("query"), f"literature query {query_id} query")

    study_ids: set[str] = set()
    for index, raw in enumerate(_list(snapshot.get("studies"), "literature snapshot studies")):
        if not isinstance(raw, dict):
            raise ValueError(f"literature snapshot study {index} must be an object")
        study_id = _text(raw.get("study_id"), f"literature study {index} study_id")
        if study_id in study_ids:
            raise ValueError(f"Duplicate literature study id: {study_id}")
        study_ids.add(study_id)
        _text(raw.get("title"), f"literature study {study_id} title")
        decision = _text(raw.get("eligibility"), f"literature study {study_id} eligibility")
        if decision not in ELIGIBILITY_DECISIONS:
            raise ValueError(f"Invalid eligibility decision for {study_id}: {decision}")
        if decision == "exclude":
            _text(raw.get("exclusion_reason"), f"literature study {study_id} exclusion_reason")

    claim_ids: set[str] = set()
    for index, raw in enumerate(_list(snapshot.get("claims"), "literature snapshot claims")):
        if not isinstance(raw, dict):
            raise ValueError(f"literature snapshot claim {index} must be an object")
        claim_id = _text(raw.get("id"), f"literature claim {index} id")
        if claim_id in claim_ids:
            raise ValueError(f"Duplicate literature claim id: {claim_id}")
        claim_ids.add(claim_id)
        _text(raw.get("status"), f"literature claim {claim_id} status")


def _index_by(items: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    return {str(item[field]): item for item in items}


def _changed_records(
    previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for key in sorted(previous.keys() & current.keys()):
        before = previous[key]
        after = current[key]
        if before != after:
            changed.append({"id": key, "before": before, "after": after})
    return changed


def diff_review_snapshots(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, Any]:
    """Create a deterministic living-review diff instead of rewriting history."""

    validate_review_snapshot(previous)
    validate_review_snapshot(current)
    if previous["protocol_id"] != current["protocol_id"]:
        raise ValueError("Cannot diff literature snapshots with different protocol IDs")

    previous_queries = _index_by(previous["queries"], "query_id")
    current_queries = _index_by(current["queries"], "query_id")
    previous_studies = _index_by(previous["studies"], "study_id")
    current_studies = _index_by(current["studies"], "study_id")
    previous_claims = _index_by(previous["claims"], "id")
    current_claims = _index_by(current["claims"], "id")

    return {
        "schema_version": 1,
        "protocol_id": current["protocol_id"],
        "previous_cutoff": previous["evidence_cutoff"],
        "current_cutoff": current["evidence_cutoff"],
        "queries": {
            "added": sorted(current_queries.keys() - previous_queries.keys()),
            "removed": sorted(previous_queries.keys() - current_queries.keys()),
            "changed": _changed_records(previous_queries, current_queries),
        },
        "studies": {
            "added": sorted(current_studies.keys() - previous_studies.keys()),
            "removed": sorted(previous_studies.keys() - current_studies.keys()),
            "changed": _changed_records(previous_studies, current_studies),
        },
        "claims": {
            "added": sorted(current_claims.keys() - previous_claims.keys()),
            "removed": sorted(previous_claims.keys() - current_claims.keys()),
            "changed": _changed_records(previous_claims, current_claims),
        },
    }


def canonical_json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
