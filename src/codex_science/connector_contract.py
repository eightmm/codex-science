"""Typed, replayable contracts for read-only scientific connectors."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Any, Iterator, Mapping

_record_counts: ContextVar[list[int] | None] = ContextVar("connector_record_counts", default=None)

SECRET_RE = re.compile(r"(?:key|token|secret|password|credential)", re.I)
QUERY_STATUSES = {"complete", "partial", "failed", "unavailable", "environment-blocked"}
def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


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
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must contain finite JSON numbers")
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
        if any(not isinstance(value, str) or not value.strip() for value in (self.source, self.operation)):
            raise ValueError("source and operation must be non-empty strings")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be an object")
        _json_value(self.parameters, "parameters")
        if isinstance(self.page_size, bool) or not isinstance(self.page_size, int):
            raise ValueError("page_size must be an integer")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if isinstance(self.max_pages, bool) or not isinstance(self.max_pages, int):
            raise ValueError("max_pages must be an integer")
        if not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if len(canonical_json_bytes(self.parameters)) > 32768:
            raise ValueError("parameters are too large")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QueryRequest":
        if not isinstance(payload, Mapping):
            raise ValueError("connector request must be an object")
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be an object")
        request = cls(
            source=payload.get("source", ""),
            operation=payload.get("operation", "search"),
            parameters=dict(parameters),
            page_size=payload.get("page_size", 5),
            max_pages=payload.get("max_pages", 1),
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
    value = payload.get("next")
    if isinstance(value, str) and value:
        return value
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


def _total(payload: Any) -> int:
    if isinstance(payload, str):
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return 0
        value = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
        return int(value) if value and re.fullmatch(r"[0-9]+", value) else 0
    if not isinstance(payload, dict):
        return 0
    totals = [0]
    for key in (
        "count", "total", "total_count", "totalResults", "hitCount", "numberOfHits", "totalElements",
        "numFound", "totalCount", "entriesCount", "totalHits", "totalNumberOfItems", "totalNumberOfElements",
    ):
        value = payload.get(key)
        if type(value) is int and value >= 0:
            totals.append(value)
        elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            totals.append(int(value))
    for key in ("esearchresult", "meta", "results", "page_meta", "page", "pageInfo", "pagination", "response", "paging_info"):
        if isinstance(payload.get(key), dict):
            totals.append(_total(payload[key]))
    return max(totals)


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
def _instrument(connector: Any) -> Iterator[tuple[list[_Call], list[int]]]:
    calls: list[_Call] = []
    received_counts: list[int] = []
    originals: dict[str, Any] = {}
    for name, method, media in (("_fetch_json", "GET", "application/json"), ("_fetch_text", "GET", "text/plain")):
        if not hasattr(connector, name):
            continue
        original = getattr(connector, name)
        originals[name] = original
        def wrapper(url: str, _original=original, _method=method, _media=media):
            payload = _original(url)
            validate_response = getattr(connector, "_validate_response", None)
            if validate_response is not None:
                validate_response(payload)
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
    tracking = _record_counts.set(received_counts)
    try:
        yield calls, received_counts
    finally:
        _record_counts.reset(tracking)
        for name, original in originals.items():
            setattr(connector, name, original)


def execute_connector(connector: Any, request: QueryRequest, *, include_snapshot: bool = False, retrieved_at: str | None = None) -> QueryResult:
    request.validate()
    typed_query = hasattr(connector, "query_v2")
    if request.operation != "search" and not typed_query:
        raise ValueError(f"connector does not implement operation: {request.operation}")
    if request.evidence_cutoff is not None and not typed_query:
        raise ValueError(f"evidence_cutoff is not supported by source: {request.source}")
    if not typed_query:
        unsupported = set(request.parameters) - {"query", "limit"}
        if unsupported:
            raise ValueError(f"unsupported parameters for source {request.source}: {', '.join(sorted(unsupported))}")
        limit = request.parameters.get("limit", 10)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("parameters.limit must be an integer between 1 and 10")
    warnings: list[str] = []
    timestamp = retrieved_at or _now()
    with _instrument(connector) as (calls, received_counts):
        if typed_query:
            records = connector.query_v2(request)
        else:
            query = request.parameters.get("query")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("search requires parameters.query")
            if request.max_pages > 1:
                warnings.append("legacy connector exposes no cursor pagination; result is bounded")
            if request.page_size * request.max_pages > 10:
                warnings.append("legacy connector request is capped at 10 records; result is bounded")
            records = connector.search(query, limit=min(limit, request.page_size * request.max_pages, 10))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("connector must return record objects")
    normalized = [dict(item) for item in records]
    if max(received_counts, default=0) > len(normalized):
        if not normalized:
            raise ValueError("upstream error: response records were discarded; no negative evidence is available")
        warnings.append("local truncation discarded received records; result is bounded")
    pages: list[PageReceipt] = []
    snapshots: list[dict[str, Any]] = []
    source_release: str | None = None
    cursors: list[str] = []
    for index, call in enumerate(calls):
        cursor = _cursor(call.response_payload)
        if cursor:
            cursors.append(cursor)
        if _total(call.response_payload) > len(normalized):
            warnings.append("source declares more records than returned; result is bounded")
        source_release = source_release or _release(call.response_payload)
        body_digest = None if call.request_payload is None else hashlib.sha256(canonical_json_bytes(call.request_payload)).hexdigest()
        pages.append(PageReceipt(
            request_url=call.url, request_method=call.method, request_body_sha256=body_digest,
            page_index=index, response_sha256=hashlib.sha256(call.raw).hexdigest(),
            response_media_type=call.media_type, etag=None, last_modified=None,
            retrieved_at=timestamp, next_cursor=cursor, record_count=len(normalized),
        ))
        snapshots.append({"method": call.method, "url": call.url, "request": copy.deepcopy(call.request_payload), "response": copy.deepcopy(call.response_payload)})
    if cursors:
        warnings.append("source returned a next cursor; result is partial")
    completeness = "partial-next-cursor" if cursors else ("bounded" if warnings or request.max_pages > 1 else ("complete" if calls else "normalized-only"))
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


def replay_snapshot(payload: Mapping[str, Any]) -> QueryResult:
    return _replay_snapshot(payload, verify_responses=True)


def _snapshot_list(value: Any, label: str) -> list[Any] | tuple[Any, ...]:
    if not value:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list")
    return value


def _replay_snapshot(payload: Mapping[str, Any], *, verify_responses: bool) -> QueryResult:
    if not isinstance(payload, Mapping):
        raise ValueError("connector snapshot must be an object")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("unsupported connector snapshot schema")
    request = QueryRequest.from_payload(payload.get("request", {}))
    records_raw = _snapshot_list(payload.get("records", []), "snapshot records")
    if any(not isinstance(item, Mapping) for item in records_raw):
        raise ValueError("snapshot records must be a list of objects")
    records = [dict(item) for item in records_raw]
    receipt_raw = payload.get("receipt", {})
    if not isinstance(receipt_raw, Mapping):
        raise ValueError("snapshot receipt must be an object")
    receipt_payload = dict(receipt_raw)
    if type(receipt_payload.get("schema_version")) is not int or receipt_payload["schema_version"] != 1:
        raise ValueError("unsupported snapshot receipt schema")
    for field in ("returned_record_ids", "excluded_records", "warnings"):
        receipt_payload[field] = tuple(_snapshot_list(receipt_payload.get(field, []), f"snapshot receipt {field}"))
    if any(not isinstance(item, str) for item in receipt_payload["warnings"]):
        raise ValueError("snapshot receipt warnings must contain strings")
    for item in receipt_payload["excluded_records"]:
        if not isinstance(item, dict):
            raise ValueError("snapshot receipt excluded_records must contain objects")
        _json_value(item, "snapshot receipt excluded_records")
    if receipt_payload.get("canonical_request_sha256") != request.request_sha256:
        raise ValueError("snapshot request hash mismatch")
    if receipt_payload.get("query_id") != request.query_id:
        raise ValueError("snapshot receipt query_id mismatch")
    if receipt_payload.get("normalized_records_sha256") != sha256_json(records):
        raise ValueError("snapshot record hash mismatch")
    for field in ("source", "operation", "source_contract_version"):
        if receipt_payload.get(field) != getattr(request, field):
            raise ValueError(f"snapshot receipt {field} mismatch")
    ids = tuple(str(item.get("id") or f"record-{index}") for index, item in enumerate(records))
    if receipt_payload["returned_record_ids"] != ids:
        raise ValueError("snapshot returned record IDs mismatch")
    pages_raw = _snapshot_list(receipt_payload.get("pages", []), "snapshot receipt pages")
    if any(not isinstance(item, Mapping) for item in pages_raw):
        raise ValueError("snapshot receipt pages must be a list of objects")
    try:
        pages = tuple(PageReceipt(**item) for item in pages_raw)
    except TypeError as error:
        raise ValueError(f"invalid snapshot page receipt: {error}") from None
    for page in pages:
        if type(page.record_count) is not int or page.record_count != len(records):
            raise ValueError("snapshot page record count mismatch")
    if "pages" in payload:
        snapshot_pages = payload["pages"]
        if not isinstance(snapshot_pages, (list, tuple)) or (snapshot_pages and len(snapshot_pages) != len(pages)):
            raise ValueError("snapshot page count mismatch")
        for page, stored in zip(pages, snapshot_pages):
            if not isinstance(stored, Mapping):
                raise ValueError("snapshot page must be an object")
            if stored.get("method") != page.request_method:
                raise ValueError("snapshot page request method mismatch")
            if stored.get("url") != page.request_url:
                raise ValueError("snapshot page request URL mismatch")
            body_digest = None if stored.get("request") is None else sha256_json(stored["request"])
            if body_digest != page.request_body_sha256:
                raise ValueError("snapshot page request body hash mismatch")
            if verify_responses:
                response = stored.get("response")
                raw = canonical_json_bytes(response) if page.response_media_type == "application/json" else str(response).encode("utf-8")
                if "response" not in stored or hashlib.sha256(raw).hexdigest() != page.response_sha256:
                    raise ValueError("snapshot page response hash mismatch")
    receipt_payload["pages"] = pages
    try:
        receipt = QueryReceipt(**receipt_payload)
    except TypeError as error:
        raise ValueError(f"invalid snapshot receipt: {error}") from None
    return QueryResult(request, tuple(records), receipt, tuple(payload.get("pages") or []))


def classify_drift(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    # Drift diagnostics compare changed response bytes even when their stored digest is stale.
    old = _replay_snapshot(previous, verify_responses=False)
    new = _replay_snapshot(current, verify_responses=False)
    changes: list[str] = []
    if old.request.canonical() != new.request.canonical():
        changes.append("schema-drift")
    if len(old.receipt.pages) != len(new.receipt.pages) or [p.next_cursor for p in old.receipt.pages] != [p.next_cursor for p in new.receipt.pages]:
        changes.append("pagination-drift")
    if old.receipt.source_release != new.receipt.source_release:
        changes.append("release-drift")
    if (
        [p.response_sha256 for p in old.receipt.pages] != [p.response_sha256 for p in new.receipt.pages]
        or (
            old.snapshot_pages and new.snapshot_pages
            and sha256_json([p.get("response") for p in old.snapshot_pages])
            != sha256_json([p.get("response") for p in new.snapshot_pages])
        )
    ):
        changes.append("response-drift")
    if old.receipt.normalized_records_sha256 != new.receipt.normalized_records_sha256:
        changes.append("semantic-drift")
    return {"status": "changed" if changes else "unchanged", "drift_types": changes or ["none"], "previous_query_id": old.receipt.query_id, "current_query_id": new.receipt.query_id}
