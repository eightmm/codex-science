"""Build a validated literature snapshot from a run's registers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.cli_io import write_json_atomic
from codex_science.connector_contract import canonical_json_bytes
from codex_science.evidence import _support_source_path, _validate_claim_register, _validate_study_table
from codex_science.literature import validate_review_snapshot
from codex_science.screening_pool import _relative_path, _safe_file
from codex_science.study_table import _input_file


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError(f"input JSON must be an object: {path.name}")
    return payload, hashlib.sha256(data).hexdigest()


def build_literature_snapshot(
    run_dir: str | Path, output: str | Path = "snapshot.current.json",
    protocol_id: str | None = None,
) -> dict[str, Any]:
    """Derive snapshot.current.json from protocol, query, study and claim records."""
    root_arg = Path(run_dir).absolute()
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root_arg.resolve()
    protocol_path = _input_file(root, root / "protocol.json", "protocol file")
    queries_path = _input_file(root, root / "queries.jsonl", "queries file")
    studies_path = _input_file(root, root / "studies.json", "studies file")
    claims_path = _input_file(root, root / "claims.json", "claims file")
    screening_path = _safe_file(root, PurePosixPath("screening.json"), required=False)
    input_paths = {
        "protocol": protocol_path, "queries": queries_path,
        "studies": studies_path, "claims": claims_path,
    }
    if screening_path is not None:
        input_paths["screening"] = screening_path

    output_arg = Path(output)
    if output_arg.is_absolute():
        try:
            output_arg = output_arg.absolute().relative_to(root)
        except ValueError as error:
            raise ValueError("output file must be inside the run directory") from error
    output_rel = _relative_path(output_arg.as_posix(), "output file")
    output_path = _safe_file(root, output_rel, required=False) or root.joinpath(*output_rel.parts)
    problems: list[str] = []
    hashes: dict[str, str] = {}
    protocol: dict[str, Any] = {}
    for name, path in (("protocol", protocol_path), ("studies", studies_path), ("claims", claims_path)):
        try:
            payload, digest = _read_json(path)
            hashes[name] = digest
            if name == "protocol":
                protocol = payload
            elif name == "studies":
                studies_payload = payload
            else:
                claims_payload = payload
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            problems.append(f"{name}: {error}")
            if name == "studies":
                studies_payload = {}
            elif name == "claims":
                claims_payload = {}

    if protocol_id is not None and (not isinstance(protocol_id, str) or not protocol_id.strip()):
        problems.append("--protocol-id must be a non-empty string")
    recorded_protocol_id = protocol.get("protocol_id")
    if isinstance(recorded_protocol_id, str) and recorded_protocol_id.strip():
        if protocol_id is not None and protocol_id != recorded_protocol_id:
            problems.append("--protocol-id differs from protocol.json protocol_id")
        effective_protocol_id = recorded_protocol_id
    elif protocol_id is not None and isinstance(protocol_id, str) and protocol_id.strip():
        effective_protocol_id = protocol_id
    else:
        effective_protocol_id = None
    required_protocol_fields = ("question", "question_framework", "evidence_cutoff")
    for field in required_protocol_fields:
        value = protocol.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"protocol.json missing required field: {field}")
    if effective_protocol_id is None:
        problems.append(
            "protocol.json missing required field: protocol_id; pass --protocol-id or add protocol_id to protocol.json, "
            "and keep it stable across living updates"
        )

    query_rows: list[dict[str, Any]] = []
    try:
        query_bytes = queries_path.read_bytes()
        hashes["queries"] = hashlib.sha256(query_bytes).hexdigest()
        by_query_id: dict[str, dict[str, Any]] = {}
        for line_number, raw in enumerate(query_bytes.decode("utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as error:
                problems.append(f"queries.jsonl line {line_number}: invalid JSON: {error}")
                continue
            if not isinstance(record, dict):
                problems.append(f"queries.jsonl line {line_number} must be an object")
                continue
            query_id, source, query = record.get("query_id"), record.get("source"), record.get("query")
            if not isinstance(query_id, str) or not query_id.strip():
                problems.append(f"queries.jsonl line {line_number} has invalid query_id")
                continue
            if not isinstance(source, str) or not source.strip() or not isinstance(query, str) or not query.strip():
                problems.append(f"queries.jsonl line {line_number} requires non-empty source and query for {query_id}")
                continue
            entry = {"query_id": query_id, "source": source, "query": query}
            for field in ("status", "accessed_at"):
                if field in record:
                    entry[field] = record[field]
            previous = by_query_id.get(query_id)
            if previous is not None:
                if canonical_json_bytes(previous) != canonical_json_bytes(entry):
                    problems.append(f"conflicting duplicate query_id: {query_id}")
                continue
            by_query_id[query_id] = entry
        query_rows = list(by_query_id.values())
    except (OSError, UnicodeError) as error:
        problems.append(f"queries: {error}")

    raw_studies = studies_payload.get("studies")
    if isinstance(raw_studies, list):
        for index, study in enumerate(raw_studies):
            if not isinstance(study, dict):
                continue
            study_id = study.get("study_id")
            label = study_id if isinstance(study_id, str) and study_id.strip() else f"at index {index}"
            for field in ("title", "persistent_id"):
                value = study.get(field)
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"study {label} missing or blank {field}")

    try:
        study_rows_for_validation = studies_payload.get("studies")
        if isinstance(study_rows_for_validation, list):
            studies_for_validation = {
                **studies_payload,
                "studies": [
                    {**study, "included": True}
                    if isinstance(study, dict) and "included" not in study
                    else study
                    for study in study_rows_for_validation
                ],
            }
        else:
            studies_for_validation = studies_payload
        study_by_id = _validate_study_table(studies_for_validation, root)
    except (ValueError, TypeError) as error:
        problems.append(f"studies: {error}")
        study_by_id = {}
    excerpt_source_paths = {
        _support_source_path(root, excerpt["source_artifact"], study_id, excerpt.get("claim_id", ""))
        for study_id, study in study_by_id.items()
        for excerpt in study.get("support_excerpts", [])
    }
    protected = {path.resolve() for path in input_paths.values()} | {path.resolve() for path in excerpt_source_paths}
    protected.update({(root / "manifest.json").resolve(), (root / "snapshot.previous.json").resolve()})
    if output_path.resolve() in protected:
        raise ValueError("output file must not replace an input file, an excerpt source, manifest.json, or snapshot.previous.json")
    try:
        claim_by_id = _validate_claim_register(claims_payload)
    except (ValueError, TypeError) as error:
        problems.append(f"claims: {error}")
        claim_by_id = {}

    study_rows: list[dict[str, Any]] = []
    studies_by_record_id: dict[str, list[tuple[str, bool]]] = {}
    for study_id, study in study_by_id.items():
        row = {
            "study_id": study_id,
            "title": study.get("title", ""),
            "persistent_id": study.get("persistent_id", ""),
            "eligibility": "include",
        }
        # The snapshot contract treats an omitted inclusion flag as included.
        if study.get("included", True) is False:
            record_id = study.get("record_id")
            if isinstance(record_id, str) and record_id.strip():
                studies_by_record_id.setdefault(record_id, []).append((study_id, False))
            reason = study.get("exclusion_reason")
            if not isinstance(reason, str) or not reason.strip():
                problems.append(f"study {study_id} included=false requires a non-empty exclusion_reason")
            else:
                row["eligibility"] = "exclude"
                row["exclusion_reason"] = reason
        else:
            record_id = study.get("record_id")
            if isinstance(record_id, str) and record_id.strip():
                studies_by_record_id.setdefault(record_id, []).append((study_id, True))
        study_rows.append(row)
    if screening_path is not None:
        try:
            screening, digest = _read_json(screening_path)
            hashes["screening"] = digest
            if screening.get("schema") != "screening-table-v1" or not isinstance(screening.get("records"), list):
                problems.append("screening.json must use schema screening-table-v1 and contain records")
            else:
                included_ids = set(study_by_id)
                seen_screen_ids: set[str] = set()
                for index, record in enumerate(screening["records"]):
                    if not isinstance(record, dict):
                        problems.append(f"screening record {index} must be an object")
                        continue
                    record_id = record.get("record_id")
                    if not isinstance(record_id, str) or not record_id.strip():
                        problems.append(f"screening record {index} has invalid record_id")
                        continue
                    if record_id in seen_screen_ids:
                        problems.append(f"duplicate screening record_id: {record_id}")
                        continue
                    seen_screen_ids.add(record_id)
                    decision = record.get("decision")
                    if decision == "include":
                        continue
                    if decision not in ("exclude", "awaiting-full-text"):
                        problems.append(f"screening record {record_id} has invalid decision: {decision!r}")
                        continue
                    linked_studies = studies_by_record_id.get(record_id, [])
                    if decision in {"exclude", "awaiting-full-text"}:
                        for study_id, is_included in linked_studies:
                            if not is_included:
                                continue
                            problems.append(
                                f"record {record_id} is {decision} in screening.json but extracted as included study {study_id}"
                            )
                    if any(not is_included for _, is_included in linked_studies):
                        continue
                    if decision == "exclude" and record_id in included_ids:
                        problems.append(f"screening record_id collides with study_id: {record_id}")
                        continue
                    row: dict[str, Any] = {"study_id": record_id, "title": "",
                                           "persistent_id": "", "eligibility": decision}
                    identifiers = record.get("identifiers", [])
                    if not isinstance(identifiers, list) or any(not isinstance(item, str) for item in identifiers):
                        problems.append(f"screening record {record_id} identifiers must be a list of strings")
                    else:
                        row["persistent_id"] = next((item for item in identifiers if item.lower().startswith("doi:")), identifiers[0] if identifiers else "")
                    title = record.get("title")
                    row["title"] = title if isinstance(title, str) and title.strip() else (
                        f"untitled record {row['persistent_id'] or record_id}"
                    )
                    if decision == "exclude":
                        criterion, rationale = record.get("criterion"), record.get("rationale")
                        if not isinstance(criterion, str) or not criterion.strip() or not isinstance(rationale, str) or not rationale.strip():
                            problems.append(f"screening record {record_id} exclusion requires criterion and rationale")
                        else:
                            row["exclusion_reason"] = f"{criterion}: {rationale}"
                    study_rows.append(row)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            problems.append(f"screening: {error}")

    snapshot = {
        "schema_version": 1,
        "protocol_id": effective_protocol_id,
        "question": protocol.get("question"),
        "question_framework": protocol.get("question_framework"),
        "evidence_cutoff": protocol.get("evidence_cutoff"),
        "queries": query_rows,
        "studies": study_rows,
        "claims": [{"id": claim_id, "status": claim["status"]} for claim_id, claim in claim_by_id.items()],
    }
    try:
        validate_review_snapshot(snapshot)
    except (ValueError, TypeError) as error:
        problems.append(str(error))
    if problems:
        raise ValueError("; ".join(problems))

    write_json_atomic(output_path, snapshot)
    return {
        "schema": "literature-snapshot-build-v1",
        "output": output_path.relative_to(root).as_posix(),
        "counts": {"queries": len(query_rows), "studies": len(study_rows), "claims": len(claim_by_id)},
        "inputs_sha256": hashes,
    }
