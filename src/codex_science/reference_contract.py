"""Progressive-disclosure reference contracts for scientific Agent Skills."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

INDEX_NAME = "index.json"
REFERENCE_SECTION_RE = re.compile(r"^##\s+Reference (?:usage|map)\s*$", re.I | re.M)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((references/[^)]+)\)")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _string_list(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    result = tuple(_text(item, f"{label} item") for item in value)
    if required and not result:
        raise ValueError(f"{label} must be non-empty")
    return result


@dataclass(frozen=True)
class ReferenceEntry:
    id: str
    path: str
    purpose: str
    read_when: tuple[str, ...]
    required_before: tuple[str, ...]
    search_patterns: tuple[str, ...] = ()
    authority: str = "repository-contract"
    version: str = "1"
    evidence_boundary: str = ""

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, index: int) -> "ReferenceEntry":
        path = _text(payload.get("path"), f"references[{index}].path")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 2 or pure.parts[0] != "references":
            raise ValueError(
                f"references[{index}].path must be one level below references/: {path}"
            )
        if pure.name == INDEX_NAME:
            raise ValueError("references/index.json cannot index itself")
        return cls(
            id=_text(payload.get("id"), f"references[{index}].id"),
            path=path,
            purpose=_text(payload.get("purpose"), f"references[{index}].purpose"),
            read_when=_string_list(payload.get("read_when"), f"references[{index}].read_when", required=True),
            required_before=_string_list(
                payload.get("required_before"),
                f"references[{index}].required_before",
                required=True,
            ),
            search_patterns=_string_list(
                payload.get("search_patterns"), f"references[{index}].search_patterns"
            ),
            authority=_text(
                payload.get("authority", "repository-contract"),
                f"references[{index}].authority",
            ),
            version=_text(payload.get("version", "1"), f"references[{index}].version"),
            evidence_boundary=str(payload.get("evidence_boundary", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in ("read_when", "required_before", "search_patterns"):
            payload[field] = list(payload[field])
        return payload


@dataclass(frozen=True)
class ReferenceIndex:
    schema_version: int
    skill: str
    references: tuple[ReferenceEntry, ...]
    default_policy: str = "load-minimum-required"

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReferenceIndex":
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported reference index schema")
        raw = payload.get("references")
        if not isinstance(raw, list) or not raw:
            raise ValueError("reference index requires a non-empty references list")
        references = tuple(
            ReferenceEntry.from_payload(item, index=index)
            for index, item in enumerate(raw)
            if isinstance(item, Mapping)
        )
        if len(references) != len(raw):
            raise ValueError("each reference index entry must be an object")
        ids = [item.id for item in references]
        paths = [item.path for item in references]
        if len(ids) != len(set(ids)):
            raise ValueError("reference IDs must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("reference paths must be unique")
        return cls(
            schema_version=1,
            skill=_text(payload.get("skill"), "skill"),
            references=references,
            default_policy=_text(
                payload.get("default_policy", "load-minimum-required"), "default_policy"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill": self.skill,
            "default_policy": self.default_policy,
            "references": [item.to_dict() for item in self.references],
        }


@dataclass(frozen=True)
class ReferenceUseReceipt:
    schema_version: int
    skill: str
    reference_id: str
    path: str
    sha256: str
    read_reason: str
    used_for: tuple[str, ...]
    sections: tuple[str, ...]
    search_terms: tuple[str, ...]
    loaded_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in ("used_for", "sections", "search_terms"):
            payload[field] = list(payload[field])
        return payload


def load_reference_index(skill_dir: Path) -> ReferenceIndex | None:
    path = skill_dir / "references" / INDEX_NAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reference index must be a JSON object")
    return ReferenceIndex.from_payload(payload)


def validate_reference_index(skill_dir: Path, *, strict: bool = False) -> dict[str, Any]:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"missing SKILL.md: {skill_dir}")
    skill_text = skill_path.read_text(encoding="utf-8")
    references_dir = skill_dir / "references"
    files = sorted(
        path
        for path in references_dir.glob("*")
        if path.is_file() and path.name != INDEX_NAME and not path.name.startswith(".")
    ) if references_dir.is_dir() else []
    index = load_reference_index(skill_dir)
    findings: list[dict[str, str]] = []
    if files and index is None:
        findings.append({
            "code": "missing-reference-index",
            "severity": "major" if strict else "minor",
            "message": f"{skill_dir.name} has reference files but no references/index.json",
        })
        return {"skill": skill_dir.name, "index": None, "findings": findings, "references": []}
    if index is None:
        return {"skill": skill_dir.name, "index": None, "findings": [], "references": []}
    if index.skill != skill_dir.name:
        findings.append({
            "code": "reference-skill-mismatch",
            "severity": "major",
            "message": f"reference index skill {index.skill} does not match {skill_dir.name}",
        })
    if not REFERENCE_SECTION_RE.search(skill_text):
        findings.append({
            "code": "missing-reference-usage-section",
            "severity": "major",
            "message": f"{skill_dir.name} must contain a '## Reference usage' or '## Reference map' section",
        })
    linked = set(MARKDOWN_LINK_RE.findall(skill_text))
    indexed_paths = {item.path for item in index.references}
    actual_paths = {path.relative_to(skill_dir).as_posix() for path in files}
    for path in sorted(indexed_paths - actual_paths):
        findings.append({
            "code": "missing-reference-file",
            "severity": "major",
            "message": f"indexed reference is missing: {path}",
        })
    for path in sorted(actual_paths - indexed_paths):
        findings.append({
            "code": "unindexed-reference-file",
            "severity": "major" if strict else "minor",
            "message": f"reference file is not indexed: {path}",
        })
    for entry in index.references:
        path = skill_dir / entry.path
        if path.is_file() and len(path.read_text(encoding="utf-8")) > 12000 and not entry.search_patterns:
            findings.append({
                "code": "large-reference-without-search-patterns",
                "severity": "minor",
                "message": f"large reference needs search_patterns: {entry.path}",
            })
        if entry.path not in linked:
            findings.append({
                "code": "reference-not-linked-from-skill",
                "severity": "major" if strict else "minor",
                "message": f"SKILL.md does not link indexed reference: {entry.path}",
            })
    return {
        "skill": skill_dir.name,
        "index": index.to_dict(),
        "findings": findings,
        "references": [
            {
                **entry.to_dict(),
                "sha256": _sha256(skill_dir / entry.path) if (skill_dir / entry.path).is_file() else None,
            }
            for entry in index.references
        ],
    }


def select_references(
    index: ReferenceIndex,
    *,
    route: str = "",
    query: str = "",
    limit: int | None = None,
) -> list[ReferenceEntry]:
    tokens = set(re.findall(r"[a-z0-9_-]+", f"{route} {query}".lower()))
    ranked: list[tuple[int, str, ReferenceEntry]] = []
    for entry in index.references:
        haystack = " ".join(
            [entry.id, entry.purpose, *entry.read_when, *entry.required_before, *entry.search_patterns]
        ).lower()
        score = sum(3 for token in tokens if token and token in haystack)
        if route and any(route.lower() in item.lower() for item in entry.required_before):
            score += 20
        if route and any(route.lower() in item.lower() for item in entry.read_when):
            score += 10
        if not tokens:
            score = 1
        if score > 0:
            ranked.append((score, entry.id, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    entries = [item[2] for item in ranked]
    return entries if limit is None else entries[:limit]


def build_reference_use_receipt(
    skill_dir: Path,
    entry: ReferenceEntry,
    *,
    read_reason: str,
    used_for: Iterable[str],
    sections: Iterable[str] = (),
    search_terms: Iterable[str] = (),
    loaded_at: str | None = None,
) -> ReferenceUseReceipt:
    path = skill_dir / entry.path
    if not path.is_file():
        raise ValueError(f"reference file is missing: {entry.path}")
    return ReferenceUseReceipt(
        schema_version=1,
        skill=skill_dir.name,
        reference_id=entry.id,
        path=entry.path,
        sha256=_sha256(path),
        read_reason=_text(read_reason, "read_reason"),
        used_for=tuple(_text(item, "used_for item") for item in used_for),
        sections=tuple(str(item).strip() for item in sections if str(item).strip()),
        search_terms=tuple(str(item).strip() for item in search_terms if str(item).strip()),
        loaded_at=loaded_at or _now(),
    )


def audit_reference_roots(
    roots: Iterable[Path],
    *,
    strict_names: Iterable[str] = (),
) -> dict[str, Any]:
    strict_set = set(strict_names)
    records: list[dict[str, Any]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if not (skill_dir / "SKILL.md").is_file():
                continue
            records.append(validate_reference_index(skill_dir, strict=skill_dir.name in strict_set))
    findings = [
        {"skill": record["skill"], **finding}
        for record in records
        for finding in record["findings"]
    ]
    return {
        "schema_version": 1,
        "summary": {
            "skills": len(records),
            "indexed_skills": sum(record["index"] is not None for record in records),
            "references": sum(len(record["references"]) for record in records),
            "findings": len(findings),
            "major_findings": sum(item["severity"] == "major" for item in findings),
        },
        "skills": records,
        "findings": findings,
    }


def validate_reference_use_receipt(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported reference use receipt schema")
    for field in ("skill", "reference_id", "path", "sha256", "read_reason", "loaded_at"):
        _text(payload.get(field), field)
    reference_path = PurePosixPath(str(payload["path"]))
    if reference_path.is_absolute() or ".." in reference_path.parts or reference_path.parts[0] != "references":
        raise ValueError("reference use receipt path must stay under references/")
    digest = str(payload["sha256"]).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("reference use receipt sha256 is invalid")
    for field in ("used_for", "sections", "search_terms"):
        value = payload.get(field, [])
        if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"reference use receipt {field} must be strings")


def validate_reference_use_ledger(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported reference use ledger schema")
    _text(payload.get("skill"), "skill")
    uses = payload.get("uses")
    if not isinstance(uses, list) or not uses:
        raise ValueError("reference use ledger requires a non-empty uses list")
    seen: set[tuple[str, str]] = set()
    for item in uses:
        if not isinstance(item, Mapping):
            raise ValueError("reference use ledger entries must be objects")
        validate_reference_use_receipt(item)
        key = (str(item["reference_id"]), str(item["sha256"]))
        if key in seen:
            raise ValueError(f"duplicate reference use receipt: {item['reference_id']}")
        seen.add(key)
