"""Deterministic inventory and conservative activation policy for agent skills."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$")
# Split on any non-alphanumeric so hyphenated/underscored skill names
# (e.g. "cx-clinvar-search") tokenize into their words and match natural queries.
TOKEN_RE = re.compile(r"[a-z0-9]+")
SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "my",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "use",
        "using",
        "with",
    }
)
NAME_TOKEN_WEIGHT = 12
CREDENTIAL_RE = re.compile(
    r"\b[A-Z][A-Z0-9_]{2,}_(?:API_)?(?:KEY|TOKEN|SECRET)\b|"
    r"\b(?:api key|credentials?) (?:is |are )?required\b|\brequires? an api key\b",
    re.IGNORECASE,
)
UNSAFE_PATTERNS = (
    re.compile(r"curl\b[^\n|]*\|\s*(?:ba)?sh\b", re.IGNORECASE),
    re.compile(r"wget\b[^\n|]*\|\s*(?:ba)?sh\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bignore (?:all )?(?:previous|prior) instructions\b", re.IGNORECASE),
    re.compile(r"\b(?:upload|send|exfiltrate)\b[^\n]{0,60}\b(?:secret|credential|token|key)s?\b", re.IGNORECASE),
)
EXECUTABLE_SUFFIXES = {".py", ".sh", ".bash", ".js", ".ts", ".ps1"}
SOURCE_DIGEST_EXCLUDES = frozenset({".git", ".omc", "__pycache__"})


@dataclass(frozen=True)
class CatalogPolicy:
    permissive_license_markers: tuple[str, ...]
    high_stakes_name_markers: tuple[str, ...]
    physical_lab_markers: tuple[str, ...] = ()

    @classmethod
    def default(cls) -> "CatalogPolicy":
        return cls(
            permissive_license_markers=(
                "mit",
                "apache-2.0",
                "apache license",
                "bsd",
                "isc",
                "cc-by-4.0",
                "cc by 4.0",
                "biopython license agreement",
                "cecill free software license",
                "creativecommons.org/licenses/by/4.0",
                "github.com/sympy/sympy/blob/master/license",
                "github.com/pydicom/pydicom/blob/main/license",
                "github.com/pola-rs/polars/blob/main/license",
                "github.com/matplotlib/matplotlib/tree/main/license",
            ),
            high_stakes_name_markers=(
                "clinical-decision",
                "clinical-reports",
                "treatment-plan",
            ),
            physical_lab_markers=(
                "pylabrobot",
                "opentrons",
                "cloud-lab",
                "cloud lab",
                "ginkgo",
                "emerald-cloud",
                "strateos",
                "tecan",
                "liquid-handling",
                "liquid handler",
                "lab automation",
                "laboratory automation",
            ),
        )


def _strip_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"Missing YAML frontmatter: {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"Unterminated YAML frontmatter: {path}") from exc

    fields: dict[str, str] = {}
    index = 1
    while index < end:
        match = FIELD_RE.match(lines[index])
        if not match:
            index += 1
            continue
        key, raw_value = match.group(1), (match.group(2) or "")
        if raw_value.strip() in {">", "|", ">-", "|-", ">+", "|+"}:
            block: list[str] = []
            index += 1
            while index < end and (lines[index].startswith(" ") or not lines[index].strip()):
                block.append(lines[index].strip())
                index += 1
            fields[key] = " ".join(part for part in block if part)
            continue
        fields[key] = _strip_scalar(raw_value)
        index += 1
    return fields


def _license_reason(license_name: str | None, policy: CatalogPolicy) -> str | None:
    if not license_name or license_name.strip().lower() in {"unknown", "n/a", "none"}:
        return "unknown-license"
    normalized = license_name.lower()
    restricted = ("proprietary", "non-commercial", "noncommercial", "by-nc", "nc-sa", "gpl")
    if any(marker in normalized for marker in restricted):
        return "restricted-license"
    if not any(marker in normalized for marker in policy.permissive_license_markers):
        return "unknown-license"
    return None


def _executable_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        if not path.is_file() or path.name == "SKILL.md":
            continue
        relative = path.relative_to(skill_dir)
        if "scripts" in relative.parts or path.suffix.lower() in EXECUTABLE_SUFFIXES:
            files.append(relative)
    return sorted(files, key=lambda item: item.as_posix())


def source_content_digest(source_root: Path) -> str:
    """Hash a vendored source tree by relative path and file content."""
    digest = sha256()
    files = (
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and not any(part in SOURCE_DIGEST_EXCLUDES for part in path.relative_to(source_root).parts)
    )
    for path in sorted(files, key=lambda item: item.relative_to(source_root).as_posix()):
        relative = path.relative_to(source_root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def audit_skill(
    skill_dir: Path,
    policy: CatalogPolicy,
    *,
    default_license: str | None = None,
) -> dict[str, Any]:
    skill_file = skill_dir / "SKILL.md"
    metadata = parse_frontmatter(skill_file)
    name = metadata.get("name", "").strip() or skill_dir.name
    description = metadata.get("description", "").strip()
    license_name = metadata.get("license") or default_license or None
    text = skill_file.read_text(encoding="utf-8", errors="replace")
    executables = _executable_files(skill_dir)
    reasons: list[str] = []

    license_reason = _license_reason(license_name, policy)
    if license_reason:
        reasons.append(license_reason)
    if executables:
        reasons.append("executable-content")
    if CREDENTIAL_RE.search(text):
        reasons.append("credentials-required")
    if any(pattern.search(text) for pattern in UNSAFE_PATTERNS):
        reasons.append("unsafe-instruction")
    lowered_name = name.lower()
    if any(marker in lowered_name for marker in policy.high_stakes_name_markers):
        reasons.append("high-stakes-domain")
    if not description:
        reasons.append("missing-description")

    lowered_haystack = f"{lowered_name} {description.lower()}"
    physical_lab = any(marker in lowered_haystack for marker in policy.physical_lab_markers)

    unique_reasons = sorted(set(reasons))
    return {
        "name": name,
        "description": description,
        "license": license_name or "Unknown",
        "path": skill_dir.name,
        "executable_count": len(executables),
        "instruction_line_count": len(text.splitlines()),
        "status": "inactive" if unique_reasons else "active",
        "reasons": unique_reasons,
        "physical_lab": physical_lab,
    }


def _audit_records(
    catalog_root: Path,
    policy: CatalogPolicy,
    *,
    path_prefix: str = "",
    name_prefix: str = "",
    source_key: str = "",
    default_license: str | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for skill_file in sorted(catalog_root.glob("*/SKILL.md"), key=lambda item: item.parent.name):
        folder = skill_file.parent.name
        if folder in exclude:
            continue
        record = audit_skill(skill_file.parent, policy, default_license=default_license)
        record["path"] = str(Path(path_prefix) / folder) if path_prefix else folder
        if name_prefix:
            record["name"] = f"{name_prefix}-{record['name']}"
        if source_key:
            record["source"] = source_key
        records.append(record)
    return records


def audit_catalog(
    catalog_root: Path,
    source_commit: str,
    policy: CatalogPolicy,
    *,
    path_prefix: str = "",
    name_prefix: str = "",
    source_key: str = "",
    default_license: str | None = None,
) -> dict[str, Any]:
    records = _audit_records(
        catalog_root,
        policy,
        path_prefix=path_prefix,
        name_prefix=name_prefix,
        source_key=source_key,
        default_license=default_license,
    )
    active = sum(record["status"] == "active" for record in records)
    return {
        "schema_version": 1,
        "source": {"commit": source_commit},
        "summary": {"total": len(records), "active": active, "inactive": len(records) - active},
        "skills": records,
    }


def audit_sources(
    sources: list[dict[str, Any]],
    root: Path,
    policy: CatalogPolicy,
) -> dict[str, Any]:
    """Audit multiple catalogs into one deterministic schema-2 inventory."""
    all_records: list[dict[str, Any]] = []
    source_meta: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        key = str(source["key"])
        catalog_path = str(source["catalog_path"])
        catalog_root = (root / catalog_path).resolve()
        if not catalog_root.is_dir():
            raise ValueError(f"Catalog directory not found: {catalog_root}")
        records = _audit_records(
            catalog_root,
            policy,
            path_prefix=catalog_path,
            name_prefix=str(source.get("name_prefix", key)),
            source_key=key,
            default_license=source.get("default_license"),
            exclude=frozenset(source.get("exclude", [])),
        )
        for record in records:
            if record["name"] in seen:
                raise ValueError(f"Duplicate skill name across sources: {record['name']}")
            seen.add(record["name"])
        all_records.extend(records)
        source_meta.append(
            {
                "key": key,
                "repository": str(source.get("repository", "")),
                "commit": str(source.get("commit", "")),
                "catalog_path": catalog_path,
                "kind": str(source.get("kind", "")),
                **(
                    {"content_sha256": str(source["content_sha256"])}
                    if source.get("content_sha256")
                    else {}
                ),
            }
        )
    all_records.sort(key=lambda item: str(item["name"]))
    active = sum(record["status"] == "active" for record in all_records)
    return {
        "schema_version": 2,
        "sources": sorted(source_meta, key=lambda item: item["key"]),
        "summary": {"total": len(all_records), "active": active, "inactive": len(all_records) - active},
        "skills": all_records,
    }


def write_inventory(inventory: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_inventory(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in (1, 2) or not isinstance(payload.get("skills"), list):
        raise ValueError(f"Unsupported inventory: {path}")
    return payload


def search_inventory(
    inventory: dict[str, Any],
    query: str,
    *,
    include_inactive: bool = False,
    limit: int = 5,
) -> list[dict[str, Any]]:
    terms = set(TOKEN_RE.findall(query.lower())) - SEARCH_STOPWORDS
    if not terms:
        raise ValueError("Query must contain a searchable term")
    if not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for skill in inventory["skills"]:
        if skill.get("status") != "active" and not include_inactive:
            continue
        name_tokens = set(TOKEN_RE.findall(str(skill.get("name", "")).lower())) - SEARCH_STOPWORDS
        description_tokens = (
            set(TOKEN_RE.findall(str(skill.get("description", "")).lower())) - SEARCH_STOPWORDS
        )
        score = NAME_TOKEN_WEIGHT * len(terms & name_tokens) + len(terms & description_tokens)
        if score:
            ranked.append((score, str(skill.get("name", "")), skill))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:limit]]
