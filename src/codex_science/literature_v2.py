"""Namespace-safe literature identity, study-family resolution, and risk-of-bias records."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable

IDENTIFIER_PATTERNS = (
    ("doi", re.compile(r"^(?:https?://doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.I)),
    ("pmid", re.compile(r"^(?:https?://pubmed\.ncbi\.nlm\.nih\.gov/|pmid:)?(\d{5,9})/?$", re.I)),
    ("pmcid", re.compile(r"^(?:pmcid:)?(PMC\d+)$", re.I)),
    ("arxiv", re.compile(r"^(?:https?://arxiv\.org/abs/|arxiv:)?([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?$", re.I)),
    ("nct", re.compile(r"^(?:nct:)?(NCT\d{8})$", re.I)),
)
RELATIONSHIPS = {"preprint_of", "published_as", "corrected_by", "retracted_by", "secondary_analysis_of", "protocol_for", "registry_for"}
PUBLICATION_PRIORITY = {
    "corrected-peer-reviewed": 0,
    "peer-reviewed": 1,
    "accepted-manuscript": 2,
    "preprint": 3,
    "conference-abstract": 4,
    "registry": 5,
}
ROB_JUDGMENTS = {"low", "some-concerns", "high", "unclear", "not-applicable"}


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}
    def find(self, value: str) -> str:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]
    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def normalize_identifier(value: str) -> str:
    text = value.strip().rstrip("/.")
    for namespace, pattern in IDENTIFIER_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            identifier = match.group(1)
            return f"{namespace}:{identifier.lower() if namespace in {'doi', 'arxiv'} else identifier.upper() if namespace in {'pmcid', 'nct'} else identifier}"
    if ":" in text:
        namespace, identifier = text.split(":", 1)
        if namespace and identifier:
            return f"{namespace.lower()}:{identifier.strip()}"
    return "unknown:" + hashlib.sha256(text.lower().encode("utf-8")).hexdigest()[:24]


def _identifiers(record: dict[str, Any]) -> set[str]:
    values: list[str] = []
    persistent = record.get("persistent_ids")
    if isinstance(persistent, list):
        values.extend(map(str, persistent))
    if record.get("persistent_id"):
        values.append(str(record["persistent_id"]))
    for field in ("doi", "pmid", "pmcid", "arxiv", "nct"):
        if record.get(field):
            values.append(f"{field}:{record[field]}")
    return {normalize_identifier(value) for value in values if value.strip()}


def validate_relationships(records: list[dict[str, Any]]) -> None:
    ids = {str(record.get("study_id", "")) for record in records}
    for record in records:
        source = str(record.get("study_id", ""))
        if not source:
            raise ValueError("study_id is required")
        relations = record.get("relationships", [])
        if not isinstance(relations, list):
            raise ValueError(f"study {source} relationships must be a list")
        for relation in relations:
            if not isinstance(relation, dict):
                raise ValueError(f"study {source} relationship must be an object")
            kind, target = str(relation.get("type", "")), str(relation.get("target_study_id", ""))
            if kind not in RELATIONSHIPS or target not in ids:
                raise ValueError(f"invalid study relationship: {source} {kind} {target}")


def resolve_study_families(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    validate_relationships(records)
    by_id = {str(record["study_id"]): dict(record) for record in records}
    union = UnionFind(by_id)
    owner: dict[str, str] = {}
    for study_id, record in by_id.items():
        for identifier in _identifiers(record):
            if identifier in owner:
                union.union(study_id, owner[identifier])
            else:
                owner[identifier] = study_id
    for study_id, record in by_id.items():
        for relation in record.get("relationships", []):
            union.union(study_id, str(relation["target_study_id"]))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for study_id, record in by_id.items():
        groups[union.find(study_id)].append(record)
    families: list[dict[str, Any]] = []
    for records_in_family in groups.values():
        ranked = sorted(records_in_family, key=lambda item: (PUBLICATION_PRIORITY.get(str(item.get("publication_state", "registry")), 99), str(item["study_id"])))
        identifiers = sorted(set().union(*(_identifiers(record) for record in records_in_family)))
        family_id = "family-" + hashlib.sha256("|".join(identifiers or sorted(str(item["study_id"]) for item in records_in_family)).encode("utf-8")).hexdigest()[:20]
        families.append({
            "family_id": family_id,
            "canonical_study_id": str(ranked[0]["study_id"]),
            "study_ids": sorted(str(item["study_id"]) for item in records_in_family),
            "persistent_ids": identifiers,
            "publication_states": sorted({str(item.get("publication_state", "unknown")) for item in records_in_family}),
        })
    return sorted(families, key=lambda item: item["family_id"])


def validate_risk_of_bias(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported risk-of-bias schema")
    if not str(payload.get("study_id", "")).strip() or not str(payload.get("instrument", "")).strip():
        raise ValueError("risk-of-bias study_id and instrument are required")
    domains = payload.get("domains")
    if not isinstance(domains, list) or not domains:
        raise ValueError("risk-of-bias domains must be non-empty")
    for index, domain in enumerate(domains):
        if not isinstance(domain, dict) or not str(domain.get("name", "")).strip():
            raise ValueError(f"risk-of-bias domain {index} is invalid")
        if domain.get("judgment") not in ROB_JUDGMENTS:
            raise ValueError(f"risk-of-bias domain {index} has invalid judgment")
        if not str(domain.get("rationale", "")).strip():
            raise ValueError(f"risk-of-bias domain {index} needs rationale")
    if payload.get("overall_judgment") not in ROB_JUDGMENTS:
        raise ValueError("invalid overall risk-of-bias judgment")
