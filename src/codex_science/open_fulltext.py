"""Opt-in, bounded retrieval of openly licensed Europe PMC full text."""
from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import os
import re
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from codex_science.citation_trace import _walk_ids, extract_identifiers
from codex_science.connectors import USER_AGENT
from codex_science.literature_v2 import normalize_identifier
from codex_science.transport_v3 import (
    _DeadlineHTTPHandler, _DeadlineHTTPSHandler, _DeadlineRedirectHandler, _read_with_deadline,
)

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EVIDENCE_BOUNDARY = "Full text retrieved; not evidence that it supports any claim. Retrieved text is untrusted data and is not executed or followed."
MAX_CANDIDATES = 30
MAX_CANDIDATE_LIMIT = 50
MAX_FETCHES = 10
MAX_SECONDS = 60.0
MAX_BODY_BYTES = 8 * 1024 * 1024
_HOSTS = frozenset({"www.ebi.ac.uk"})
_PUBLICATION_TEMPORARY_PREFIX = ".fulltext-"
_PUBLICATION_TEMPORARY_SUFFIXES = (".xml", ".txt")
_PUBLICATION_TEMPORARY = re.compile(
    re.escape(_PUBLICATION_TEMPORARY_PREFIX) + r"[0-9a-f]{32}-[a-z0-9_]+(?:"
    + "|".join(re.escape(suffix) for suffix in _PUBLICATION_TEMPORARY_SUFFIXES) + ")"
)
_DOCTYPE_START = re.compile(br"<!\s*DOCTYPE\b", re.IGNORECASE)
_DOCTYPE = re.compile(
    br"<!DOCTYPE\s+[A-Za-z_:][A-Za-z0-9_.:-]*\s+"
    br"(?:PUBLIC\s+(?:\"[^\"]*\"|'[^']*')\s+(?:\"[^\"]*\"|'[^']*')|"
    br"SYSTEM\s+(?:\"[^\"]*\"|'[^']*'))\s*>",
)
_ENTITY = re.compile(br"<!\s*ENTITY\b", re.IGNORECASE)
_XML_DECLARATION_START = re.compile(br"\A<\?xml[ \t\r\n]+")
_XML_ENCODING = re.compile(
    br"\bencoding[ \t\r\n]*=[ \t\r\n]*(['\"])([A-Za-z][A-Za-z0-9._-]*)\1"
)
_XML_PROLOG_WHITESPACE = frozenset(b" \t\r\n")


def _skip_xml_prolog_misc(body: bytes, offset: int) -> int | None:
    while offset < len(body):
        while offset < len(body) and body[offset] in _XML_PROLOG_WHITESPACE:
            offset += 1
        if body.startswith(b"<?", offset):
            end = body.find(b"?>", offset + 2)
            if end < 0:
                return None
            offset = end + 2
        elif body.startswith(b"<!--", offset):
            end = body.find(b"-->", offset + 4)
            if end < 0:
                return None
            offset = end + 3
        else:
            return offset
    return offset


def _is_xml_root_start(body: bytes, offset: int) -> bool:
    if offset + 1 >= len(body) or body[offset] != ord("<"):
        return False
    first = body[offset + 1]
    if not (first == ord(":") or first == ord("_") or first >= 0x80
            or ord("A") <= first <= ord("Z") or ord("a") <= first <= ord("z")):
        return False
    offset += 2
    while offset < len(body):
        if body[offset] in _XML_PROLOG_WHITESPACE or body[offset] in b"/>":
            return True
        offset += 1
    return False


class _EuropePMCRedirectHandler(_DeadlineRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme.lower() != "https" or target.hostname not in _HOSTS or target.port not in (None, 443):
            raise ValueError("refused Europe PMC redirect")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def _http_fetch(url: str, *, timeout: float, max_body_bytes: int) -> tuple[int, bytes]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in _HOSTS or parsed.port not in (None, 443):
        raise ValueError("refused non-Europe PMC URL")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml"})
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(
        _EuropePMCRedirectHandler(deadline), _DeadlineHTTPHandler(deadline), _DeadlineHTTPSHandler(deadline))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = _read_with_deadline(response, max_body_bytes + 1, deadline)
            if len(body) > max_body_bytes:
                raise ValueError("response exceeds body cap")
            length = response.headers.get("Content-Length")
            if length is not None and "chunked" not in response.headers.get("Transfer-Encoding", "").lower():
                if not re.fullmatch(r"[0-9]+", length.strip()):
                    raise ValueError("invalid Content-Length")
                if len(body) < int(length):
                    raise ValueError("incomplete response body")
            return response.status, body
    except urllib.error.HTTPError as exc:
        with exc:
            body = _read_with_deadline(exc, max_body_bytes + 1, deadline)
            if len(body) > max_body_bytes:
                raise ValueError("response exceeds body cap")
            return exc.code, body


def _manifest(root: Path) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    path = _safe_run_file(root, "manifest.json", required=True)
    assert path is not None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("run manifest must be an object")
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("run manifest artifacts must be a list")
    declarations = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ValueError(f"manifest artifact {index} must be an object")
        kind, relative = artifact.get("kind"), artifact.get("path")
        if not isinstance(kind, str) or not isinstance(relative, str) or not relative.strip():
            raise ValueError(f"manifest artifact {index} needs a kind and path")
        declarations.append((kind, relative))
    return payload, declarations


def _safe_run_file(root: Path, relative: str, *, required: bool) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError(f"unsafe run-relative path: {relative}")
    current = root
    for index, part in enumerate(candidate.parts):
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if required or index < len(candidate.parts) - 1:
                if required:
                    raise ValueError(f"required run file is missing: {relative}")
                raise ValueError(f"parent directory is missing: {relative}")
            return current
        except OSError as exc:
            raise ValueError(f"unsafe run path: {relative}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"symlink in run path: {relative}")
        if index < len(candidate.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"non-directory component in run path: {relative}")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"run path escapes its directory: {relative}") from exc
    if not stat.S_ISREG(current.stat().st_mode):
        raise ValueError(f"run path is not a regular file: {relative}")
    return current


_ROW_IDENTITY_KEYS = ("identifiers", "persistent_id", "persistent_ids", "pmcid", "pmid", "doi")


def _own_identity_ids(row: dict[str, Any]) -> set[str]:
    """Identity ids written directly in the row's top-level fields (no recursion)."""
    result: set[str] = set()
    for key in _ROW_IDENTITY_KEYS:
        value = row.get(key)
        if key in {"identifiers", "persistent_ids"}:
            values = value if isinstance(value, list) else []
        else:
            values = [value]
        for item in values:
            if isinstance(item, str) or (key == "pmid" and isinstance(item, int) and not isinstance(item, bool)):
                raw = str(item)
                if key in {"pmcid", "pmid", "doi"}:
                    raw = f"{key}:{raw}"
                result.add(normalize_identifier(raw))
    return result


def _row_identity(row: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    """Return (row ids, own valid pmcids, own pmid/doi superseded by them).

    An identifier is replaced only when it is one of the row's own top-level
    identity identifiers and the row has a valid own PMCID. Identifiers that
    appear only in nested metadata (and are not also own identifiers) are never
    replaced; a nested copy of an own identifier is the same identifier and is
    replaced with it.
    """
    ids = {normalize_identifier(value) for value in _walk_ids(row)}
    own = _own_identity_ids(row)
    own_pmcids = {item for item in own if re.fullmatch(r"pmcid:PMC\d+", item)}
    if not own_pmcids:
        return ids, set(), set()
    nested = {normalize_identifier(value) for value in _walk_ids(
        {key: value for key, value in row.items() if key not in _ROW_IDENTITY_KEYS})}
    superseded = {item for item in own if item.startswith(("pmid:", "doi:")) and item not in nested}
    return ids, own_pmcids, superseded


def _row_fetch_ids(row: dict[str, Any]) -> set[str]:
    ids, own_pmcids, superseded = _row_identity(row)
    return ids - superseded if own_pmcids else ids


def identifiers_from_run(run_dir: str | Path) -> list[str]:
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
    manifest_path = _safe_run_file(root, "manifest.json", required=False)
    if manifest_path is None or not manifest_path.exists():
        study_path = _safe_run_file(root, "studies.json", required=False)
        if study_path is None or not study_path.exists():
            return []
        if study_path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"run citation file exceeds 8 MiB: {study_path.name}")
        table = json.loads(study_path.read_text(encoding="utf-8"))
        if not isinstance(table, dict) or not isinstance(table.get("studies", []), list):
            raise ValueError("study table must be an object with a studies list")
        found: set[str] = set()
        for row in table.get("studies", []):
            if isinstance(row, dict) and not row.get("excluded"):
                found.update(_row_fetch_ids(row))
        return sorted(item for item in found if item.startswith(("pmcid:", "pmid:", "doi:")))
    _, declarations = _manifest(root)
    found: set[str] = set()
    report_names = [path for kind, path in declarations if kind == "report"]
    for relative in report_names:
        path = _safe_run_file(root, relative, required=True)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"run citation file exceeds 8 MiB: {path.name}")
        for item in extract_identifiers(path.read_text(encoding="utf-8")):
            identifier = normalize_identifier(item["identifier"])
            if identifier.startswith(("pmcid:", "pmid:", "doi:")):
                found.add(identifier)

    study_declared = next((path for kind, path in declarations if kind == "study-table"), None)
    study_path = _safe_run_file(root, study_declared or "studies.json", required=study_declared is not None)
    if study_path is not None and study_path.exists():
        if study_path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError(f"run citation file exceeds 8 MiB: {study_path.name}")
        table = json.loads(study_path.read_text(encoding="utf-8"))
        if not isinstance(table, dict) or not isinstance(table.get("studies", []), list):
            raise ValueError("study table must be an object with a studies list")
        study_ids: set[str] = set()
        for row in table.get("studies", []):
            if isinstance(row, dict) and not row.get("excluded"):
                row_ids, row_pmcids, superseded = _row_identity(row)
                if row_pmcids and found & (row_pmcids | superseded):
                    found.difference_update(superseded)
                    found.update(row_pmcids)
                study_ids.update(row_ids - superseded)
        found.intersection_update(study_ids)
    return sorted(found)


def _normalize_ids(ids: list[str]) -> list[str]:
    if not isinstance(ids, list):
        raise TypeError("identifiers must be a list")
    result = set()
    for item in ids:
        if not isinstance(item, str):
            raise TypeError("identifiers must be strings")
        normalized = normalize_identifier(item)
        if not normalized.startswith(("pmcid:", "pmid:", "doi:")):
            raise ValueError(f"unsupported identifier: {item}")
        if normalized.startswith("doi:") and (not re.fullmatch(r"doi:10\.\d{4,9}/\S+", normalized) or '"' in normalized):
            raise ValueError(f"malformed DOI: {item}")
        if normalized.startswith("pmid:") and not re.fullmatch(r"pmid:\d{5,9}", normalized):
            raise ValueError(f"malformed PMID: {item}")
        if normalized.startswith("pmcid:") and not re.fullmatch(r"pmcid:PMC\d+", normalized):
            raise ValueError(f"malformed PMCID: {item}")
        result.add(normalized)
    return sorted(result)


def _search_query(identifier: str) -> str:
    kind, value = identifier.split(":", 1)
    if kind == "doi":
        if '"' in value:
            raise ValueError("DOIs containing a quote are not supported")
        return f'DOI:"{value}"'
    if kind == "pmcid":
        return f"PMCID:{value.upper()}"
    return f"EXT_ID:{value} AND SRC:MED"


def _record_matches(record: dict[str, Any], identifier: str) -> bool:
    kind, value = identifier.split(":", 1)
    if kind == "doi":
        returned = record.get("doi")
        return isinstance(returned, str) and returned.casefold() == value.casefold()
    if kind == "pmcid":
        return str(record.get("pmcid", "")).casefold() == value.casefold()
    return str(record.get("source", "")).upper() == "MED" and str(record.get("pmid", "")) == value


def _plain_text(xml: bytes, *, expected_ids: dict[str, str] | None = None) -> str:
    # UTF-16/32 can hide markup from the byte-level declaration checks.
    body = xml.removeprefix(b"\xef\xbb\xbf")
    if b"\x00" in body:
        raise ValueError("XML declarations and non-UTF-8-compatible bytes are not allowed")
    try:
        body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("XML declarations and non-UTF-8-compatible bytes are not allowed") from exc
    xml_declaration = _XML_DECLARATION_START.match(body)
    if xml_declaration is not None:
        declaration_end = body.find(b"?>", xml_declaration.end())
        if declaration_end >= 0:
            encoding = _XML_ENCODING.search(body, xml_declaration.end(), declaration_end)
            if encoding is not None and encoding.group(2).lower() not in {b"utf-8", b"utf8"}:
                raise ValueError("XML declarations and non-UTF-8-compatible bytes are not allowed")
    leading = body.lstrip()
    if not leading.startswith(b"<") or _ENTITY.search(body):
        raise ValueError("XML declarations are not allowed")
    prolog_offset = _skip_xml_prolog_misc(body, 0)
    if prolog_offset is None:
        raise ValueError("XML declarations are not allowed")
    sanitized = body
    if _DOCTYPE_START.match(body, prolog_offset):
        declaration = _DOCTYPE.match(body, prolog_offset)
        if declaration is None:
            raise ValueError("XML declarations are not allowed")
        root_offset = _skip_xml_prolog_misc(body, declaration.end())
        if root_offset is None or not _is_xml_root_start(body, root_offset):
            raise ValueError("XML declarations are not allowed")
        sanitized = body[:declaration.start()] + body[declaration.end():]
    elif body.startswith(b"<!", prolog_offset) or not _is_xml_root_start(body, prolog_offset):
        raise ValueError("XML declarations are not allowed")
    root = ET.fromstring(sanitized, parser=ET.XMLParser(encoding="utf-8"))

    def name(node: ET.Element) -> str:
        return node.tag.rsplit("}", 1)[-1].lower()

    # Alias extraction also checks metadata-only XML; fetch callers pass expected_ids.
    if expected_ids is not None and name(root) != "article":
        raise ET.ParseError("expected an article document")
    if expected_ids:
        metadata = [root]
        metadata.extend(meta for meta in root if name(meta) == "article-meta")
        metadata.extend(meta for front in root if name(front) == "front"
                        for meta in front if name(meta) == "article-meta")
        for parent in metadata:
            for node in parent:
                if name(node) != "article-id":
                    continue
                kind = node.get("pub-id-type", "").lower()
                kind = "pmc" if kind == "pmcid" else kind
                if kind not in expected_ids:
                    continue
                value = "".join(node.itertext()).strip().upper()
                if kind == "pmc" and value.isdigit():
                    value = "PMC" + value
                if value and value != expected_ids[kind].upper():
                    raise ET.ParseError("article identity conflicts with request")

    block_tags = {
        "abstract", "caption", "fig", "list", "list-item", "p", "sec",
        "supplementary-material", "table", "table-wrap", "title", "tr",
    }

    def text(node: ET.Element) -> str:
        parts = [node.text or ""]
        for child in node:
            child_text = text(child)
            if name(child) in block_tags:
                parts.extend((" ", child_text, " "))
            else:
                parts.append(child_text)
            parts.append(child.tail or "")
        return "".join(parts)

    pieces: list[str] = []

    def emit(value: str) -> None:
        value = " ".join(value.split())
        if value:
            pieces.append(value)

    def caption_block(node: ET.Element) -> str:
        label = next((text(child) for child in node if name(child) == "label"), "")
        caption = next((text(child) for child in node if name(child) == "caption"), "")
        return " ".join(part for part in (label, caption) if part)

    def mixed_content(node: ET.Element) -> None:
        pending = [node.text or ""]
        for child in node:
            if any(name(item) in block_tags for item in child.iter()):
                emit("".join(pending))
                pending = []
                walk(child)
            else:
                pending.append(text(child))
            pending.append(child.tail or "")
        emit("".join(pending))

    def walk(node: ET.Element) -> None:
        tag = name(node)
        if tag == "ref-list":
            return
        if tag == "article-title":
            emit(text(node))
            return
        if tag in {"abstract", "caption", "list", "list-item", "p"}:
            mixed_content(node)
            return
        if tag in {"fig", "table-wrap"}:
            emit(caption_block(node))
            for child in node:
                if name(child) not in {"label", "caption"}:
                    walk(child)
            return
        if tag == "supplementary-material":
            emit(caption_block(node))
            return
        if tag in {"sec", "ack", "app", "boxed-text"}:
            title = next((text(child) for child in node if name(child) == "title"), "")
            emit(title)
            for child in node:
                if name(child) != "title":
                    walk(child)
            return
        if tag == "tr":
            emit(" | ".join(text(cell) for cell in node if name(cell) in {"td", "th"}))
            return
        if tag == "title":
            emit(text(node))
            return
        for child in node:
            walk(child)

    walk(root)
    plain = "\n\n".join(pieces)
    if expected_ids is not None and not plain:
        raise ET.ParseError("article contains no extracted text")
    return plain


def _open_license(value: str) -> bool:
    normalized = re.sub(r"[\s-]+", " ", value.casefold()).strip()
    if re.fullmatch(
        r"(?:cc(?:0| by(?: nc)?(?: nd| sa)?)(?: \d+(?:\.\d+)?)?"
        r"|public domain(?: dedication| license)?)", normalized.removeprefix("creative commons "),
    ):
        return True
    if re.fullmatch(
        r"creative commons (?:attribution(?: noncommercial)?(?: noderivatives| sharealike)?|zero|public domain)"
        r"(?: \d+(?:\.\d+)?)?(?: international| unported| generic)?(?: license)?", normalized,
    ):
        return True
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme.lower() not in {"https", "http"} or parsed.hostname not in {"creativecommons.org", "www.creativecommons.org"}:
            return False
        if parsed.port not in (None, 80 if parsed.scheme.lower() == "http" else 443) or "@" in parsed.netloc:
            return False
        return re.fullmatch(
            r"/(?:licenses/by(?:-nc)?(?:-nd|-sa)?/\d+\.\d+|publicdomain/(?:zero|mark)/1\.0)"
            r"(?:/(?:deed(?:\.[a-zA-Z_-]+)?|legalcode)?)?", parsed.path,
        ) is not None
    except ValueError:
        return False


def _remove_publication_temporaries(output_dir: Path) -> None:
    # The caller holds the ledger lock, so no live publisher owns these names.
    for path in output_dir.iterdir():
        if _PUBLICATION_TEMPORARY.fullmatch(path.name):
            path.unlink()


def _publish_pair(output_dir: Path, pmcid: str, xml: bytes, plain: str) -> None:
    """Stage both artifacts before exposing either; caller holds the ledger lock."""
    _remove_publication_temporaries(output_dir)
    staged: list[Path] = []
    try:
        for suffix in _PUBLICATION_TEMPORARY_SUFFIXES:
            descriptor, name = tempfile.mkstemp(
                prefix=f"{_PUBLICATION_TEMPORARY_PREFIX}{uuid.uuid4().hex}-", suffix=suffix, dir=output_dir)
            staged.append(Path(name))
            os.close(descriptor)
        staged[0].write_bytes(xml)
        staged[1].write_text(plain, encoding="utf-8")
        for path in staged:
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        os.replace(staged[0], output_dir / f"{pmcid}.xml")
        os.replace(staged[1], output_dir / f"{pmcid}.txt")
    finally:
        for path in staged:
            path.unlink(missing_ok=True)


def _prepare_output_paths(root: Path, ids: list[str]) -> tuple[Path, Path]:
    output_dir = root / "fulltext"
    if output_dir.is_symlink() or (output_dir.exists() and not output_dir.is_dir()):
        raise ValueError("fulltext output path must be a regular directory")
    if output_dir.exists():
        try:
            output_dir.resolve(strict=True).relative_to(root)
            for item in output_dir.iterdir():
                try:
                    metadata = item.lstat()
                except FileNotFoundError:
                    # A concurrent publisher can replace or remove its staging files.
                    if _PUBLICATION_TEMPORARY.fullmatch(item.name):
                        continue
                    raise
                if not stat.S_ISREG(metadata.st_mode):
                    raise ValueError(f"unsafe fulltext entry: {item.name}")
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("fulltext output path is unsafe") from exc
    else:
        output_dir.mkdir(exist_ok=True)
    for identifier in ids:
        if identifier.startswith("pmcid:"):
            pmcid = identifier.split(":", 1)[1].upper()
            for suffix in (".xml", ".txt"):
                candidate = _safe_run_file(root, f"fulltext/{pmcid}{suffix}", required=False)
                if candidate is None:
                    raise ValueError("unsafe fulltext artifact path")
    ledger = _safe_run_file(root, "fulltext/fetch-ledger.jsonl", required=False)
    if ledger is None:
        raise ValueError("unsafe fulltext ledger path")
    return output_dir, ledger


def fetch_fulltext(
    ids: list[str], run_dir: str | Path, *, execute: bool = False,
    fetch: Callable[..., Any] | None = None, max_fetches: int = MAX_FETCHES,
    max_seconds: float = MAX_SECONDS, max_body_bytes: int = MAX_BODY_BYTES,
    max_candidates: int = MAX_CANDIDATES,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    all_ids = _normalize_ids(ids)
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or not 1 <= max_candidates <= MAX_CANDIDATE_LIMIT:
        raise ValueError(f"max_candidates must be between 1 and {MAX_CANDIDATE_LIMIT}")
    normalized = all_ids[:max_candidates]
    dropped_count = len(all_ids) - len(normalized)
    for value, limit, maximum in ((max_fetches, "max_fetches", MAX_FETCHES), (max_body_bytes, "max_body_bytes", MAX_BODY_BYTES)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(f"{limit} must be between 0 and {maximum}")
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)) or not 0 < max_seconds <= MAX_SECONDS:
        raise ValueError(f"max_seconds must be > 0 and at most {MAX_SECONDS}")
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
    output_dir = root / "fulltext"
    if execute:
        output_dir, ledger_path = _prepare_output_paths(root, normalized)
    fetcher = fetch or _http_fetch
    started = clock()
    results: list[dict[str, Any]] = []
    fulltext_count = 0
    stop_for_cap = False
    ledger_failed = False
    requests_recorded = 0
    resolved_pmcids: set[str] = set()

    def request(url: str, query: str, pmcid: str | None = None, license_value: str | None = None,
                expected_ids: dict[str, str] | None = None):
        nonlocal stop_for_cap, ledger_failed, requests_recorded
        remaining = max_seconds - (clock() - started)
        if remaining <= 0:
            stop_for_cap = True
            return None, b"", False, False, None
        response_status: int | None = None
        body = b""
        plain: str | Exception | None = None
        try:
            deadline = time.monotonic() + remaining
            response = fetcher(url, timeout=min(10.0, remaining), max_body_bytes=max_body_bytes)
            if isinstance(response, tuple):
                response_status, body = response
            else:
                try:
                    response_status = response.status
                    body = _read_with_deadline(response, max_body_bytes + 1, deadline)
                finally:
                    close = getattr(response, "close", None)
                    if close is not None:
                        close()
            if isinstance(body, str):
                body = body.encode("utf-8")
            if len(body) > max_body_bytes:
                raise ValueError("response exceeds body cap")
            if clock() - started >= max_seconds:
                stop_for_cap = True
        except (OSError, TimeoutError, http.client.HTTPException, urllib.error.URLError, ValueError, TypeError, AttributeError):
            response_status, body = None, b""
            if clock() - started >= max_seconds:
                stop_for_cap = True
        if response_status == 200 and pmcid is not None:
            try:
                plain = _plain_text(body, expected_ids=expected_ids)
            except (ET.ParseError, ValueError, RecursionError) as error:
                plain = error
        row = {
            "query_id": "fulltext-" + uuid.uuid4().hex,
            "source": "europepmc",
            "query": query,
            "url": url,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "status": "complete" if response_status == 200 and not isinstance(plain, Exception) else "unavailable",
            "response_sha256": hashlib.sha256(body).hexdigest() if response_status is not None else None,
            "fulltext_pmcid": pmcid,
            "license": license_value,
        }
        row_recorded = False
        try:
            with ledger_path.open("a+b") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                stream.seek(0, 2)
                prefix = b""
                if stream.tell():
                    stream.seek(-1, 2)
                    if stream.read(1) != b"\n":
                        prefix = b"\n"
                stream.write(prefix + (json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
                stream.flush()
                requests_recorded += 1
                row_recorded = True
                if pmcid is not None and response_status == 200 and isinstance(plain, str):
                    _publish_pair(output_dir, pmcid, body, plain)
        except OSError:
            if not row_recorded:
                ledger_failed = True
            return response_status, body, False, True, plain
        return response_status, body, True, True, plain

    for identifier in normalized:
        if not execute:
            results.append({"identifier": identifier, "status": "planned"})
            continue
        if ledger_failed:
            results.append({"identifier": identifier, "status": "write-failed"})
            continue
        if stop_for_cap or fulltext_count >= max_fetches:
            results.append({"identifier": identifier, "status": "skipped-cap"})
            stop_for_cap = True
            continue
        query = _search_query(identifier)
        params = urllib.parse.urlencode({"query": query, "resultType": "core", "format": "json"})
        core_url = f"{BASE}/search?{params}"
        status, body, ledger_ok, did_request, _ = request(core_url, query)
        if not did_request:
            results.append({"identifier": identifier, "status": "skipped-cap"})
            continue
        if not ledger_ok:
            results.append({"identifier": identifier, "status": "write-failed"})
            continue
        if status != 200:
            reason = f"http-{status}" if status is not None else "request-failed"
            results.append({"identifier": identifier, "status": "unavailable", "reason": reason})
            continue
        try:
            payload = json.loads(body.decode("utf-8"))
            records = payload.get("resultList", {}).get("result", [])
            if not isinstance(records, list):
                raise ValueError("malformed Europe PMC result list")
            record = next((candidate for candidate in records
                           if isinstance(candidate, dict) and _record_matches(candidate, identifier)), None)
        except (json.JSONDecodeError, UnicodeError, AttributeError, TypeError, ValueError, RecursionError):
            results.append({"identifier": identifier, "status": "unavailable",
                            "reason": "search-response-malformed"})
            continue
        if record is None:
            results.append({"identifier": identifier, "status": "not-found"})
            continue
        pmcid = str(record.get("pmcid", "")).upper()
        if not re.fullmatch(r"PMC\d+", pmcid):
            results.append({"identifier": identifier, "status": "unavailable", "reason": "no-pmcid"})
            continue
        if pmcid in resolved_pmcids:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "status": f"duplicate-of:{pmcid}"})
            continue
        resolved_pmcids.add(pmcid)
        raw_license = record.get("license")
        license_value = raw_license.strip() if isinstance(raw_license, str) else ""
        if record.get("isOpenAccess") != "Y":
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value or None, "status": "not-open-access"})
            continue
        if not license_value:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid, "status": "license-unknown"})
            continue
        if not _open_license(license_value):
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "not-open-access"})
            continue
        if stop_for_cap:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "skipped-cap"})
            stop_for_cap = True
            continue
        full_url = f"{BASE}/{pmcid}/fullTextXML"
        expected_ids = {"pmc": pmcid}
        pmid = identifier.split(":", 1)[1] if identifier.startswith("pmid:") else record.get("pmid")
        if isinstance(pmid, (str, int)) and not isinstance(pmid, bool) and str(pmid):
            expected_ids["pmid"] = str(pmid)
        status, xml, ledger_ok, did_request, plain = request(
            full_url, f"PMCID:{pmcid} fullTextXML", pmcid, license_value, expected_ids)
        if not did_request:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "skipped-cap"})
            continue
        fulltext_count += 1
        if not ledger_ok:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "write-failed"})
            continue
        if status != 200:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "unavailable",
                            "reason": f"http-{status}" if status is not None else "request-failed"})
            continue
        try:
            if isinstance(plain, Exception):
                raise plain
        except ET.ParseError:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "unavailable", "reason": "xml-parse-error"})
            continue
        except (ValueError, RecursionError):
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "unavailable",
                            "reason": "xml-declaration-refused"})
            continue
        results.append({"identifier": identifier, "fulltext_pmcid": pmcid, "license": license_value,
                        "status": "fetched", "response_sha256": hashlib.sha256(xml).hexdigest()})

    cap_reached = stop_for_cap or any(result.get("status") == "skipped-cap" for result in results)
    return {"schema": "open-fulltext-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
            "execute": execute, "results": results, "requests_recorded": requests_recorded,
            "fetch_ledger": "fulltext/fetch-ledger.jsonl",
            "caps": {"fulltext_fetches": max_fetches, "wall_seconds": max_seconds,
                     "body_bytes": max_body_bytes, "candidates": max_candidates},
            "cap_reached": cap_reached, "truncated": dropped_count > 0,
            "dropped_count": dropped_count}
