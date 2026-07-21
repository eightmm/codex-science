"""Machine-readable maturity auditing for first-party scientific skills."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


LEVELS = {f"L{index}": index for index in range(5)}
ROLES = {"conductor", "retriever", "executor", "analyzer", "reviewer", "infrastructure"}
REQUIRED_DECISION_SECTIONS = ("## Decision contract", "## Workflow", "## Outputs", "## Boundaries")
CORE_SECTION_ALIASES = {
    "codex-science": ("## Research contract and evidence graph", "## Workflow", "## Completion test", "## Boundaries"),
    "science-provenance": ("## Run contract", "## Inputs and retrieval", "## Outputs and claims", "## Safety and integrity"),
    "science-review": ("## Inputs and review mode", "## Review workflow", "## Receipt and independence", "## Boundary"),
}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.+?)\s*$", re.MULTILINE)


def _safe_repo_path(root: Path, value: Any, label: str) -> Path:
    text = str(value).strip()
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{label} must be a safe repository-relative path: {text}")
    path = (root / pure.as_posix()).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"{label} escapes repository root")
    return path


def _frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        return {}
    return {item.group("key"): item.group("value").strip().strip('"\'') for item in FIELD_RE.finditer(match.group("body"))}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _reference_contract(skill_dir: Path) -> tuple[bool, list[str]]:
    index_path = skill_dir / "references" / "index.json"
    if not index_path.is_file():
        return False, ["references/index.json is missing"]
    try:
        payload = _load_json(index_path, "reference index")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return False, [str(error)]
    entries = payload.get("references")
    if not isinstance(entries, list) or not entries:
        return False, ["reference index contains no references"]
    errors: list[str] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping):
            errors.append(f"reference {index} is not an object")
            continue
        reference_id = str(raw.get("id", "")).strip()
        relative = str(raw.get("path", "")).strip()
        if not reference_id or reference_id in ids:
            errors.append(f"reference {index} has missing or duplicate id")
        ids.add(reference_id)
        if not relative or relative in paths:
            errors.append(f"reference {index} has missing or duplicate path")
        paths.add(relative)
        try:
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 2 or pure.parts[0] != "references":
                raise ValueError("must be a one-level references path")
            target = skill_dir / relative
            if not target.is_file():
                errors.append(f"indexed reference is missing: {relative}")
        except ValueError as error:
            errors.append(f"invalid reference path {relative}: {error}")
        if not isinstance(raw.get("read_when"), list) or not raw.get("read_when"):
            errors.append(f"reference {reference_id or index} has no read_when routes")
        if raw.get("required_before") is None:
            errors.append(f"reference {reference_id or index} has no required_before field")
        if not str(raw.get("evidence_boundary", "")).strip():
            errors.append(f"reference {reference_id or index} has no evidence_boundary")
    return not errors, errors


def _path_list(payload: Mapping[str, Any], field: str) -> list[str]:
    value = payload.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"quality {field} must be a string list")
    return [item.strip() for item in value]


def validate_quality_declaration(root: Path, skill_dir: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported quality declaration schema")
    skill = str(payload.get("skill", "")).strip()
    if not skill:
        raise ValueError("quality skill is required")
    roles = _path_list(payload, "roles")
    unknown_roles = sorted(set(roles) - ROLES)
    if unknown_roles:
        raise ValueError(f"unknown skill roles: {', '.join(unknown_roles)}")
    declared = str(payload.get("declared_maturity", "")).strip()
    if declared not in LEVELS:
        raise ValueError(f"invalid declared maturity: {declared}")
    output_schemas = _path_list(payload, "output_schemas")
    fixtures = _path_list(payload, "acceptance_fixtures")
    seeded_failures = _path_list(payload, "seeded_failures")
    tests = _path_list(payload, "test_files")
    limitations = _path_list(payload, "limitations")
    for path in fixtures + tests:
        if not _safe_repo_path(root, path, "quality dependency").exists():
            raise ValueError(f"quality dependency does not exist: {path}")
    if LEVELS[declared] >= 3 and not output_schemas:
        raise ValueError("L3+ skills require output_schemas")
    if LEVELS[declared] >= 4 and (not fixtures or not seeded_failures or not tests):
        raise ValueError("L4 skills require acceptance fixtures, seeded failures, and tests")
    return {
        "schema_version": 1,
        "skill": skill,
        "roles": roles,
        "declared_maturity": declared,
        "output_schemas": output_schemas,
        "acceptance_fixtures": fixtures,
        "seeded_failures": seeded_failures,
        "test_files": tests,
        "limitations": limitations,
        "quality_path": str((skill_dir / "quality.json").relative_to(root)),
    }


def _sections_for(skill_dir: Path, name: str, text: str) -> tuple[bool, list[str]]:
    required = CORE_SECTION_ALIASES.get(name, REQUIRED_DECISION_SECTIONS)
    missing = [section for section in required if section not in text]
    return not missing, missing


def evaluate_skill(root: Path, skill_dir: Path) -> dict[str, Any]:
    skill_path = skill_dir / "SKILL.md"
    relative = str(skill_dir.relative_to(root))
    record: dict[str, Any] = {
        "path": relative,
        "name": skill_dir.name,
        "computed_maturity": "L0",
        "declared_maturity": None,
        "roles": [],
        "reasons": [],
        "output_schemas": [],
        "acceptance_fixtures": [],
        "seeded_failures": [],
        "test_files": [],
        "limitations": [],
        "reference_contract": False,
    }
    if not skill_path.is_file():
        record["reasons"].append("SKILL.md is missing")
        return record
    text = skill_path.read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    name = metadata.get("name", "").strip()
    description = metadata.get("description", "").strip()
    if not name or not description or "# " not in text:
        record["reasons"].append("frontmatter name/description or title is missing")
        return record
    record["name"] = name
    computed = 1
    complete_sections, missing_sections = _sections_for(skill_dir, skill_dir.name, text)
    has_provenance = "$science-provenance" in text or skill_dir.name == "science-provenance"
    has_review = "$science-review" in text or skill_dir.name == "science-review"
    if complete_sections and has_provenance and has_review:
        computed = 2
    else:
        record["reasons"].extend(f"missing instruction contract: {section}" for section in missing_sections)
        if not has_provenance:
            record["reasons"].append("science provenance handoff is missing")
        if not has_review:
            record["reasons"].append("science review handoff is missing")
    reference_ok, reference_errors = _reference_contract(skill_dir)
    record["reference_contract"] = reference_ok
    if not reference_ok and (skill_dir / "references").is_dir():
        record["reasons"].extend(reference_errors)
    quality_path = skill_dir / "quality.json"
    declaration: dict[str, Any] | None = None
    if quality_path.is_file():
        try:
            declaration = validate_quality_declaration(root, skill_dir, _load_json(quality_path, "quality declaration"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            record["reasons"].append(f"invalid quality declaration: {error}")
    if declaration:
        record.update({key: declaration[key] for key in ("declared_maturity", "roles", "output_schemas", "acceptance_fixtures", "seeded_failures", "test_files", "limitations")})
        if computed >= 2 and reference_ok and declaration["output_schemas"]:
            computed = 3
        if computed >= 3 and declaration["acceptance_fixtures"] and declaration["seeded_failures"] and declaration["test_files"]:
            computed = 4
    record["computed_maturity"] = f"L{computed}"
    if record["declared_maturity"] and LEVELS[record["computed_maturity"]] < LEVELS[record["declared_maturity"]]:
        record["reasons"].append(f"declared {record['declared_maturity']} but computed {record['computed_maturity']}")
    return record


def load_policy(root: Path, path: Path | None = None) -> dict[str, Any]:
    policy_path = path or root / "catalog" / "native-skill-policy.json"
    payload = _load_json(policy_path, "native skill policy")
    if payload.get("schema_version") != 1 or not isinstance(payload.get("requirements"), list):
        raise ValueError("unsupported native skill policy")
    return payload


def audit_native_skills(root: Path, *, policy_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    records = []
    for parent in (root / "skills", root / "authored-skills"):
        if not parent.is_dir():
            continue
        for skill_dir in sorted(path for path in parent.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()):
            records.append(evaluate_skill(root, skill_dir))
    by_name = {record["name"]: record for record in records}
    policy = load_policy(root, policy_path)
    findings: list[dict[str, str]] = []
    for requirement in policy["requirements"]:
        if not isinstance(requirement, Mapping):
            raise ValueError("native skill policy requirements must be objects")
        name = str(requirement.get("skill", ""))
        minimum = str(requirement.get("minimum_maturity", ""))
        if minimum not in LEVELS:
            raise ValueError(f"invalid policy maturity: {minimum}")
        record = by_name.get(name)
        if record is None:
            findings.append({"code": "missing-policy-skill", "severity": "major", "skill": name, "message": f"Policy skill is missing: {name}"})
            continue
        if LEVELS[record["computed_maturity"]] < LEVELS[minimum]:
            findings.append({"code": "skill-below-maturity", "severity": "major", "skill": name, "message": f"{name} computed {record['computed_maturity']} below required {minimum}."})
        required_roles = set(requirement.get("required_roles", []))
        missing_roles = sorted(required_roles - set(record["roles"]))
        if missing_roles:
            findings.append({"code": "missing-skill-role", "severity": "major", "skill": name, "message": f"{name} is missing roles: {', '.join(missing_roles)}"})
        if bool(requirement.get("require_reference_contract", False)) and not record["reference_contract"]:
            findings.append({"code": "missing-reference-contract", "severity": "major", "skill": name, "message": f"{name} has no valid progressive reference contract."})
    summary = {level: sum(record["computed_maturity"] == level for record in records) for level in LEVELS}
    return {
        "schema_version": 1,
        "skill_count": len(records),
        "summary": summary,
        "status": "findings" if findings else "passed",
        "findings": sorted(findings, key=lambda item: (item["code"], item["skill"])),
        "skills": records,
        "policy": policy,
    }


def render_maturity_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Native skill maturity",
        "",
        f"Status: **{report['status']}** · skills: **{report['skill_count']}**",
        "",
        "| Skill | Path | Computed | Declared | Roles | References | Findings |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for record in report["skills"]:
        reasons = "; ".join(record["reasons"]).replace("|", "\\|")
        lines.append(
            f"| {record['name']} | `{record['path']}` | {record['computed_maturity']} | {record['declared_maturity'] or ''} | "
            f"{', '.join(record['roles'])} | {'yes' if record['reference_contract'] else 'no'} | {reasons} |"
        )
    if report["findings"]:
        lines.extend(["", "## Policy findings", ""])
        lines.extend(f"- **{item['code']}** `{item['skill']}` — {item['message']}" for item in report["findings"])
    lines.append("")
    return "\n".join(lines)
