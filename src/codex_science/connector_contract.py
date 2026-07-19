"""Typed, replayable connector contracts layered over read-only source clients."""

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
from typing import Any, Callable, Iterator, Mapping


SECRET_PARAMETER_RE = re.compile(r"(?:key|token|secret|password|credential)", re.IGNORECASE)
QUERY_STATUSES = {"complete", "partial", "failed", "unavailable", "environment-blocked"}
COMPLETENESS_STATES = {
    "complete",
    "bounded",
    "partial-next-cursor",
    "normalized-only",
    "unavailable",
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [
        (key, "[REDACTED]" if SECRET_PARAMETER_RE.search(key) else value)
        for key, value in query
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


def _validate_json_value(value: Any, label: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} keys must be strings")
            _validate_json_value(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} must contain only JSON-compatible values")


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
        if not self.source.strip():
            raise ValueError("source is required")
        if not self.operation.strip():
            raise ValueError("operation is required")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be an object")
        _validate_json_value(self.parameters, "parameters")
        if isinstance(self.page_size, bool) or not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if isinstance(self.max_pages, bool) or not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if len(canonical_json_bytes(self.parameters)) > 32_768:
            raise ValueError("parameters are too large")
        if self.evidence_cutoff is not None and not str(self.evidence_cutoff).strip():
            raise ValueError("evidence_cutoff cannot be empty")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QueryRequest":
        request = cls(
            source=str(payload.get("source", "")),
            operation=str(payload.get("operation", "search")),
            parameters=dict(payload.get("parameters") or {}),
            page_size=int(payload.get("page_size", 5)),
            max_pages=int(payload.get("max_pages", 1)),
            evidence_cutoff=(
                None
                if payload.get("evidence_cutoff") is None
                else str(payload.get("evidence_cutoff"))
            ),
            source_contract_version=str(payload.get("source_contract_version", "2")),
        )
        request.validate()
        return request

    def canonical(self) -> dict[str, Any]:
        self.validate()
        return {
            "source": self.source,
            "operation": self.operation,
            "parameters": self.parameters,
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "evidence_cutoff": self.evidence_cutoff,
            "source_contract_version": self.source_contract_version,
        }

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
        payload = asdict(self)
        payload["pages"] = [asdict(page) for page in self.pages]
        payload["returned_record_ids"] = list(self.returned_record_ids)
        payload["excluded_records"] = list(self.excluded_records)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class QueryResult:
    records: tuple[dict[str, Any], ...]
    receipt: QueryReceipt
    snapshot: dict[str, Any] | None = None

    def to_dict(self, *, include_snapshot: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "records": [dict(record) for record in self.records],
            "receipt": self.receipt.to_dict(),
        }
        if include_snapshot and self.snapshot is not None:
            payload["snapshot"] = copy.deepcopy(self.snapshot)
        return payload


@dataclass
class _CapturedCall:
    kind: str
    method: str
    url: str
    request_payload: Any
    response_payload: Any
    raw_bytes: bytes
    media_type: str


def _next_cursor(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    candidates = (
        payload.get("nextCursor"),
        payload.get("nextPageToken"),
        payload.get("next_page_token"),
        payload.get("cursor"),
    )
    for value in candidates:
        if isinstance(value, str) and value:
            return value
    links = payload.get("_links") or payload.get("links")
    if isinstance(links, dict):
        value = links.get("next")
        if isinstance(value, dict):
            value = value.get("href")
        if isinstance(value, str) and value:
            return value
    meta = payload.get("meta")
    if isinstance(meta, dict):
        value = meta.get("next_cursor") or meta.get("cursor")
        if isinstance(value, str) and value:
            return value
    return None


def _source_release(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in (
        "release",
        "release_version",
        "releaseVersion",
        "data_release",
        "dataRelease",
        "version",
        "genomeBuild",
    ):
        value = payload.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value)
    meta = payload.get("meta")
    if isinstance(meta, dict):
        for key in ("release", "version", "data_release"):
            value = meta.get(key)
            if isinstance(value, (str, int, float)) and str(value).strip():
                return str(value)
    return None


def _record_ids(records: list[dict[str, Any]]) -> tuple[str, ...]:
    result: list[str] = []
    for index, record in enumerate(records):
        value = record.get("id")
        result.append(str(value) if value not in (None, "") else f"record-{index}")
    return tuple(result)


@contextlib.contextmanager
def _instrument(connector: Any) -> Iterator[list[_CapturedCall]]:
    calls: list[_CapturedCall] = []
    originals: dict[str, Any] = {}

    if hasattr(connector, "_fetch_json"):
        originals["_fetch_json"] = connector._fetch_json

        def fetch_json(url: str) -> Any:
            payload = originals["_fetch_json"](url)
            raw = canonical_json_bytes(payload)
            calls.append(
                _CapturedCall(
                    "json",
                    "GET",
                    _redact_url(url),
                    None,
                    copy.deepcopy(payload),
                    raw,
                    "application/json",
                )
            )
            return payload

        connector._fetch_json = fetch_json

    if hasattr(connector, "_fetch_text"):
        originals["_fetch_text"] = connector._fetch_text

        def fetch_text(url: str) -> str:
            payload = originals["_fetch_text"](url)
            raw = str(payload).encode("utf-8")
            calls.append(
                _CapturedCall(
                    "text",
                    "GET",
                    _redact_url(url),
                    None,
                    str(payload),
                    raw,
                    "text/plain",
                )
            )
            return payload

        connector._fetch_text = fetch_text

    if hasattr(connector, "_post_json"):
        originals["_post_json"] = connector._post_json

        def post_json(url: str, request_payload: dict[str, Any]) -> Any:
            payload = originals["_post_json"](url, request_payload)
            raw = canonical_json_bytes(payload)
            calls.append(
                _CapturedCall(
                    "json",
                    "POST",
                    _redact_url(url),
                    copy.deepcopy(request_payload),
                    copy.deepcopy(payload),
                    raw,
                    "application/json",
                )
            )
            return payload

        connector._post_json = post_json

    try:
        yield calls
    finally:
        for name, value in originals.items():
            setattr(connector, name, value)


def execute_connector(
    connector: Any,
    request: QueryRequest,
    *,
    include_snapshot: bool = False,
    retrieved_at: str | None = None,
) -> QueryResult:
    """Execute one bounded, read-only connector request with a replayable receipt."""

    request.validate()
    if request.operation != "search" and not hasattr(connector, "query_v2"):
        raise ValueError(f"Connector does not implement operation: {request.operation}")
    retrieved_at = retrieved_at or _utc_now()
    warnings: list[str] = []
    with _instrument(connector) as calls:
        if hasattr(connector, "query_v2"):
            records = connector.query_v2(request)
        else:
            query = request.parameters.get("query")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("search operation requires parameters.query")
            limit = min(request.page_size * request.max_pages, 10)
            if request.max_pages > 1:
                warnings.append(
                    "legacy connector does not expose cursor pagination; bounded result uses one source request"
                )
            records = connector.search(query, limit=limit)
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("connector must return a list of record objects")
    normalized = [dict(item) for item in records]
    pages: list[PageReceipt] = []
    source_release: str | None = None
    cursors: list[str] = []
    snapshot_pages: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        cursor = _next_cursor(call.response_payload)
        if cursor:
            cursors.append(cursor)
        source_release = source_release or _source_release(call.response_payload)
        request_digest = (
            None
            if call.request_payload is None
            else hashlib.sha256(canonical_json_bytes(call.request_payload)).hexdigest()
        )
        pages.append(
            PageReceipt(
                request_url=call.url,
                request_method=call.method,
                request_body_sha256=request_digest,
                page_index=index,
                response_sha256=hashlib.sha256(call.raw_bytes).hexdigest(),
                response_media_type=call.media_type,
                etag=None,
                last_modified=None,
                retrieved_at=retrieved_at,
                next_cursor=cursor,
                record_count=len(normalized) if len(calls) == 1 else 0,
            )
        )
        snapshot_pages.append(
            {
                "kind": call.kind,
                "method": call.method,
                "url": call.url,
                "request_payload": call.request_payload,
                "response": call.response_payload,
                "response_sha256": hashlib.sha256(call.raw_bytes).hexdigest(),
            }
        )
    if not pages:
        raw = canonical_json_bytes(normalized)
        pages.append(
            PageReceipt(
                request_url=f"connector://{request.source}/{request.operation}",
                request_method="LOCAL",
                request_body_sha256=None,
                page_index=0,
                response_sha256=hashlib.sha256(raw).hexdigest(),
                response_media_type="application/json",
                etag=None,
                last_modified=None,
                retrieved_at=retrieved_at,
                next_cursor=None,
                record_count=len(normalized),
            )
        )
        warnings.append("transport payload was not observable; snapshot contains normalized records only")

    completeness = "partial-next-cursor" if cursors else "complete"
    if len(normalized) >= request.page_size * request.max_pages:
        completeness = "bounded"
    if not calls:
        completeness = "normalized-only"
    receipt = QueryReceipt(
        schema_version=2,
        query_id=request.query_id,
        canonical_request_sha256=request.request_sha256,
        source=request.source,
        operation=request.operation,
        source_contract_version=request.source_contract_version,
        source_release=source_release,
        status="complete" if completeness != "partial-next-cursor" else "partial",
        completeness=completeness,
        pages=tuple(pages),
        returned_record_ids=_record_ids(normalized),
        excluded_records=(),
        missingness="none" if normalized else "no-records-returned",
        warnings=tuple(warnings),
        normalized_records_sha256=sha256_json(normalized),
    )
    snapshot = None
    if include_snapshot:
        snapshot = {
            "schema_version": 2,
            "request": request.canonical(),
            "transport_pages": snapshot_pages,
            "normalized_records": normalized,
            "receipt": receipt.to_dict(),
        }
        snapshot["snapshot_sha256"] = sha256_json(snapshot)
    return QueryResult(tuple(normalized), receipt, snapshot)


def validate_snapshot(snapshot: Mapping[str, Any]) -> None:
    if snapshot.get("schema_version") != 2:
        raise ValueError("unsupported connector snapshot schema")
    request = QueryRequest.from_payload(snapshot.get("request") or {})
    receipt = snapshot.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("connector snapshot has no receipt")
    if receipt.get("canonical_request_sha256") != request.request_sha256:
        raise ValueError("connector snapshot request hash mismatch")
    records = snapshot.get("normalized_records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("connector snapshot normalized_records must be a list of objects")
    if receipt.get("normalized_records_sha256") != sha256_json(records):
        raise ValueError("connector snapshot normalized-record hash mismatch")
    pages = snapshot.get("transport_pages")
    if not isinstance(pages, list):
        raise ValueError("connector snapshot transport_pages must be a list")
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError(f"connector snapshot page {index} must be an object")
        response = page.get("response")
        raw = (
            str(response).encode("utf-8")
            if page.get("kind") == "text"
            else canonical_json_bytes(response)
        )
        if page.get("response_sha256") != hashlib.sha256(raw).hexdigest():
            raise ValueError(f"connector snapshot page {index} hash mismatch")
    expected = snapshot.get("snapshot_sha256")
    if expected is not None:
        material = dict(snapshot)
        material.pop("snapshot_sha256", None)
        if expected != sha256_json(material):
            raise ValueError("connector snapshot envelope hash mismatch")


def replay_snapshot(snapshot: Mapping[str, Any], connector: Any) -> QueryResult:
    """Replay a connector parser from saved transport payloads without network access."""

    validate_snapshot(snapshot)
    request = QueryRequest.from_payload(snapshot["request"])
    pages = list(snapshot["transport_pages"])
    positions = {"json": 0, "text": 0, "post": 0}
    originals: dict[str, Any] = {}

    def next_page(kind: str, method: str) -> Any:
        matching = [page for page in pages if page.get("kind") == kind and page.get("method") == method]
        key = "post" if method == "POST" else kind
        position = positions[key]
        if position >= len(matching):
            raise ValueError(f"snapshot has no remaining {method} {kind} response")
        positions[key] += 1
        return copy.deepcopy(matching[position]["response"])

    if hasattr(connector, "_fetch_json"):
        originals["_fetch_json"] = connector._fetch_json
        connector._fetch_json = lambda _url: next_page("json", "GET")
    if hasattr(connector, "_fetch_text"):
        originals["_fetch_text"] = connector._fetch_text
        connector._fetch_text = lambda _url: next_page("text", "GET")
    if hasattr(connector, "_post_json"):
        originals["_post_json"] = connector._post_json
        connector._post_json = lambda _url, _payload: next_page("json", "POST")
    try:
        replayed = execute_connector(
            connector,
            request,
            include_snapshot=False,
            retrieved_at=str(snapshot["receipt"]["pages"][0]["retrieved_at"]),
        )
    finally:
        for name, value in originals.items():
            setattr(connector, name, value)
    if [dict(item) for item in replayed.records] != snapshot["normalized_records"]:
        raise ValueError("connector replay normalized records differ from snapshot")
    return replayed


def write_snapshot(result: QueryResult, path: Path) -> None:
    if result.snapshot is None:
        raise ValueError("query result was created without a snapshot")
    validate_snapshot(result.snapshot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compare_snapshots(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Classify schema, pagination, release, response, and semantic connector drift."""

    validate_snapshot(previous)
    validate_snapshot(current)
    if previous["request"] != current["request"]:
        raise ValueError("connector snapshots must describe the same canonical request")
    previous_records = list(previous["normalized_records"])
    current_records = list(current["normalized_records"])
    previous_keys = sorted({key for item in previous_records for key in item})
    current_keys = sorted({key for item in current_records for key in item})
    previous_ids = [str(item.get("id", "")) for item in previous_records]
    current_ids = [str(item.get("id", "")) for item in current_records]
    previous_receipt = previous["receipt"]
    current_receipt = current["receipt"]
    classifications: list[str] = []
    if previous_keys != current_keys:
        classifications.append("schema-drift")
    if previous_ids != current_ids:
        classifications.append("semantic-drift")
    if previous_receipt.get("completeness") != current_receipt.get("completeness") or len(
        previous_receipt.get("pages", [])
    ) != len(current_receipt.get("pages", [])):
        classifications.append("pagination-drift")
    if previous_receipt.get("source_release") != current_receipt.get("source_release"):
        classifications.append("release-drift")
    if previous_receipt.get("normalized_records_sha256") != current_receipt.get(
        "normalized_records_sha256"
    ):
        classifications.append("response-drift")
    return {
        "schema_version": 1,
        "query_id": current_receipt["query_id"],
        "source": current_receipt["source"],
        "classifications": classifications or ["no-drift"],
        "previous_record_count": len(previous_records),
        "current_record_count": len(current_records),
        "added_ids": sorted(set(current_ids) - set(previous_ids)),
        "removed_ids": sorted(set(previous_ids) - set(current_ids)),
        "previous_release": previous_receipt.get("source_release"),
        "current_release": current_receipt.get("source_release"),
    }
