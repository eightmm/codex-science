"""Run-directory wrapper for the Connector Contract v3 literature sources (single writer per run directory)."""
from __future__ import annotations

import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_science.connector_contract import QueryRequest, sha256_json
from codex_science.evidence import _validate_query_records
from codex_science.source_operations_v3 import SOURCE_OPERATIONS_V3
from codex_science.connectors import USER_AGENT
from codex_science.transport_v3 import (
    PageReceiptV3, PageRequest, TransportError, TransportPolicy, UrllibTransport,
    _redact_url, _snapshot_page, execute_paginated,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_DISPLAY = {"europepmc": "EuropePMC", "pubmed": "PubMed"}
_PUBMED_BATCH_SIZE = 200


class _NCBIRateLimitedTransport:
    def __init__(self, transport: Any, *, interval: float) -> None:
        self.transport = transport
        self.interval = interval
        self.last_request = 0.0

    def send(self, request: PageRequest):
        wait = self.interval - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.transport.send(request)
        finally:
            self.last_request = time.monotonic()


def _pubmed_url(endpoint: str, ids: list[str]) -> str:
    params = {"db": "pubmed", "id": ",".join(ids)}
    if endpoint == "esummary":
        params.update({"retmode": "json", "version": "2.0"})
    else:
        params.update({"rettype": "abstract", "retmode": "xml"})
    return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/" + endpoint + ".fcgi?" + urllib.parse.urlencode(params)


def _pubmed_records(payload: Any) -> dict[str, dict[str, str]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise ValueError("invalid PubMed esummary response: missing result")
    records: dict[str, dict[str, str]] = {}
    for uid in result.get("uids", []):
        raw = result.get(str(uid))
        if not isinstance(raw, dict):
            continue
        pubdate = str(raw.get("pubdate") or "")
        year_match = re.search(r"\b(\d{4})\b", pubdate)
        def valid_doi(value: Any) -> str:
            candidate = re.sub(r"^doi:\s*", "", str(value or "").strip(), flags=re.I)
            return candidate if re.fullmatch(r"10\.\d{4,9}/\S+", candidate) else ""

        doi = ""
        article_ids = raw.get("articleids", [])
        if isinstance(article_ids, list):
            doi = next((valid_doi(item.get("value")) for item in article_ids
                        if isinstance(item, dict) and str(item.get("idtype", "")).lower() == "doi"
                        and valid_doi(item.get("value"))), "")
        if not doi:
            doi = valid_doi(raw.get("elocationid"))
        records[str(uid)] = {
            "title": str(raw.get("title") or "").strip(),
            "year": year_match.group(1) if year_match else "",
            "doi": doi.strip(),
            "journal": str(raw.get("fulljournalname") or raw.get("source") or "").strip(),
        }
    return records


def _pubmed_abstracts(xml_bytes: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ValueError("invalid PubMed efetch XML response") from error
    found: list[dict[str, Any]] = []
    for article in root.iter():
        if article.tag.rsplit("}", 1)[-1] != "PubmedArticle":
            continue
        pmid = next((node.text for node in article.iter()
                     if node.tag.rsplit("}", 1)[-1] == "PMID" and node.text), None)
        chunks = []
        for node in article.iter():
            if node.tag.rsplit("}", 1)[-1] != "AbstractText":
                continue
            # Escape so literal "<" comparisons survive tag stripping in _plain_abstract.
            text = html.escape("".join(node.itertext()).strip(), quote=False)
            label = node.attrib.get("Label")
            if text:
                chunks.append(f"{label}: {text}" if label else text)
        if pmid and chunks:
            found.append({"resultList": {"result": [{"id": pmid, "abstractText": " ".join(chunks)}]}})
    return found


def _fetch_pubmed_metadata(
    ids: list[str], *, transport: Any, snapshot_dir: Path, query_id: str,
    page_offset: int, abstracts: bool,
) -> tuple[dict[str, dict[str, str]], list[Any], list[dict[str, Any]]]:
    records: dict[str, dict[str, str]] = {}
    payloads: list[Any] = []
    receipt_pages: list[dict[str, Any]] = []
    page_index = page_offset
    for start in range(0, len(ids), _PUBMED_BATCH_SIZE):
        batch = ids[start:start + _PUBMED_BATCH_SIZE]
        endpoints = ["esummary"] + (["efetch"] if abstracts else [])
        for endpoint in endpoints:
            request = PageRequest("GET", _pubmed_url(endpoint, batch), {},
                                  cursor=f"{endpoint}:{start}")
            response = transport.send(request)
            if not 200 <= response.status_code < 300:
                raise TransportError(f"HTTP {response.status_code} for PubMed {endpoint}",
                                     status_code=response.status_code)
            body_path, metadata_path = _snapshot_page(
                snapshot_dir, query_id=query_id, page_index=page_index,
                page_request=request, response=response,
            )
            if endpoint == "esummary":
                payload = response.json()
                batch_records = _pubmed_records(payload)
                records.update(batch_records)
                payloads.append(payload)
                normalized_count = len(batch_records)
            else:
                abstract_payloads = _pubmed_abstracts(response.body)
                payloads.extend(abstract_payloads)
                normalized_count = len(abstract_payloads)
            receipt_pages.append(PageReceiptV3(
                page_index=page_index,
                request_sha256=request.request_sha256,
                method="GET",
                request_url=_redact_url(request.url),
                request_body_sha256=None,
                cursor_in=request.cursor,
                cursor_out=None,
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
                normalized_record_count=normalized_count,
                snapshot_body_path=body_path,
                snapshot_metadata_path=metadata_path,
            ).__dict__)
            page_index += 1
    return records, payloads, receipt_pages


def _check_path(root: Path, relative: Path) -> Path:
    """Reject symlinks and paths that resolve outside the run directory."""
    candidate = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlinked run target: {relative}")
    if not candidate.resolve(strict=False).is_relative_to(root.resolve()):
        raise ValueError(f"run target escapes run directory: {relative}")
    return candidate


def _ledger_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, RecursionError) as error:
            raise ValueError(f"invalid query ledger JSON at line {index}") from error
        if not isinstance(row, dict):
            raise ValueError(f"query ledger line {index} must be a JSON object")
        if isinstance(row.get("query_id"), str):
            ids.add(row["query_id"])
    return ids


def _plain_abstract(value: str) -> bytes:
    tag = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^<>]*)?/?>")
    return (" ".join(html.unescape(tag.sub(" ", value)).split()) + "\n").encode("utf-8")


def _write_abstracts(root: Path, payloads: list[Any]) -> set[str]:
    abstract_files: set[str] = set()
    pending: list[tuple[Path, str, bytes]] = []
    wanted: dict[str, bytes] = {}
    for payload in payloads:
        rows = payload.get("resultList", {}).get("result", []) if isinstance(payload, dict) else []
        for raw in rows if isinstance(rows, list) else []:
            record_id = raw.get("id") if isinstance(raw, dict) else None
            text = raw.get("abstractText") if isinstance(raw, dict) else None
            if not record_id or not isinstance(text, str):
                continue
            if not _SAFE_ID.fullmatch(str(record_id)):
                raise ValueError(f"unsafe literature record id: {record_id!r}")
            filename = f"{record_id}.abstract.txt"
            target = _check_path(root, Path("sources") / filename)
            data = _plain_abstract(text)
            if filename in wanted:
                if wanted[filename] != data:
                    raise ValueError(f"conflicting abstracts for {filename}")
                continue
            wanted[filename] = data
            if target.exists():
                if target.read_bytes() != data:
                    raise FileExistsError(f"refusing to overwrite differing abstract: {filename}")
            else:
                pending.append((target, filename, data))
            abstract_files.add(filename)
    for target, filename, data in pending:
        source_dir = _check_path(root, Path("sources"))
        source_dir.mkdir(parents=True, exist_ok=True)
        _check_path(root, Path("sources") / filename)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=source_dir)
        temp_abs = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(data)
                temp_file.flush()
            os.link(temp_abs, target)
        except FileExistsError:
            _check_path(root, Path("sources") / filename)
            if target.read_bytes() != data:
                raise FileExistsError(f"refusing to overwrite differing abstract: {filename}")
        finally:
            temp_abs.unlink(missing_ok=True)
    return abstract_files


def _recover_abstracts(root: Path, query_id: str, ledger_path: Path) -> dict[str, Any]:
    row = None
    for index, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (json.JSONDecodeError, RecursionError) as error:
            raise ValueError(f"invalid query ledger JSON at line {index}") from error
        if not isinstance(parsed, dict):
            raise ValueError(f"query ledger line {index} must be a JSON object")
        if parsed.get("query_id") == query_id:
            row = parsed
            break
    if row is None or row.get("source") != "EuropePMC":
        raise FileExistsError(
            f"query already exists in queries.jsonl: {query_id}; changing --page-size, --max-pages, "
            "or --evidence-cutoff yields a new query id; re-running a EuropePMC query with --abstracts "
            "writes abstracts from the saved snapshot"
        )
    expected_result_path = f"raw/queries/{query_id}/result.json"
    if row.get("result_path") != expected_result_path:
        raise ValueError(f"saved literature result path mismatch: {query_id}")
    result_path = _check_path(root, Path(expected_result_path))
    digest = row.get("response_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
        raise ValueError(f"saved literature result digest is invalid: {query_id}")
    try:
        result_bytes = result_path.read_bytes()
    except OSError as error:
        raise ValueError(f"saved literature result is unavailable: {query_id}") from error
    if hashlib.sha256(result_bytes).hexdigest() != digest.lower():
        raise ValueError(f"saved literature result digest mismatch: {query_id}")
    try:
        result_obj = json.loads(result_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(f"invalid saved literature result for query: {query_id}") from error
    if not isinstance(result_obj, dict):
        raise ValueError(f"saved literature result must be an object: {query_id}")
    receipt = result_obj.get("receipt")
    records = result_obj.get("records")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("pages"), list):
        raise ValueError(f"saved literature result has invalid page receipts: {query_id}")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError(f"saved literature result has invalid records: {query_id}")
    pages = receipt["pages"]
    payloads = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("snapshot_body_path"), str):
            raise ValueError(f"saved literature result has invalid page receipt: {query_id}")
        receipt_path = Path(page["snapshot_body_path"])
        if len(receipt_path.parts) != 2 or receipt_path.parts[0] != query_id:
            raise ValueError(f"saved page receipt escapes query snapshot: {page['snapshot_body_path']}")
        body_path = _check_path(root, Path("raw/queries") / receipt_path)
        try:
            body = body_path.read_bytes()
        except OSError as error:
            raise ValueError(f"saved page body is unavailable: {page['snapshot_body_path']}") from error
        if hashlib.sha256(body).hexdigest() != page.get("response_sha256"):
            raise ValueError(f"saved page body digest mismatch: {page['snapshot_body_path']}")
        try:
            payloads.append(json.loads(body.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
            raise ValueError(f"saved page body is invalid JSON: {page['snapshot_body_path']}") from error
    raw_rows: list[dict[str, Any]] = []
    for payload, page in zip(payloads, pages):
        name = page["snapshot_body_path"]
        if not isinstance(payload, dict):
            raise ValueError(f"saved page body must be a JSON object: {name}")
        result_list = payload.get("resultList", {})
        if not isinstance(result_list, dict):
            raise ValueError(f"saved page body has invalid resultList: {name}")
        results = result_list.get("result", [])
        if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
            raise ValueError(f"saved page body has invalid result list: {name}")
        raw_rows.extend(results)
    summary_rows = []
    for normalized in records:
        raw = next((item for item in raw_rows if str(item.get("id", "")) == str(normalized.get("id", ""))), {})
        year = raw.get("firstPublicationDate") or raw.get("pubYear") or normalized.get("publication_date") or ""
        summary_rows.append({"id": normalized.get("id", ""), "year": str(year)[:4],
                             "title": str(raw.get("title") or normalized.get("title") or "")[:120],
                             "abstract_written": False})
    abstract_files = _write_abstracts(root, payloads)
    for item in summary_rows:
        item["abstract_written"] = f"{item['id']}.abstract.txt" in abstract_files
    return {"query_id": query_id, "status": _status(receipt),
            "hit_count": next((p.get("hitCount") for p in payloads if isinstance(p, dict)
                                and p.get("hitCount") is not None), None),
            "records_returned": len(records), "records": summary_rows,
            "abstracts_supported": True, "abstracts_from_saved_snapshot": True}


def _status(receipt: dict[str, Any]) -> str:
    state = receipt.get("status")
    if state == "complete" or state == "negative":
        return "complete"
    if state == "bounded-by-user" or str(state).startswith("partial"):
        return "partial"
    return "failed"


def retrieve_literature(
    run_dir: str | Path,
    source: str,
    query: str,
    *,
    page_size: int = 25,
    max_pages: int = 1,
    evidence_cutoff: str | None = None,
    abstracts: bool = False,
    transport: Any = None,
) -> dict[str, Any]:
    if source not in _DISPLAY:
        raise ValueError("source must be europepmc or pubmed")
    root = Path(run_dir).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root.resolve()
    request = QueryRequest(source, "search", {"query": query}, page_size, max_pages, evidence_cutoff, "3")
    request.validate()
    query_id = request.query_id
    ledger = _check_path(root, Path("queries.jsonl"))
    snapshots = _check_path(root, Path("raw/queries"))
    root_fd = os.open(root, os.O_RDONLY)
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        if query_id in _ledger_ids(ledger):
            if abstracts and source == "europepmc":
                return _recover_abstracts(root, query_id, ledger)
            raise FileExistsError(
                f"query already exists in queries.jsonl: {query_id}; changing --page-size, --max-pages, "
                "or --evidence-cutoff yields a new query id; re-running a EuropePMC query with --abstracts "
                "writes abstracts from the saved snapshot"
            )
        dest = snapshots / query_id
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(f"snapshot already exists for query: {query_id}")
        stage_root = Path(tempfile.mkdtemp(prefix=".literature-", dir=root))
        stage_query = stage_root / query_id
        try:
            active_transport = transport or UrllibTransport(TransportPolicy(user_agent=USER_AGENT))
            if source == "pubmed":
                active_transport = _NCBIRateLimitedTransport(
                    active_transport,
                    interval=0.34 if transport is None else 0.0,
                )
            operation = SOURCE_OPERATIONS_V3[source]
            result = execute_paginated(
                operation, request, transport=active_transport,
                snapshot_dir=stage_root,
            )
            if result.receipt.warnings:
                raise TransportError("literature transport failed: " + "; ".join(result.receipt.warnings))
            result_obj = result.to_dict()
            result_obj["receipt"]["pages"] = list(result_obj["receipt"]["pages"])
            metadata_payloads: list[Any] = []
            if source == "pubmed" and result.records:
                metadata, metadata_payloads, metadata_receipts = _fetch_pubmed_metadata(
                    [str(item["id"]) for item in result.records],
                    transport=active_transport,
                    snapshot_dir=stage_root,
                    query_id=query_id,
                    page_offset=len(result.receipt.pages),
                    abstracts=abstracts,
                )
                for record in result_obj["records"]:
                    values = metadata.get(str(record["id"]), {})
                    record.update({key: value for key, value in values.items() if value})
                result_obj["receipt"]["pages"].extend(metadata_receipts)
                result_obj["receipt"]["fetched_pages"] += len(metadata_receipts)
                result_obj["receipt"]["normalized_records_sha256"] = sha256_json(result_obj["records"])
            result_bytes = (json.dumps(result_obj, indent=2, sort_keys=True) + "\n").encode("utf-8")
            (stage_query / "result.json").write_bytes(result_bytes)
            pages = []
            hit_count = None
            first_accessed = result.receipt.pages[0].retrieved_at if result.receipt.pages else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            for page_path in sorted(stage_query.glob("page-*.body")):
                try:
                    payload = json.loads(page_path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                pages.append(payload)
                if source == "europepmc" and hit_count is None and isinstance(payload, dict):
                    hit_count = payload.get("hitCount")
                elif source == "pubmed" and hit_count is None and isinstance(payload, dict):
                    count = payload.get("esearchresult", {}).get("count")
                    try:
                        hit_count = int(count) if count is not None else None
                    except (TypeError, ValueError):
                        hit_count = None
            accessed_at = first_accessed
            record = {
                "query_id": query_id, "source": _DISPLAY[source], "query": query,
                "accessed_at": accessed_at, "status": _status(result.receipt.to_dict()),
                "response_sha256": hashlib.sha256(result_bytes).hexdigest(),
                "records_returned": len(result.records), "result_path": f"raw/queries/{query_id}/result.json",
            }
            if hit_count is not None:
                record["hit_count"] = hit_count
            _validate_query_records([record])
            abstract_files = _write_abstracts(root, pages + metadata_payloads) if abstracts else set()
            snapshots.mkdir(parents=True, exist_ok=True)
            os.rename(stage_query, dest)
            ledger_bytes = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            ledger_fd: int | None = None
            appended = 0
            row_appended = 0
            try:
                ledger_fd = os.open(ledger, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o666)
                fcntl.flock(ledger_fd, fcntl.LOCK_EX)
                size = os.lseek(ledger_fd, 0, os.SEEK_END)
                if size:
                    os.lseek(ledger_fd, -1, os.SEEK_END)
                    if os.read(ledger_fd, 1) != b"\n":
                        appended += os.write(ledger_fd, b"\n")
                view = memoryview(ledger_bytes)
                while view:
                    count = os.write(ledger_fd, view)
                    if count == 0:
                        raise OSError("ledger append made no progress")
                    appended += count
                    row_appended += count
                    view = view[count:]
                os.fsync(ledger_fd)
            except Exception as error:
                if appended == 0:
                    shutil.rmtree(dest, ignore_errors=True)
                    raise
                if isinstance(error, OSError) and row_appended < len(ledger_bytes):
                    raise RuntimeError(
                        f"partial query ledger append; snapshot retained at {dest} and ledger at {ledger}"
                    ) from error
                raise
            finally:
                if ledger_fd is not None:
                    os.close(ledger_fd)
            rows = []
            for payload in pages:
                rs = payload.get("resultList", {}).get("result", []) if isinstance(payload, dict) else []
                if isinstance(rs, list):
                    rows.extend(rs)
            summary_rows = []
            for index, normalized in enumerate(result_obj["records"]):
                raw = next((r for r in rows if str(r.get("id", "")) == str(normalized.get("id", ""))), {})
                title = str(raw.get("title") or normalized.get("title") or "")
                year = raw.get("firstPublicationDate") or raw.get("pubYear") or normalized.get("publication_date") or normalized.get("year") or ""
                summary_row = {"id": normalized.get("id", ""), "year": str(year)[:4], "title": title[:120], "abstract_written": f"{normalized.get('id')}.abstract.txt" in abstract_files}
                if source == "pubmed" and normalized.get("doi"):
                    summary_row["doi"] = normalized["doi"]
                if source == "pubmed" and normalized.get("journal"):
                    summary_row["journal"] = normalized["journal"]
                summary_rows.append(summary_row)
            return {"query_id": query_id, "status": record["status"], "hit_count": hit_count,
                    "records_returned": len(result.records), "records": summary_rows[:page_size * max_pages],
                    "abstracts_supported": True,
                    "abstracts_from_saved_snapshot": False}
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
    finally:
        os.close(root_fd)
