"""Typed, replayable contracts for read-only scientific connectors."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import re
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

SECRET_RE = re.compile(r"(?:key|token|secret|password|credential)", re.I)
QUERY_STATUSES = {"complete", "partial", "failed", "unavailable", "environment-blocked"}
COMPLETENESS_STATES = {"complete", "bounded", "partial-next-cursor", "normalized-only", "unavailable"}
DRIFT_TYPES = {"none", "schema-drift", "pagination-drift", "release-drift", "response-drift", "semantic-drift"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, "[REDACTED]" if SECRET_RE.search(key) else value) for key, value in query]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment))


def _json_value(value: Any, label: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings")
            _json_value(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} must contain JSON-compatible values")


@dataclass(frozen=True)
class QueryRequest:
    source: str
    operation: str
    parameters: dict[str, Any]
    page_size: int = 5
    max_pages: int = 1
    evidence_cutoff: str | None = None
    source_contract_version: str = "2"

    def validate(self) -> None:
        if not self.source.strip() or not self.operation.strip():
            raise ValueError("source and operation are required")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be an object")
        _json_value(self.parameters, "parameters")
        if isinstance(self.page_size, bool) or not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if isinstance(self.max_pages, bool) or not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if len(canonical_json_bytes(self.parameters)) > 32768:
            raise ValueError("parameters are too large")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QueryRequest":
        request = cls(
            source=str(payload.get("source", "")),
            operation=str(payload.get("operation", "search")),
            parameters=dict(payload.get("parameters") or {}),
            page_size=int(payload.get("page_size", 5)),
            max_pages=int(payload.get("max_pages", 1)),
            evidence_cutoff=None if payload.get("evidence_cutoff") is None else str(payload["evidence_cutoff"]),
            source_contract_version=str(payload.get("source_contract_version", "2")),
        )
        request.validate()
        return request

    def canonical(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @property
    def request_sha256(self) -> str:
        return sha256_json(self.canonical())

    @property
    def query_id(self) -> str:
        return f"q-{self.request_sha256[:24]}"


@dataclass(frozen=True)
class PageReceipt:
    request_url: str
    request_method: str
    request_body_sha256: str | None
    page_index: int
    response_sha256: str
    response_media_type: str
    etag: str | None
    last_modified: str | None
    retrieved_at: str
    next_cursor: str | None
    record_count: int


@dataclass(frozen=True)
class QueryReceipt:
    schema_version: int
    query_id: str
    canonical_request_sha256: str
    source: str
    operation: str
    source_contract_version: str
    source_release: str | None
    status: str
    completeness: str
    pages: tuple[PageReceipt, ...]
    returned_record_ids: tuple[str, ...]
    excluded_records: tuple[dict[str, Any], ...]
    missingness: str
    warnings: tuple[str, ...]
    normalized_records_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryResult:
    request: QueryRequest
    records: tuple[dict[str, Any], ...]
    receipt: QueryReceipt
    snapshot_pages: tuple[dict[str, Any], ...] = ()

    def to_dict(self, *, include_snapshot: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"records": [dict(item) for item in self.records], "receipt": self.receipt.to_dict()}
        if include_snapshot:
            result["snapshot"] = self.snapshot()
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "request": self.request.canonical(),
            "records": [dict(item) for item in self.records],
            "receipt": self.receipt.to_dict(),
            "pages": [copy.deepcopy(item) for item in self.snapshot_pages],
        }


@dataclass
class _Call:
    method: str
    url: str
    request_payload: Any
    response_payload: Any
    raw: bytes
    media_type: str


def _cursor(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("nextCursor", "nextPageToken", "next_page_token", "cursor"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    links = payload.get("_links") or payload.get("links")
    if isinstance(links, dict):
        value = links.get("next")
        if isinstance(value, dict):
            value = value.get("href")
        if isinstance(value, str) and value:
            return value
    return None


def _release(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("release", "release_version", "releaseVersion", "data_release", "dataRelease", "version", "genomeBuild"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("release", "version", "data_release"):
            if meta.get(key) not in (None, ""):
                return str(meta[key])
    return None


@contextlib.contextmanager
def _instrument(connector: Any) -> Iterator[list[_Call]]:
    calls: list[_Call] = []
    originals: dict[str, Any] = {}
    for name, method, media in (("_fetch_json", "GET", "application/json"), ("_fetch_text", "GET", "text/plain")):
        if not hasattr(connector, name):
            continue
        original = getattr(connector, name)
        originals[name] = original
        def wrapper(url: str, _original=original, _method=method, _media=media):
            payload = _original(url)
            raw = canonical_json_bytes(payload) if _media == "application/json" else str(payload).encode("utf-8")
            calls.append(_Call(_method, _redact_url(url), None, copy.deepcopy(payload), raw, _media))
            return payload
        setattr(connector, name, wrapper)
    if hasattr(connector, "_post_json"):
        original = connector._post_json
        originals["_post_json"] = original
        def post(url: str, request_payload: dict[str, Any]):
            payload = original(url, request_payload)
            calls.append(_Call("POST", _redact_url(url), copy.deepcopy(request_payload), copy.deepcopy(payload), canonical_json_bytes(payload), "application/json"))
            return payload
        connector._post_json = post
    try:
        yield calls
    finally:
        for name, original in originals.items():
            setattr(connector, name, original)


def execute_connector(connector: Any, request: QueryRequest, *, include_snapshot: bool = False, retrieved_at: str | None = None) -> QueryResult:
    request.validate()
    if request.operation != "search" and not hasattr(connector, "query_v2"):
        raise ValueError(f"connector does not implement operation: {request.operation}")
    warnings: list[str] = []
    timestamp = retrieved_at or _now()
    with _instrument(connector) as calls:
        if hasattr(connector, "query_v2"):
            records = connector.query_v2(request)
        else:
            query = request.parameters.get("query")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("search requires parameters.query")
            if request.max_pages > 1:
                warnings.append("legacy connector exposes no cursor pagination; result is bounded")
            records = connector.search(query, limit=min(request.page_size * request.max_pages, 10))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("connector must return record objects")
    normalized = [dict(item) for item in records]
    pages: list[PageReceipt] = []
    snapshots: list[dict[str, Any]] = []
    source_release: str | None = None
    cursors: list[str] = []
    for index, call in enumerate(calls):
        cursor = _cursor(call.response_payload)
        if cursor:
            cursors.append(cursor)
        source_release = source_release or _release(call.response_payload)
        body_digest = None if call.request_payload is None else hashlib.sha256(canonical_json_bytes(call.request_payload)).hexdigest()
        pages.append(PageReceipt(
            request_url=call.url, request_method=call.method, request_body_sha256=body_digest,
            page_index=index, response_sha256=hashlib.sha256(call.raw).hexdigest(),
            response_media_type=call.media_type, etag=None, last_modified=None,
            retrieved_at=timestamp, next_cursor=cursor, record_count=len(normalized),
        ))
        snapshots.append({"method": call.method, "url": call.url, "request": copy.deepcopy(call.request_payload), "response": copy.deepcopy(call.response_payload)})
    completeness = "partial-next-cursor" if cursors else ("bounded" if request.max_pages > 1 else ("complete" if calls else "normalized-only"))
    missingness = "negative" if not normalized else "observed"
    ids = tuple(str(item.get("id") or f"record-{index}") for index, item in enumerate(normalized))
    receipt = QueryReceipt(
        schema_version=1, query_id=request.query_id, canonical_request_sha256=request.request_sha256,
        source=request.source, operation=request.operation, source_contract_version=request.source_contract_version,
        source_release=source_release, status="complete", completeness=completeness,
        pages=tuple(pages), returned_record_ids=ids, excluded_records=(), missingness=missingness,
        warnings=tuple(warnings), normalized_records_sha256=sha256_json(normalized),
    )
    return QueryResult(request, tuple(normalized), receipt, tuple(snapshots) if include_snapshot else ())


def save_snapshot(path: Path, result: QueryResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replay_snapshot(payload: Mapping[str, Any]) -> QueryResult:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported connector snapshot schema")
    request = QueryRequest.from_payload(payload.get("request") or {})
    records = [dict(item) for item in payload.get("records") or []]
    receipt_payload = dict(payload.get("receipt") or {})
    if receipt_payload.get("canonical_request_sha256") != request.request_sha256:
        raise ValueError("snapshot request hash mismatch")
    if receipt_payload.get("normalized_records_sha256") != sha256_json(records):
        raise ValueError("snapshot record hash mismatch")
    pages = tuple(PageReceipt(**item) for item in receipt_payload.get("pages") or [])
    receipt_payload["pages"] = pages
    for field in ("returned_record_ids", "excluded_records", "warnings"):
        receipt_payload[field] = tuple(receipt_payload.get(field) or [])
    receipt = QueryReceipt(**receipt_payload)
    return QueryResult(request, tuple(records), receipt, tuple(payload.get("pages") or []))


def classify_drift(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    old = replay_snapshot(previous)
    new = replay_snapshot(current)
    changes: list[str] = []
    if old.request.canonical() != new.request.canonical():
        changes.append("schema-drift")
    if len(old.receipt.pages) != len(new.receipt.pages) or [p.next_cursor for p in old.receipt.pages] != [p.next_cursor for p in new.receipt.pages]:
        changes.append("pagination-drift")
    if old.receipt.source_release != new.receipt.source_release:
        changes.append("release-drift")
    if [p.response_sha256 for p in old.receipt.pages] != [p.response_sha256 for p in new.receipt.pages]:
        changes.append("response-drift")
    if old.receipt.normalized_records_sha256 != new.receipt.normalized_records_sha256:
        changes.append("semantic-drift")
    return {"status": "changed" if changes else "unchanged", "drift_types": changes or ["none"], "previous_query_id": old.receipt.query_id, "current_query_id": new.receipt.query_id}
