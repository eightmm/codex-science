"""Bounded HTTP transport, true pagination, and replay receipts for public science sources."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from codex_science.connector_contract import QueryRequest, sha256_json

SECRET_KEYS = {"authorization", "proxy-authorization", "x-api-key", "api-key", "token", "key"}
TERMINAL_STATUSES = {
    "complete",
    "bounded-by-user",
    "negative",
    "filtered-empty",
    "partial-next-cursor",
    "partial-rate-limit",
    "source-unavailable",
    "authentication-required",
    "schema-drift",
    "normalization-failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        pairs.append((key, "[REDACTED]" if key.lower() in SECRET_KEYS else value))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(pairs), parsed.fragment)
    )


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        str(key).lower(): "[REDACTED]" if str(key).lower() in SECRET_KEYS else str(value)
        for key, value in headers.items()
    }


@dataclass(frozen=True)
class TransportPolicy:
    timeout_seconds: float = 30.0
    max_attempts: int = 3
    backoff_seconds: tuple[float, ...] = (0.0, 0.5, 1.5)
    max_response_bytes: int = 50 * 1024 * 1024
    user_agent: str = "codex-science/0.4 (+https://github.com/eightmm/codex-science)"

    def validate(self) -> None:
        if self.timeout_seconds <= 0 or self.max_attempts < 1 or self.max_response_bytes < 1:
            raise ValueError("transport policy values must be positive")
        if len(self.backoff_seconds) < self.max_attempts:
            raise ValueError("backoff_seconds must cover every attempt")


@dataclass(frozen=True)
class PageRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None
    cursor: str | None = None

    @property
    def request_sha256(self) -> str:
        material = {
            "method": self.method.upper(),
            "url": _redact_url(self.url),
            "headers": _safe_headers(self.headers),
            "body_sha256": None if self.body is None else hashlib.sha256(self.body).hexdigest(),
            "cursor": self.cursor,
        }
        return sha256_json(material)


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    url: str
    headers: dict[str, str]
    body: bytes
    media_type: str
    retrieved_at: str
    attempts: int

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


class Transport(Protocol):
    def send(self, request: PageRequest) -> TransportResponse: ...


class TransportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class UrllibTransport:
    def __init__(self, policy: TransportPolicy | None = None) -> None:
        self.policy = policy or TransportPolicy()
        self.policy.validate()

    def send(self, request: PageRequest) -> TransportResponse:
        last_error: BaseException | None = None
        for attempt in range(1, self.policy.max_attempts + 1):
            delay = self.policy.backoff_seconds[attempt - 1]
            if delay:
                time.sleep(delay)
            headers = {"User-Agent": self.policy.user_agent, "Accept": "application/json", **request.headers}
            urllib_request = urllib.request.Request(
                request.url,
                data=request.body,
                headers=headers,
                method=request.method.upper(),
            )
            try:
                with urllib.request.urlopen(urllib_request, timeout=self.policy.timeout_seconds) as response:
                    body = response.read(self.policy.max_response_bytes + 1)
                    if len(body) > self.policy.max_response_bytes:
                        raise TransportError("response exceeded max_response_bytes")
                    response_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
                    media_type = response_headers.get("content-type", "application/octet-stream").split(";", 1)[0]
                    return TransportResponse(
                        status_code=int(response.status),
                        url=_redact_url(response.geturl()),
                        headers=_safe_headers(response_headers),
                        body=body,
                        media_type=media_type,
                        retrieved_at=_now(),
                        attempts=attempt,
                    )
            except urllib.error.HTTPError as error:
                last_error = error
                retryable = error.code == 429 or 500 <= error.code < 600
                if retryable and attempt < self.policy.max_attempts:
                    continue
                raise TransportError(
                    f"HTTP {error.code} for {_redact_url(request.url)}",
                    status_code=error.code,
                    retryable=retryable,
                ) from error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt < self.policy.max_attempts:
                    continue
                raise TransportError(
                    f"transport failed for {_redact_url(request.url)}: {error}",
                    retryable=True,
                ) from error
        raise TransportError(f"transport failed: {last_error}", retryable=True)


class SourceOperation(Protocol):
    source: str
    operation: str

    def first_request(self, request: QueryRequest) -> PageRequest: ...
    def next_request(
        self,
        request: QueryRequest,
        page_request: PageRequest,
        payload: Any,
        page_index: int,
    ) -> PageRequest | None: ...
    def normalize(self, payload: Any) -> list[dict[str, Any]]: ...
    def source_release(self, payload: Any, headers: Mapping[str, str]) -> str | None: ...


@dataclass(frozen=True)
class PageReceiptV3:
    page_index: int
    request_sha256: str
    method: str
    request_url: str
    request_body_sha256: str | None
    cursor_in: str | None
    cursor_out: str | None
    status_code: int
    response_sha256: str
    response_bytes: int
    media_type: str
    etag: str | None
    last_modified: str | None
    rate_limit_limit: str | None
    rate_limit_remaining: str | None
    rate_limit_reset: str | None
    retrieved_at: str
    attempts: int
    normalized_record_count: int
    snapshot_body_path: str | None
    snapshot_metadata_path: str | None


@dataclass(frozen=True)
class QueryReceiptV3:
    schema_version: int
    query_id: str
    canonical_request_sha256: str
    source: str
    operation: str
    source_contract_version: str
    source_release: str | None
    status: str
    completeness: str
    requested_max_pages: int
    fetched_pages: int
    records_returned: int
    returned_record_ids: tuple[str, ...]
    normalized_records_sha256: str
    missingness: str
    warnings: tuple[str, ...]
    pages: tuple[PageReceiptV3, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryResultV3:
    request: QueryRequest
    records: tuple[dict[str, Any], ...]
    receipt: QueryReceiptV3

    def to_dict(self) -> dict[str, Any]:
        return {"records": [dict(item) for item in self.records], "receipt": self.receipt.to_dict()}


def _snapshot_page(
    snapshot_dir: Path | None,
    *,
    query_id: str,
    page_index: int,
    page_request: PageRequest,
    response: TransportResponse,
) -> tuple[str | None, str | None]:
    if snapshot_dir is None:
        return None, None
    query_dir = snapshot_dir / query_id
    query_dir.mkdir(parents=True, exist_ok=True)
    body_name = f"page-{page_index:04d}.body"
    meta_name = f"page-{page_index:04d}.json"
    body_path = query_dir / body_name
    meta_path = query_dir / meta_name
    body_path.write_bytes(response.body)
    metadata = {
        "schema_version": 1,
        "request": {
            "method": page_request.method,
            "url": _redact_url(page_request.url),
            "headers": _safe_headers(page_request.headers),
            "body_sha256": None if page_request.body is None else hashlib.sha256(page_request.body).hexdigest(),
            "cursor": page_request.cursor,
            "request_sha256": page_request.request_sha256,
        },
        "response": {
            "status_code": response.status_code,
            "url": response.url,
            "headers": response.headers,
            "body_sha256": response.body_sha256,
            "body_bytes": len(response.body),
            "media_type": response.media_type,
            "retrieved_at": response.retrieved_at,
            "attempts": response.attempts,
            "body_path": body_name,
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return (body_path.relative_to(snapshot_dir).as_posix(), meta_path.relative_to(snapshot_dir).as_posix())


def _status_from_error(error: TransportError) -> str:
    if error.status_code in {401, 403}:
        return "authentication-required"
    if error.status_code == 429:
        return "partial-rate-limit"
    return "source-unavailable"


def execute_paginated(
    operation: SourceOperation,
    request: QueryRequest,
    *,
    transport: Transport | None = None,
    snapshot_dir: Path | None = None,
) -> QueryResultV3:
    request.validate()
    if request.source != operation.source or request.operation != operation.operation:
        raise ValueError(
            f"operation mismatch: request={request.source}.{request.operation}, "
            f"handler={operation.source}.{operation.operation}"
        )
    transport = transport or UrllibTransport()
    page_request = operation.first_request(request)
    records: list[dict[str, Any]] = []
    receipts: list[PageReceiptV3] = []
    warnings: list[str] = []
    source_release: str | None = None
    next_exists = False
    terminal_status = "complete"

    for page_index in range(request.max_pages):
        try:
            response = transport.send(page_request)
        except TransportError as error:
            terminal_status = _status_from_error(error)
            warnings.append(str(error))
            break
        try:
            payload = response.json()
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"schema-drift: source returned invalid JSON on page {page_index}") from error
        try:
            page_records = operation.normalize(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"normalization-failed on page {page_index}: {error}") from error
        if not isinstance(page_records, list) or not all(isinstance(item, dict) for item in page_records):
            raise ValueError("normalization-failed: operation must return record objects")
        next_request = operation.next_request(request, page_request, payload, page_index)
        next_exists = next_request is not None
        source_release = source_release or operation.source_release(payload, response.headers)
        body_path, metadata_path = _snapshot_page(
            snapshot_dir,
            query_id=request.query_id,
            page_index=page_index,
            page_request=page_request,
            response=response,
        )
        receipts.append(
            PageReceiptV3(
                page_index=page_index,
                request_sha256=page_request.request_sha256,
                method=page_request.method.upper(),
                request_url=_redact_url(page_request.url),
                request_body_sha256=None if page_request.body is None else hashlib.sha256(page_request.body).hexdigest(),
                cursor_in=page_request.cursor,
                cursor_out=None if next_request is None else next_request.cursor,
                status_code=response.status_code,
                response_sha256=response.body_sha256,
                response_bytes=len(response.body),
                media_type=response.media_type,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                rate_limit_limit=response.headers.get("x-ratelimit-limit"),
                rate_limit_remaining=response.headers.get("x-ratelimit-remaining"),
                rate_limit_reset=response.headers.get("x-ratelimit-reset"),
                retrieved_at=response.retrieved_at,
                attempts=response.attempts,
                normalized_record_count=len(page_records),
                snapshot_body_path=body_path,
                snapshot_metadata_path=metadata_path,
            )
        )
        records.extend(dict(item) for item in page_records)
        if next_request is None:
            next_exists = False
            break
        page_request = next_request

    if terminal_status == "complete":
        if next_exists and len(receipts) >= request.max_pages:
            terminal_status = "bounded-by-user"
        elif not records:
            terminal_status = "negative"
    completeness = terminal_status
    missingness = "negative" if not records and terminal_status in {"complete", "negative"} else (
        "unavailable" if terminal_status in {"source-unavailable", "authentication-required"} else
        "partial" if terminal_status.startswith("partial") or terminal_status == "bounded-by-user" else
        "observed"
    )
    record_ids = tuple(str(item.get("id") or f"record-{index}") for index, item in enumerate(records))
    receipt = QueryReceiptV3(
        schema_version=3,
        query_id=request.query_id,
        canonical_request_sha256=request.request_sha256,
        source=request.source,
        operation=request.operation,
        source_contract_version="3",
        source_release=source_release,
        status=terminal_status,
        completeness=completeness,
        requested_max_pages=request.max_pages,
        fetched_pages=len(receipts),
        records_returned=len(records),
        returned_record_ids=record_ids,
        normalized_records_sha256=sha256_json(records),
        missingness=missingness,
        warnings=tuple(warnings),
        pages=tuple(receipts),
    )
    return QueryResultV3(request, tuple(records), receipt)


def replay_snapshot_directory(snapshot_dir: Path, query_id: str) -> list[dict[str, Any]]:
    query_dir = snapshot_dir / query_id
    if not query_dir.is_dir():
        raise ValueError(f"snapshot query directory not found: {query_id}")
    pages: list[dict[str, Any]] = []
    for metadata_path in sorted(query_dir.glob("page-*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        body_path = query_dir / metadata["response"]["body_path"]
        body = body_path.read_bytes()
        if hashlib.sha256(body).hexdigest() != metadata["response"]["body_sha256"]:
            raise ValueError(f"snapshot body digest mismatch: {body_path.name}")
        pages.append({"metadata": metadata, "payload": json.loads(body.decode("utf-8"))})
    if not pages:
        raise ValueError(f"no snapshot pages found for query: {query_id}")
    return pages
