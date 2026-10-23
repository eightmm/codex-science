"""Run-directory wrapper for the Connector Contract v3 literature sources (single writer per run directory)."""
from __future__ import annotations

import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codex_science.connector_contract import QueryRequest
from codex_science.evidence import _validate_query_records
from codex_science.source_operations_v3 import SOURCE_OPERATIONS_V3
from codex_science.transport_v3 import TransportError, execute_paginated

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_DISPLAY = {"europepmc": "EuropePMC", "pubmed": "PubMed"}


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
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid query ledger JSON at line {index}") from error
        if not isinstance(row, dict):
            raise ValueError(f"query ledger line {index} must be a JSON object")
        if isinstance(row.get("query_id"), str):
            ids.add(row["query_id"])
    return ids


def _plain_abstract(value: str) -> bytes:
    return (" ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split()) + "\n").encode("utf-8")


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
    if abstracts and source == "pubmed":
        print("PubMed returns IDs only; use europepmc --abstracts for titles and abstract sources.", file=sys.stderr)
        abstracts = False
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
            raise FileExistsError(
                f"query already exists in queries.jsonl: {query_id}; changing --page-size, --max-pages, "
                "or --evidence-cutoff yields a new query id"
            )
        dest = snapshots / query_id
        if dest.exists() or dest.is_symlink():
            raise FileExistsError(f"snapshot already exists for query: {query_id}")
        stage_root = Path(tempfile.mkdtemp(prefix=".literature-", dir=root))
        stage_query = stage_root / query_id
        try:
            result = execute_paginated(
                SOURCE_OPERATIONS_V3[source], request, transport=transport,
                snapshot_dir=stage_root,
            )
            if result.receipt.warnings:
                raise TransportError("literature transport failed: " + "; ".join(result.receipt.warnings))
            result_obj = result.to_dict()
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
            abstract_files: set[str] = set()
            pending_abstracts: list[tuple[Path, str, bytes]] = []
            if abstracts:
                for payload in pages:
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
                        if target.exists():
                            if target.read_bytes() != data:
                                raise FileExistsError(f"refusing to overwrite differing abstract: {filename}")
                        else:
                            pending_abstracts.append((target, filename, data))
                        abstract_files.add(filename)
            for target, filename, data in pending_abstracts:
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
            for index, normalized in enumerate(result.records):
                raw = next((r for r in rows if str(r.get("id", "")) == str(normalized.get("id", ""))), {})
                title = str(raw.get("title") or normalized.get("title") or "")
                year = raw.get("firstPublicationDate") or raw.get("pubYear") or normalized.get("publication_date") or ""
                summary_rows.append({"id": normalized.get("id", ""), "year": str(year)[:4], "title": title[:120], "abstract_written": f"{normalized.get('id')}.abstract.txt" in abstract_files})
            return {"query_id": query_id, "status": record["status"], "hit_count": hit_count,
                    "records_returned": len(result.records), "records": summary_rows[:page_size * max_pages],
                    "abstracts_supported": source == "europepmc"}
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
    finally:
        os.close(root_fd)
