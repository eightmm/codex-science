"""Build deterministic literature candidate pools and reviewed screening tables."""
from __future__ import annotations

import hashlib
import fcntl
import json
import os
import re
import stat
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.cli_io import DEFAULT_MAX_JSON_BYTES, write_json_atomic
from codex_science.literature_v2 import normalize_identifier
from codex_science.source_operations_v3 import EuropePMCSearchV3


class _UnionFind:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))

    def find(self, item: int) -> int:
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def _relative_path(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must be a non-empty run-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must stay inside the run directory")
    return path


def _safe_file(root: Path, relative: PurePosixPath, *, required: bool = True) -> Path | None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlinked run file: {relative.as_posix()}")
    if not current.exists():
        if required:
            raise ValueError(f"run file does not exist: {relative.as_posix()}")
        return None
    if not current.is_file():
        if required:
            raise ValueError(f"run path is not a regular file: {relative.as_posix()}")
        return None
    if not current.resolve().is_relative_to(root):
        raise ValueError(f"run file escapes run directory: {relative.as_posix()}")
    return current


def _identifiers(record: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for namespace in ("doi", "pmid", "pmcid"):
        value = record.get(namespace)
        if namespace == "pmid" and type(value) is int:
            value = str(value)
        if isinstance(value, str) and value.strip():
            value = value.strip()
            if value.lower().startswith(f"{namespace}:"):
                value = value[len(namespace) + 1:].strip()
            if namespace == "doi":
                value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
            values.add(normalize_identifier(f"{namespace}:{value}"))
    source = str(record.get("source", "")).strip().lower()
    record_id = str(record.get("id", "")).strip()
    if record_id:
        if source in {"med", "pubmed"}:
            values.add(normalize_identifier(f"pmid:{record_id}"))
        elif source == "pmc" or record_id.upper().startswith("PMC"):
            values.add(normalize_identifier(f"pmcid:{record_id}"))
    return values


def _refuse_input_overwrite(output: Path, inputs: set[Path]) -> None:
    if output.resolve() in {path.resolve() for path in inputs}:
        raise ValueError("output file must not replace a consumed input or evidence file, or an excerpt source")


def build_candidate_pool(run_dir: str | Path) -> dict[str, Any]:
    root_arg = Path(run_dir).absolute()
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root_arg.resolve()
    ledger_path = _safe_file(root, PurePosixPath("queries.jsonl"))
    assert ledger_path is not None
    consumed = {ledger_path}
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid queries.jsonl JSON at line {line_number}") from error
        if not isinstance(row, dict):
            raise ValueError(f"queries.jsonl line {line_number} must be an object")
        if not row.get("result_path"):
            continue
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"queries.jsonl line {line_number} has invalid query_id")
        relative = _relative_path(row["result_path"], f"queries.jsonl line {line_number} result_path")
        # Path-safety refusals stay fatal; unusable result content is skipped and reported.
        result_path = _safe_file(root, relative, required=False)
        if result_path is None:
            skipped.append({"query_id": query_id, "result_path": relative.as_posix(), "reason": "missing or not a regular file"})
            continue
        consumed.add(result_path)
        try:
            data = _read_snapshot(result_path)
        except ValueError:
            skipped.append({"query_id": query_id, "result_path": relative.as_posix(), "reason": "invalid, oversized, or non-object JSON"})
            continue
        digest = row.get("response_sha256")
        if digest is not None and str(digest).lower() != hashlib.sha256(data).hexdigest():
            raise ValueError(f"query {query_id} result {relative.as_posix()}: response_sha256 does not match result bytes")
        try:
            result = _parse_snapshot(result_path, data)
        except ValueError:
            skipped.append({"query_id": query_id, "result_path": relative.as_posix(), "reason": "invalid, oversized, or non-object JSON"})
            continue
        records = result.get("records")
        fallback_source = row.get("source")
        if not isinstance(records, list):
            result_list = result.get("resultList")
            items = result_list.get("result") if isinstance(result_list, dict) else None
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                skipped.append({"query_id": query_id, "result_path": relative.as_posix(), "reason": "unrecognized result shape"})
                continue
            records = EuropePMCSearchV3().normalize(result)
            fallback_source = "EuropePMC"
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"result record {index} must be an object: {relative.as_posix()}")
            source, record_id = record.get("source"), record.get("id")
            if not isinstance(source, str) or not source.strip():
                source = fallback_source
            if not isinstance(source, str) or not source.strip() or not isinstance(record_id, (str, int)) or not str(record_id).strip():
                raise ValueError(f"result record {index} needs source and id: {relative.as_posix()}")
            if isinstance(record_id, bool):
                raise ValueError(f"result record {index} has invalid id: {relative.as_posix()}")
            identity_record = dict(record)
            identity_record["source"] = source
            rows.append({"query_id": query_id, "record": identity_record, "source_key": f"{source.strip().lower()}:{record_id}"})

    union = _UnionFind(len(rows))
    owners: dict[str, int] = {}
    for index, item in enumerate(rows):
        keys = _identifiers(item["record"])
        keys.add("source-record:" + item["source_key"])
        for key in keys:
            if key in owners:
                union.union(index, owners[key])
            else:
                owners[key] = index
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, item in enumerate(rows):
        groups[union.find(index)].append(item)

    candidates: list[dict[str, Any]] = []
    for members in groups.values():
        members.sort(key=lambda item: item["source_key"])
        all_ids = sorted(set().union(*(_identifiers(item["record"]) for item in members)))
        record_id = members[0]["source_key"]
        titles = sorted({str(item["record"].get("title", "")).strip() for item in members if str(item["record"].get("title", "")).strip()})
        dates = sorted({str(item["record"].get("publication_date", "")).strip() for item in members if str(item["record"].get("publication_date", "")).strip()})
        years = sorted({str(item["record"].get("year", "")).strip() for item in members if str(item["record"].get("year", "")).strip()})
        candidate: dict[str, Any] = {
            "record_id": record_id,
            "identifiers": all_ids,
            "title": titles[0] if titles else "",
            "query_ids": sorted({item["query_id"] for item in members}),
            "abstract_artifact": None,
            "abstract_sha256": None,
        }
        if dates:
            candidate["publication_date"] = dates[0]
        elif years:
            candidate["year"] = years[0]
        abstracts: list[tuple[str, str]] = []
        for item in members:
            raw_id = str(item["record"]["id"])
            if not re.fullmatch(r"[A-Za-z0-9._-]+", raw_id):
                continue
            relative = PurePosixPath("sources") / f"{raw_id}.abstract.txt"
            path = _safe_file(root, relative, required=False)
            if path is not None:
                consumed.add(path)
                abstracts.append((relative.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
        if abstracts:
            artifact, digest = sorted(abstracts)[0]
            candidate["abstract_artifact"] = artifact
            candidate["abstract_sha256"] = digest
        candidates.append(candidate)
    candidates.sort(key=lambda item: item["record_id"])
    skipped.sort(key=lambda item: (item["query_id"], item["result_path"], item["reason"]))
    pool = {
        "schema": "literature-candidates-v1", "returned_records": len(rows), "unique_records": len(candidates),
        "records": candidates, "skipped_results": skipped,
    }
    _refuse_input_overwrite(root / "candidates.json", consumed)
    write_json_atomic(root / "candidates.json", pool)
    return pool


_ARTIFACT_RE = re.compile(r"(?:^|[\s`'\"(])([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+)")


def _rationale_paths(rationale: str) -> list[str]:
    return list(dict.fromkeys(
        value for match in _ARTIFACT_RE.finditer(rationale)
        if (value := match.group(1).rstrip(".,;:)")).startswith("fulltext/")
    ))


def _rationale_artifact(root: Path, rationale: str) -> tuple[str, str] | None:
    for value in _rationale_paths(rationale):
        relative = _relative_path(value, "full-text evidence path")
        path = _safe_file(root, relative, required=False)
        if path is not None:
            return value, hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _read_snapshot(path: Path) -> bytes:
    if path.stat().st_size > DEFAULT_MAX_JSON_BYTES:
        raise ValueError(f"input JSON exceeds {DEFAULT_MAX_JSON_BYTES} bytes: {path.name}")
    data = path.read_bytes()
    if len(data) > DEFAULT_MAX_JSON_BYTES:
        raise ValueError(f"input JSON exceeds {DEFAULT_MAX_JSON_BYTES} bytes: {path.name}")
    return data


def _parse_snapshot(path: Path, data: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid JSON in {path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _load_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    # Hash the exact bytes parsed so the output names the inputs actually applied.
    data = _read_snapshot(path)
    return _parse_snapshot(path, data), hashlib.sha256(data).hexdigest()


def apply_screening_decisions(run_dir: str | Path, decisions_file: str | Path) -> dict[str, Any]:
    root_arg = Path(run_dir).absolute()
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root_arg.resolve()
    lock_path = root.parent / f".{root.name}.screening.lock"
    try:
        _safe_file(root.parent, PurePosixPath(lock_path.name), required=lock_path.exists())
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise ValueError(f"cannot open screening output lock: {error}") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("screening output lock must be a regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as error:
            raise ValueError(f"cannot acquire screening output lock: {error}") from error
        return _apply_screening_decisions_locked(root, decisions_file)
    finally:
        os.close(descriptor)


def _apply_screening_decisions_locked(root: Path, decisions_file: str | Path) -> dict[str, Any]:
    decisions_arg = Path(decisions_file)
    if decisions_arg.is_absolute():
        try:
            decisions_relative = decisions_arg.absolute().relative_to(root)
        except ValueError as error:
            raise ValueError("decisions file must be inside the run directory") from error
    else:
        cwd_candidate = decisions_arg.absolute()
        try:
            decisions_relative = cwd_candidate.relative_to(root)
        except ValueError:
            decisions_relative = decisions_arg
    decisions_path = _safe_file(root, _relative_path(decisions_relative.as_posix(), "decisions file"))
    candidates_path = _safe_file(root, PurePosixPath("candidates.json"))
    assert decisions_path is not None and candidates_path is not None
    consumed = {decisions_path, candidates_path}
    output_path = root / "screening.json"
    _refuse_input_overwrite(output_path, consumed)
    candidates, candidates_sha256 = _load_snapshot(candidates_path)
    if candidates.get("schema") != "literature-candidates-v1" or not isinstance(candidates.get("records"), list):
        raise ValueError("unsupported or malformed candidates.json")
    decisions, decisions_sha256 = _load_snapshot(decisions_path)
    top_level_errors = []
    if decisions.get("schema") != "screening-decisions-v1":
        top_level_errors.append("schema must be screening-decisions-v1")
    for field in ("reviewer", "stage"):
        if not isinstance(decisions.get(field), str) or not decisions[field].strip():
            top_level_errors.append(f"{field} must be a non-empty string")
    groups = decisions.get("groups")
    if not isinstance(groups, list):
        top_level_errors.append("groups must be a list")
    if top_level_errors:
        raise ValueError("invalid decisions top-level fields: " + "; ".join(top_level_errors))
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for item in candidates["records"]:
        if not isinstance(item, dict) or not isinstance(item.get("record_id"), str) or item["record_id"] in candidate_by_id:
            raise ValueError("candidates.json contains invalid or duplicate record_id")
        if not isinstance(item.get("title"), str):
            raise ValueError(f"candidate {item['record_id']} title must be a string")
        artifact = item.get("abstract_artifact")
        digest = item.get("abstract_sha256")
        if artifact is None:
            if digest is not None:
                raise ValueError(f"candidate has an abstract hash without an artifact: {item['record_id']}")
        else:
            relative = _relative_path(artifact, "candidate abstract_artifact")
            abstract_path = _safe_file(root, relative)
            assert abstract_path is not None
            consumed.add(abstract_path)
            actual_digest = hashlib.sha256(abstract_path.read_bytes()).hexdigest()
            if digest != actual_digest:
                raise ValueError(f"candidate abstract hash does not match artifact: {item['record_id']}")
        if not isinstance(item.get("identifiers"), list) or not isinstance(item.get("query_ids"), list):
            raise ValueError(f"candidate identifiers and query_ids must be lists: {item['record_id']}")
        candidate_by_id[item["record_id"]] = item
    assignment: dict[str, tuple[dict[str, Any], str, str, str, tuple[str, str] | None]] = {}
    for group_index, group in enumerate(groups):
        if not isinstance(group, dict) or not isinstance(group.get("decision"), str) or group["decision"] not in {"include", "exclude", "awaiting-full-text"}:
            raise ValueError(f"decision group {group_index} has invalid decision")
        for field in ("criterion", "rationale"):
            if not isinstance(group.get(field), str) or not group[field].strip():
                raise ValueError(f"decision group {group_index} {field} must be a non-empty string")
        ids = group.get("record_ids")
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise ValueError(f"decision group {group_index} record_ids must be a list of strings")
        if group["decision"] == "exclude" and len(ids) > 1 and sum(
            _safe_file(root, _relative_path(value, "full-text evidence path"), required=False) is not None
            for value in _rationale_paths(group["rationale"])
        ) > 1:
            raise ValueError(f"decision group {group_index} names multiple existing evidence files for multiple records; use separate groups")
        evidence = _rationale_artifact(root, group["rationale"])
        if evidence is not None:
            consumed.add(root / evidence[0])
        for record_id in ids:
            if record_id not in candidate_by_id:
                raise ValueError(f"unknown candidate record_id: {record_id}")
            if record_id in assignment:
                raise ValueError(f"candidate assigned more than once: {record_id}")
            candidate = candidate_by_id[record_id]
            if group["decision"] == "exclude" and not candidate.get("abstract_artifact") and evidence is None:
                raise ValueError(f"cannot exclude without an abstract or existing full-text artifact: {record_id}")
            assignment[record_id] = (group, group["decision"], group["criterion"], group["rationale"], evidence)
    records = []
    counts = {"include": 0, "exclude": 0, "awaiting-full-text": 0}
    for candidate in candidates["records"]:
        record_id = candidate["record_id"]
        group_evidence = None
        if record_id not in assignment:
            if candidate.get("abstract_artifact"):
                raise ValueError(f"candidate with accessible abstract is unlisted: {record_id}")
            decision, criterion, rationale = "awaiting-full-text", "no accessible abstract", "No accessible abstract artifact is available."
        else:
            _, decision, criterion, rationale, group_evidence = assignment[record_id]
        evidence_artifact = candidate.get("abstract_artifact")
        evidence_sha256 = candidate.get("abstract_sha256")
        if record_id in assignment and group_evidence:
            evidence_artifact, evidence_sha256 = group_evidence
        if decision == "exclude" and not evidence_artifact:
            if not group_evidence:
                raise ValueError(f"full-text evidence artifact is missing for excluded candidate: {record_id}")
        counts[decision] += 1
        records.append({
            "record_id": record_id, "identifiers": candidate["identifiers"], "title": candidate["title"],
            "query_ids": candidate["query_ids"], "decision": decision, "criterion": criterion,
            "rationale": rationale, "reviewer": decisions["reviewer"], "stage": decisions["stage"],
            "evidence_artifact": evidence_artifact, "evidence_sha256": evidence_sha256,
        })
    table = {
        "schema": "screening-table-v1",
        "candidates_sha256": candidates_sha256,
        "decisions_sha256": decisions_sha256,
        "counts": counts,
        "records": records,
    }
    _refuse_input_overwrite(output_path, consumed)
    write_json_atomic(output_path, table)
    return table
