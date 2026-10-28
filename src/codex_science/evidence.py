"""Validation and review helpers for hashed claim/evidence sidecars.

The stable artifact manifest schema remains version 1. Rich scientific semantics
live in ordinary manifest artifacts with explicit ``kind`` values, so older
bundles stay valid and newer bundles gain machine-readable claim lineage.
"""

from __future__ import annotations

import json
import hashlib
import reprlib
import stat
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from codex_science.rigor import CLAIM_STRENGTHS
from codex_science import commitment_ledger


SIDECAR_KINDS = {
    "claim-register",
    "evidence-graph",
    "lane-receipt",
    "query-ledger",
    "study-table",
    "literature-snapshot",
    "model-receipt",
}
SINGLETON_KINDS = {
    "claim-register": "claim_register",
    "evidence-graph": "evidence_graph",
    "study-table": "study_table",
    "literature-snapshot": "literature_snapshot",
}
RELATIONS = {
    "supports",
    "contradicts",
    "depends_on",
    "duplicates",
    "derived_from",
    "shares_cohort",
    "shares_samples",
    "propagated_from",
    "training_overlap",
}
NODE_TYPES = {
    "claim",
    "study",
    "dataset",
    "artifact",
    "execution",
    "query",
    "model",
    "cohort",
    "sample",
    "portal",
}
CLAIM_STATUSES = {
    "planned",
    "supported",
    "replicated",
    "suggestive",
    "conflicting",
    "unsupported",
    "withdrawn",
    "unavailable",
}
QUERY_STATUSES = {"complete", "partial", "failed", "unavailable"}
EVIDENCE_TYPES = {"primary", "secondary", "preprint", "registry", "dataset", "computed"}
CONFIDENCE_LEVELS = {"high", "moderate", "low", "very-low", "unrated"}
MAX_SUPPORT_SOURCE_BYTES = 10 * 1024 * 1024
_USER_VALUE_REPR = reprlib.Repr()
_USER_VALUE_REPR.maxlevel = 4
_USER_VALUE_REPR.maxstring = 80
_USER_VALUE_REPR.maxlist = 6
_USER_VALUE_REPR.maxdict = 6
_USER_VALUE_REPR.maxtuple = 6
_USER_VALUE_REPR.maxset = 6
_USER_VALUE_REPR.maxfrozenset = 6
_USER_VALUE_REPR.maxother = 80


def _bounded_repr(value: Any) -> str:
    """Render one-line, bounded diagnostics for values supplied in sidecars."""
    try:
        try:
            rendered = _USER_VALUE_REPR.repr(value)
        except Exception:
            rendered = f"<{type(value).__name__[:40]}>"
        rendered = rendered.replace("\r", r"\r").replace("\n", r"\n")
        return rendered if len(rendered) <= 120 else rendered[:119] + "…"
    except Exception:
        try:
            rendered = f"<{type(value).__name__[:40]}>"
            return rendered.replace("\r", r"\r").replace("\n", r"\n")[:120]
        except Exception:
            return "<unavailable>"


def _bounded_field_repr(record: Any, field: str) -> str:
    try:
        return _bounded_repr(record.get(field))
    except Exception:
        return "<unavailable>"


def _bounded_item_repr(record: Any, field: str) -> str:
    try:
        return _bounded_repr(record[field])
    except Exception:
        return "<unavailable>"


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object: {_bounded_repr(value)}; expected: object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list: {_bounded_repr(value)}; expected: list")
    return value


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required: {_bounded_repr(value)}; expected: non-empty text")
    return text


def _string_list(value: Any, label: str) -> list[str]:
    items = _list(value, label)
    result: list[str] = []
    for index, item in enumerate(items):
        result.append(_text(item, f"{label}[{index}]"))
    return result


def _schema_one(payload: dict[str, Any], label: str) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"Unsupported {label} schema version: {_bounded_field_repr(payload, 'schema_version')}; "
            "expected: 1"
        )


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _validate_claim_kind(claim_id: str, claim: dict[str, Any]) -> None:
    kind = claim.get("kind")
    if "kind" in claim and (not isinstance(kind, str) or kind not in CLAIM_STRENGTHS):
        raise ValueError(
            f"Invalid claim kind for {claim_id}: {_bounded_repr(kind)}; "
            f"allowed: {sorted(CLAIM_STRENGTHS)}"
        )


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {label}: {path.name}: {error}") from error
    return _mapping(payload, label)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid query ledger JSON at {path.name}:{line_number}: {error}"
            ) from error
        records.append(_mapping(payload, f"query ledger line {line_number}"))
    return records


def _validate_claim_register(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    _schema_one(payload, "claim register")
    claims = _list(payload.get("claims"), "claim register claims")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(claims):
        claim = _mapping(raw, f"claim register claim {index}")
        claim_id = _text(claim.get("id"), f"claim register claim {index} id")
        if claim_id in by_id:
            raise ValueError(f"Duplicate claim register id: {claim_id}")
        _text(claim.get("text"), f"claim {claim_id} text")
        _text(claim.get("permitted_inference"), f"claim {claim_id} permitted_inference")
        status = _text(claim.get("status"), f"claim {claim_id} status")
        if status not in CLAIM_STATUSES:
            raise ValueError(
                f"Invalid claim status for {claim_id}: {_bounded_repr(status)}; "
                f"allowed: {sorted(CLAIM_STATUSES)}"
            )
        _text(claim.get("falsifier"), f"claim {claim_id} falsifier")
        _text(claim.get("uncertainty"), f"claim {claim_id} uncertainty")
        _text(claim.get("next_action"), f"claim {claim_id} next_action")
        _validate_claim_kind(claim_id, claim)
        required_support = claim.get("required_support", 1)
        if (
            not isinstance(required_support, int)
            or isinstance(required_support, bool)
            or required_support < 0
        ):
            raise ValueError(
                f"claim {claim_id} required_support must be a non-negative integer: "
                f"{_bounded_repr(required_support)}; expected: non-negative integer"
            )
        for field in ("required_evidence", "dependencies"):
            if field in claim:
                _string_list(claim[field], f"claim {claim_id} {field}")
        by_id[claim_id] = claim
    return by_id


def _validate_evidence_graph(
    payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    _schema_one(payload, "evidence graph")
    nodes = _list(payload.get("nodes"), "evidence graph nodes")
    edges = _list(payload.get("edges"), "evidence graph edges")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(nodes):
        node = _mapping(raw, f"evidence node {index}")
        node_id = _text(node.get("id"), f"evidence node {index} id")
        if node_id in by_id:
            raise ValueError(f"Duplicate evidence node id: {node_id}")
        node_type = _text(node.get("type"), f"evidence node {node_id} type")
        if node_type not in NODE_TYPES:
            raise ValueError(
                f"Invalid evidence node type for {node_id}: {_bounded_repr(node_type)}; "
                f"allowed: {sorted(NODE_TYPES)}"
            )
        by_id[node_id] = node

    seen_edges: set[tuple[str, str, str]] = set()
    normalized_edges: list[dict[str, Any]] = []
    for index, raw in enumerate(edges):
        edge = _mapping(raw, f"evidence edge {index}")
        source = _text(edge.get("source"), f"evidence edge {index} source")
        target = _text(edge.get("target"), f"evidence edge {index} target")
        relation = _text(edge.get("relation"), f"evidence edge {index} relation")
        if source not in by_id or target not in by_id:
            raise ValueError(f"Evidence edge endpoint is missing: {source} -> {target}")
        if relation not in RELATIONS:
            raise ValueError(
                f"Invalid evidence relation: {_bounded_repr(relation)}; allowed: {sorted(RELATIONS)}"
            )
        key = (source, target, relation)
        if key in seen_edges:
            raise ValueError(f"Duplicate evidence edge: {source} {relation} {target}")
        seen_edges.add(key)
        normalized_edges.append(edge)
    return by_id, normalized_edges


def _validate_query_records(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        query_id = _text(record.get("query_id"), f"query ledger record {index} query_id")
        if query_id in by_id:
            raise ValueError(f"Duplicate query id: {query_id}")
        _text(record.get("source"), f"query {query_id} source")
        _text(record.get("query"), f"query {query_id} query")
        _text(record.get("accessed_at"), f"query {query_id} accessed_at")
        status = _text(record.get("status"), f"query {query_id} status")
        if status not in QUERY_STATUSES:
            raise ValueError(
                f"Invalid query status for {query_id}: {_bounded_repr(status)}; "
                f"allowed: {sorted(QUERY_STATUSES)}"
            )
        digest = record.get("response_sha256")
        if digest is not None and not _valid_sha256(str(digest)):
            raise ValueError(
                f"Invalid response_sha256 for query {query_id}: {_bounded_repr(digest)}; "
                "expected: 64 hexadecimal characters"
            )
        by_id[query_id] = record
    return by_id


def _normalise_excerpt(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _support_source_path(run_dir: Path, artifact: Any, study_id: str, claim_id: str) -> Path:
    label = f"Study {study_id} claim {claim_id}"
    relative = Path(_text(artifact, f"{label} source_artifact"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} excerpt_source_missing: source_artifact must be run-relative")
    root = run_dir.resolve()
    candidate = run_dir / relative
    try:
        current = run_dir
        for part in relative.parts:
            current = current / part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError("symlink")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        metadata = candidate.stat()
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        raise ValueError(f"{label} excerpt_source_missing: source_artifact is missing or unsafe") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_SUPPORT_SOURCE_BYTES:
        raise ValueError(f"{label} excerpt_source_missing: source_artifact must be a regular file under 10 MiB")
    return resolved


def _validate_study_table(payload: dict[str, Any], run_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Validate excerpt shape always; verify source content when run_dir is available."""
    _schema_one(payload, "study table")
    studies = _list(payload.get("studies"), "study table studies")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(studies):
        study = _mapping(raw, f"study {index}")
        study_id = _text(study.get("study_id"), f"study {index} study_id")
        if study_id in by_id:
            raise ValueError(f"Duplicate study id: {study_id}")
        _text(study.get("persistent_id"), f"study {study_id} persistent_id")
        _text(study.get("title"), f"study {study_id} title")
        evidence_type = _text(study.get("evidence_type"), f"study {study_id} evidence_type")
        if evidence_type not in EVIDENCE_TYPES:
            raise ValueError(
                f"Invalid evidence type for study {study_id}: {_bounded_repr(evidence_type)}; "
                f"allowed: {sorted(EVIDENCE_TYPES)}"
            )
        if not isinstance(study.get("included"), bool):
            raise ValueError(
                f"study {study_id} included must be boolean: {_bounded_field_repr(study, 'included')}; "
                "expected: boolean"
            )
        for field in ("supports_claim_ids", "contradicts_claim_ids"):
            study[field] = _string_list(study.get(field, []), f"study {study_id} {field}")
        if "support_excerpts" in study:
            excerpts = _list(study["support_excerpts"], f"study {study_id} support_excerpts")
            linked_claims = set(study.get("supports_claim_ids", [])) | set(study.get("contradicts_claim_ids", []))
            for index, raw_excerpt in enumerate(excerpts):
                excerpt = _mapping(raw_excerpt, f"study {study_id} support excerpt {index}")
                claim_id = _text(excerpt.get("claim_id"), f"study {study_id} excerpt claim_id")
                label = f"Study {study_id} claim {claim_id}"
                if claim_id not in linked_claims:
                    raise ValueError(f"{label} excerpt claim is not linked to this study")
                text = excerpt.get("text")
                if not isinstance(text, str):
                    raise ValueError(f"{label} excerpt text must be a string")
                if not 20 <= (text_length := len(text)) <= 2000:
                    raise ValueError(
                        f"{label} excerpt text length must be 20..2000 characters: "
                        f"{text_length} characters; preview: {_bounded_repr(text)}; "
                        "expected: 20..2000 characters; quote only the verbatim "
                        "claim-bearing sentences, not the whole abstract"
                    )
                try:
                    source_artifact = _text(excerpt["source_artifact"], f"{label} source_artifact")
                except (KeyError, ValueError) as error:
                    raise ValueError(f"{label} excerpt_source_missing: source_artifact is required") from error
                try:
                    digest = _text(excerpt.get("source_sha256"), f"{label} source_sha256")
                except ValueError as error:
                    raise ValueError(f"{label} excerpt_hash_mismatch: source_sha256 is required") from error
                if not _valid_sha256(digest):
                    raise ValueError(
                        f"{label} excerpt_hash_mismatch: invalid source_sha256 {_bounded_repr(digest)}; "
                        "expected: 64 hexadecimal characters"
                    )
                if "locator" in excerpt:
                    if not isinstance(excerpt["locator"], dict):
                        raise ValueError(
                            f"{label} locator must be an object: {_bounded_item_repr(excerpt, 'locator')}; "
                            "expected: object"
                        )
                if run_dir is not None:
                    path = _support_source_path(run_dir, source_artifact, study_id, claim_id)
                    content = path.read_bytes()
                    if hashlib.sha256(content).hexdigest() != digest.lower():
                        raise ValueError(f"{label} excerpt_hash_mismatch: source_sha256 does not match")
                    try:
                        source_text = content.decode("utf-8")
                    except UnicodeDecodeError as error:
                        raise ValueError(f"{label} excerpt_source_missing: source is not UTF-8") from error
                    if _normalise_excerpt(text) not in _normalise_excerpt(source_text):
                        raise ValueError(f"{label} excerpt_not_found: text does not occur in source")
                    line = excerpt.get("locator", {}).get("line")
                    if (isinstance(line, int) and not isinstance(line, bool)
                            and not 1 <= line <= len(source_text.splitlines())):
                        raise ValueError(f"{label} locator.line {line} is outside source line count")
        by_id[study_id] = study
    return by_id


def _validate_lane_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    _schema_one(payload, "lane receipt")
    lane_id = _text(payload.get("lane_id"), "lane receipt lane_id")
    _text(payload.get("lane_type"), f"lane {lane_id} lane_type")
    _mapping(payload.get("normalized_inputs"), f"lane {lane_id} normalized_inputs")
    for field in (
        "claim_ids",
        "sources",
        "queries",
        "included_records",
        "excluded_records",
        "outputs",
        "supported_claim_ids",
        "contradicted_claim_ids",
        "dependencies",
        "limitations",
    ):
        value = payload.get(field)
        if field == "sources":
            sources = _list(value, f"lane {lane_id} sources")
            for index, source in enumerate(sources):
                source_record = _mapping(source, f"lane {lane_id} source {index}")
                _text(source_record.get("source"), f"lane {lane_id} source {index} name")
                _text(source_record.get("release"), f"lane {lane_id} source {index} release")
        else:
            _string_list(value, f"lane {lane_id} {field}")
    confidence = _text(payload.get("confidence"), f"lane {lane_id} confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(
            f"Invalid lane confidence for {lane_id}: {_bounded_repr(confidence)}; "
            f"allowed: {sorted(CONFIDENCE_LEVELS)}"
        )
    _text(payload.get("next_action"), f"lane {lane_id} next_action")
    return payload


def _validate_literature_snapshot(payload: dict[str, Any]) -> None:
    from codex_science.literature import validate_review_snapshot

    validate_review_snapshot(payload)


def load_sidecars(
    manifest: dict[str, Any],
    run_dir: Path,
    verified: dict[str, Path],
) -> dict[str, Any]:
    """Load sidecar artifacts without applying cross-file semantics."""

    loaded: dict[str, Any] = {
        "claim_register": None,
        "evidence_graph": None,
        "study_table": None,
        "literature_snapshot": None,
        "lane_receipts": [],
        "query_ledgers": [],
        "query_records": [],
        "model_receipts": [],
        "paths": {},
    }
    seen_singletons: set[str] = set()
    for record in manifest.get("artifacts", []):
        kind = str(record.get("kind", ""))
        if kind not in SIDECAR_KINDS:
            continue
        relative = str(record["path"])
        path = verified[relative]
        loaded["paths"].setdefault(kind, []).append(relative)
        if kind in SINGLETON_KINDS:
            if kind in seen_singletons:
                raise ValueError(f"Only one {kind} artifact is allowed")
            seen_singletons.add(kind)
            loaded[SINGLETON_KINDS[kind]] = _load_json(path, kind)
        elif kind == "lane-receipt":
            loaded["lane_receipts"].append(_load_json(path, kind))
        elif kind == "query-ledger":
            records = _load_jsonl(path)
            loaded["query_ledgers"].append({"path": relative, "records": records})
            loaded["query_records"].extend(records)
        elif kind == "model-receipt":
            loaded["model_receipts"].append(_load_json(path, kind))
    return loaded


def _verified_artifact_path(
    manifest: dict[str, Any], verified: dict[str, Path], kind: str, *, suffix: str | None = None,
) -> Path | None:
    paths = [
        verified[record["path"]] for record in manifest.get("artifacts", [])
        if record.get("kind") == kind and record.get("path") in verified
        and (suffix is None or record["path"].endswith(suffix))
    ]
    if kind in {"screening-table", "report"} and len(paths) > 1:
        raise ValueError(f"commitment_ledger requires only one {kind} artifact; actual: {len(paths)}")
    return paths[0] if paths else None


def _validate_screening_table(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "screening-table-v1":
        raise ValueError("screening.json schema must be screening-table-v1")
    seen: set[str] = set()
    for index, raw in enumerate(_list(payload.get("records"), "screening.json records")):
        record = _mapping(raw, f"screening.json record {index}")
        record_id = _text(record.get("record_id"), f"screening.json record {index} record_id")
        if record_id in seen:
            raise ValueError(f"screening.json duplicate record_id: {record_id}")
        seen.add(record_id)
        if record.get("decision") not in ("include", "exclude", "awaiting-full-text"):
            raise ValueError(f"screening.json record {record_id} has invalid decision: {_bounded_field_repr(record, 'decision')}")


def validate_sidecars(
    manifest: dict[str, Any],
    run_dir: Path,
    verified: dict[str, Path],
) -> dict[str, Any]:
    """Validate optional sidecars and their cross-file references."""

    loaded = load_sidecars(manifest, run_dir, verified)
    manifest_claims = {
        str(claim["id"]).strip(): claim
        for claim in manifest.get("claims", [])
        if isinstance(claim, dict) and claim.get("id") is not None
    }
    manifest_claim_ids = set(manifest_claims)
    for claim_id, claim in manifest_claims.items():
        _validate_claim_kind(claim_id, claim)
    artifact_paths = set(verified)

    claim_by_id: dict[str, dict[str, Any]] = {}
    if loaded["claim_register"] is not None:
        claim_by_id = _validate_claim_register(loaded["claim_register"])
        if set(claim_by_id) != manifest_claim_ids:
            missing = sorted(manifest_claim_ids - set(claim_by_id))
            extra = sorted(set(claim_by_id) - manifest_claim_ids)
            raise ValueError(
                "Manifest and claim register IDs differ: "
                f"missing={missing or 'none'} extra={extra or 'none'}"
            )
        for claim_id, registered_claim in claim_by_id.items():
            manifest_claim = manifest_claims.get(claim_id)
            if (
                manifest_claim is not None
                and "kind" in manifest_claim
                and "kind" in registered_claim
                and manifest_claim["kind"] != registered_claim["kind"]
            ):
                raise ValueError(f"Claim {claim_id} kind differs between manifest and claim register")

    node_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    if loaded["evidence_graph"] is not None:
        node_by_id, edges = _validate_evidence_graph(loaded["evidence_graph"])
        graph_claim_ids = {
            node_id for node_id, node in node_by_id.items() if node.get("type") == "claim"
        }
        expected_claim_ids = set(claim_by_id) or manifest_claim_ids
        if graph_claim_ids != expected_claim_ids:
            raise ValueError(
                "Evidence graph claim nodes differ from registered claims: "
                f"expected={sorted(expected_claim_ids)} actual={sorted(graph_claim_ids)}"
            )

    query_by_id = _validate_query_records(loaded["query_records"])

    study_by_id: dict[str, dict[str, Any]] = {}
    if loaded["study_table"] is not None:
        study_by_id = _validate_study_table(loaded["study_table"], run_dir)
        known_claims = set(claim_by_id) or manifest_claim_ids
        for study_id, study in study_by_id.items():
            for field in ("supports_claim_ids", "contradicts_claim_ids"):
                unknown = set(study.get(field, [])) - known_claims
                if unknown:
                    raise ValueError(
                        f"Study {study_id} references unknown claims in {field}: {sorted(unknown)}"
                    )
    protocols: list[tuple[str, dict[str, Any]]] = []
    for record in manifest.get("artifacts", []):
        relative = record.get("path")
        if record.get("kind") != "protocol" or relative not in verified or not relative.endswith(".json"):
            continue
        raw = verified[relative].read_text(encoding="utf-8")
        try:
            protocol = json.loads(raw)
        except json.JSONDecodeError as error:
            if "commitment_ledger" in raw:
                raise ValueError(f"Invalid JSON in protocol: {relative}: {error}") from error
            continue
        if not isinstance(protocol, dict):
            if "commitment_ledger" in raw:
                raise ValueError(f"protocol {relative} must be an object to declare commitment_ledger")
            continue
        if "commitment_ledger" in protocol:
            protocols.append((relative, protocol))
    if len(protocols) > 1:
        raise ValueError(
            f"commitment_ledger is declared in {len(protocols)} protocol artifacts: "
            f"{sorted(relative for relative, _ in protocols)}; must be declared in exactly one"
        )
    if protocols:
        ledger = protocols[0][1]["commitment_ledger"]
        if not isinstance(ledger, dict):
            raise ValueError("protocol.json commitment_ledger must be an object; actual: " + type(ledger).__name__)
        procedures = ledger.get("procedures")
        screening = None
        if procedures != []:
            screening_path = _verified_artifact_path(manifest, verified, "screening-table")
            if screening_path is not None:
                screening = _load_json(screening_path, "screening.json")
                _validate_screening_table(screening)
        needs_report = isinstance(procedures, list) and any(
            isinstance(procedure, dict)
            and isinstance(procedure.get("completed_count"), int)
            and isinstance(procedure.get("denominator"), int)
            and procedure["completed_count"] < procedure["denominator"]
            and isinstance(procedure.get("deviation"), dict)
            and procedure["deviation"].get("affected_claims")
            for procedure in procedures
        )
        context = commitment_ledger.validate_ledger(
            ledger,
            study_table_payload=loaded["study_table"],
            screening_payload=screening,
            claim_ids=set(claim_by_id) or manifest_claim_ids,
            verified=verified,
            report_path=_verified_artifact_path(manifest, verified, "report") if needs_report else None,
        )
        if context["procedures"]:
            loaded["protocol_commitment_context"] = context

    if loaded["study_table"] is not None and node_by_id:
        graph_study_ids = {
            node_id for node_id, node in node_by_id.items() if node.get("type") == "study"
        }
        if graph_study_ids != set(study_by_id):
            raise ValueError(
                "Evidence graph study nodes differ from study table: "
                f"expected={sorted(study_by_id)} actual={sorted(graph_study_ids)}"
            )

    lane_ids: set[str] = set()
    known_claims = set(claim_by_id) or manifest_claim_ids
    for raw in loaded["lane_receipts"]:
        lane = _validate_lane_receipt(raw)
        lane_id = str(lane["lane_id"])
        if lane_id in lane_ids:
            raise ValueError(f"Duplicate lane receipt id: {lane_id}")
        lane_ids.add(lane_id)
        claim_refs = set(lane["claim_ids"]) | set(lane["supported_claim_ids"]) | set(
            lane["contradicted_claim_ids"]
        )
        unknown_claims = claim_refs - known_claims
        if unknown_claims:
            raise ValueError(f"Lane {lane_id} references unknown claims: {sorted(unknown_claims)}")
        unknown_queries = set(lane["queries"]) - set(query_by_id)
        if unknown_queries:
            raise ValueError(f"Lane {lane_id} references unknown queries: {sorted(unknown_queries)}")
        unknown_outputs = set(lane["outputs"]) - artifact_paths
        if unknown_outputs:
            raise ValueError(f"Lane {lane_id} references unsaved outputs: {sorted(unknown_outputs)}")

    if loaded["literature_snapshot"] is not None:
        _validate_literature_snapshot(loaded["literature_snapshot"])

    if loaded["model_receipts"]:
        from codex_science.models import validate_model_receipt

        for receipt in loaded["model_receipts"]:
            validate_model_receipt(receipt)

    loaded["claim_by_id"] = claim_by_id
    loaded["node_by_id"] = node_by_id
    loaded["edges"] = edges
    loaded["query_by_id"] = query_by_id
    loaded["study_by_id"] = study_by_id
    loaded["lane_by_id"] = {str(item["lane_id"]): item for item in loaded["lane_receipts"]}
    return loaded


def _persistent_id(value: Any) -> str:
    text = str(value).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.rstrip("/")


def review_sidecars(sidecars: dict[str, Any]) -> list[dict[str, str]]:
    """Return record/source-level findings from validated sidecars."""

    findings: list[dict[str, str]] = []

    def add(code: str, severity: str, message: str, claim_id: str = "") -> None:
        finding = {"code": code, "severity": severity, "message": message}
        if claim_id:
            finding["claim_id"] = claim_id
        findings.append(finding)

    claims: dict[str, dict[str, Any]] = sidecars.get("claim_by_id", {})
    edges: list[dict[str, Any]] = sidecars.get("edges", [])
    studies: dict[str, dict[str, Any]] = sidecars.get("study_by_id", {})
    queries: dict[str, dict[str, Any]] = sidecars.get("query_by_id", {})

    duplicate_groups: dict[str, list[str]] = defaultdict(list)
    for study_id, study in studies.items():
        duplicate_groups[_persistent_id(study.get("persistent_id"))].append(study_id)
    for persistent_id, study_ids in sorted(duplicate_groups.items()):
        if persistent_id and len(study_ids) > 1:
            add(
                "duplicate-study",
                "major",
                f"Multiple study records share persistent ID {persistent_id}: {', '.join(sorted(study_ids))}",
            )

    support_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contradiction_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        target = str(edge["target"])
        if edge["relation"] == "supports":
            support_edges[target].append(edge)
        elif edge["relation"] == "contradicts":
            contradiction_edges[target].append(edge)

        source = str(edge["source"])
        if target in claims and source in studies:
            declared_field = (
                "supports_claim_ids" if edge["relation"] == "supports" else "contradicts_claim_ids"
            )
            if edge["relation"] in {"supports", "contradicts"} and target not in studies[
                source
            ].get(declared_field, []):
                add(
                    "citation-mismatch",
                    "major",
                    f"Graph says {source} {edge['relation']} {target}, but the study table does not declare that relationship.",
                    target,
                )

    for claim_id, claim in claims.items():
        status = str(claim.get("status"))
        supports = support_edges.get(claim_id, [])
        contradictions = contradiction_edges.get(claim_id, [])
        required_support = int(claim.get("required_support", 1))
        if status in {"supported", "replicated", "suggestive"} and len(supports) < required_support:
            add(
                "unsupported-conclusion",
                "major",
                f"Claim {claim_id} is {status} but has {len(supports)} supporting edge(s); {required_support} required.",
                claim_id,
            )

        required_evidence = set(claim.get("required_evidence", []))
        if "primary" in required_evidence:
            primary_sources = [
                edge
                for edge in supports
                if studies.get(str(edge["source"]), {}).get("evidence_type") == "primary"
            ]
            if not primary_sources:
                add(
                    "missing-primary-evidence",
                    "major",
                    f"Claim {claim_id} requires primary evidence but none supports it.",
                    claim_id,
                )

        if contradictions and status in {"supported", "replicated"} and not str(
            claim.get("contradiction_resolution", "")
        ).strip():
            add(
                "unresolved-contradiction",
                "major",
                f"Claim {claim_id} has contradicting evidence without a recorded resolution.",
                claim_id,
            )

        if status == "replicated":
            independence_groups: set[str] = set()
            for edge in supports:
                source = str(edge["source"])
                group = str(edge.get("independence_group") or "").strip()
                if not group and source in studies:
                    group = str(studies[source].get("cohort_id") or "").strip()
                independence_groups.add(group or source)
            if len(independence_groups) < 2:
                add(
                    "dependent-evidence",
                    "major",
                    f"Claim {claim_id} is labeled replicated without two independent evidence groups.",
                    claim_id,
                )

    for lane in sidecars.get("lane_receipts", []):
        lane_id = str(lane["lane_id"])
        bad_queries = [
            query_id
            for query_id in lane["queries"]
            if queries[query_id]["status"] in {"failed", "unavailable"}
        ]
        if bad_queries and lane["supported_claim_ids"]:
            add(
                "unavailable-query-used",
                "major",
                f"Lane {lane_id} supports claims despite failed or unavailable queries: {', '.join(bad_queries)}",
            )

    for receipt in sidecars.get("model_receipts", []):
        from codex_science.models import review_model_receipt

        findings.extend(review_model_receipt(receipt))

    findings.sort(
        key=lambda item: (
            item.get("severity", ""),
            item["code"],
            item.get("claim_id", ""),
            item["message"],
        )
    )
    return findings
