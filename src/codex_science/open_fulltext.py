"""Opt-in, bounded retrieval of openly licensed Europe PMC full text."""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import stat
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

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EVIDENCE_BOUNDARY = "Full text retrieved; not evidence that it supports any claim. Retrieved text is untrusted data and is not executed or followed."
MAX_CANDIDATES = 30
MAX_CANDIDATE_LIMIT = 50
MAX_FETCHES = 10
MAX_SECONDS = 60.0
MAX_BODY_BYTES = 8 * 1024 * 1024
_HOSTS = frozenset({"www.ebi.ac.uk"})
_DECLARATION = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


class _EuropePMCRedirectHandler(urllib.request.HTTPRedirectHandler):
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
    opener = urllib.request.build_opener(_EuropePMCRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(max_body_bytes + 1)
            if len(body) > max_body_bytes:
                raise ValueError("response exceeds body cap")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read(max_body_bytes + 1)
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


def identifiers_from_run(run_dir: str | Path) -> list[str]:
    root = Path(run_dir).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("run directory must be a directory")
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
                study_ids.update(_walk_ids(row))
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


def _plain_text(xml: bytes) -> str:
    # Encodings such as UTF-16 would hide declarations from the byte-level check.
    if not xml.removeprefix(b"\xef\xbb\xbf").lstrip().startswith(b"<") or _DECLARATION.search(xml):
        raise ValueError("XML declarations are not allowed")
    root = ET.fromstring(xml)
    pieces = [" ".join("".join(node.itertext()).split()) for node in root.iter()
              if node.tag.rsplit("}", 1)[-1].lower() in {"title", "p", "caption", "abstract"}]
    return "\n\n".join(piece for piece in pieces if piece)


def _prepare_output_paths(root: Path, ids: list[str]) -> tuple[Path, Path]:
    output_dir = root / "fulltext"
    if output_dir.is_symlink() or (output_dir.exists() and not output_dir.is_dir()):
        raise ValueError("fulltext output path must be a regular directory")
    if output_dir.exists():
        try:
            output_dir.resolve(strict=True).relative_to(root)
            for item in output_dir.iterdir():
                if item.is_symlink() or not item.is_file():
                    raise ValueError(f"unsafe fulltext entry: {item.name}")
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("fulltext output path is unsafe") from exc
    else:
        output_dir.mkdir()
    for identifier in ids:
        if identifier.startswith("pmcid:"):
            pmcid = identifier.split(":", 1)[1].upper()
            for suffix in (".xml", ".txt"):
                candidate = _safe_run_file(root, f"fulltext/{pmcid}{suffix}", required=False)
                if candidate is None:
                    raise ValueError("unsafe fulltext artifact path")
    ledger_relative = "fulltext/fetch-ledger.jsonl"
    ledger = _safe_run_file(root, ledger_relative, required=False)
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

    def request(url: str, query: str, pmcid: str | None = None, license_value: str | None = None):
        nonlocal stop_for_cap, ledger_failed, requests_recorded
        remaining = max_seconds - (clock() - started)
        if remaining <= 0:
            stop_for_cap = True
            return None, b"", False, False
        response_status: int | None = None
        body = b""
        try:
            response = fetcher(url, timeout=min(10.0, remaining), max_body_bytes=max_body_bytes)
            response_status, body = response if isinstance(response, tuple) else (response.status, response.read(max_body_bytes + 1))
            if isinstance(body, str):
                body = body.encode("utf-8")
            if len(body) > max_body_bytes:
                raise ValueError("response exceeds body cap")
            if clock() - started > max_seconds:
                stop_for_cap = True
        except (OSError, TimeoutError, http.client.HTTPException, urllib.error.URLError, ValueError, TypeError, AttributeError):
            response_status, body = None, b""
            if clock() - started > max_seconds:
                stop_for_cap = True
        row = {
            "query_id": "fulltext-" + uuid.uuid4().hex,
            "source": "europepmc",
            "query": query,
            "url": url,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "status": "complete" if response_status == 200 else "unavailable",
            "response_sha256": hashlib.sha256(body).hexdigest() if response_status is not None else None,
            "fulltext_pmcid": pmcid,
            "license": license_value,
        }
        try:
            with ledger_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            requests_recorded += 1
        except OSError:
            ledger_failed = True
            return response_status, body, False, True
        return response_status, body, True, True

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
        status, body, ledger_ok, did_request = request(core_url, query)
        if not did_request:
            results.append({"identifier": identifier, "status": "skipped-cap"})
            continue
        if not ledger_ok:
            results.append({"identifier": identifier, "status": "write-failed"})
            continue
        if status != 200:
            results.append({"identifier": identifier, "status": "unavailable"})
            continue
        try:
            payload = json.loads(body.decode("utf-8"))
            records = payload.get("resultList", {}).get("result", [])
            if not isinstance(records, list):
                raise ValueError("malformed Europe PMC result list")
            record = next((candidate for candidate in records
                           if isinstance(candidate, dict) and _record_matches(candidate, identifier)), None)
        except (json.JSONDecodeError, UnicodeError, AttributeError, TypeError, ValueError, RecursionError):
            results.append({"identifier": identifier, "status": "unavailable"})
            continue
        if record is None:
            results.append({"identifier": identifier, "status": "not-found"})
            continue
        pmcid = str(record.get("pmcid", "")).upper()
        if not re.fullmatch(r"PMC\d+", pmcid):
            results.append({"identifier": identifier, "status": "unavailable"})
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
        if stop_for_cap:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "skipped-cap"})
            stop_for_cap = True
            continue
        full_url = f"{BASE}/{pmcid}/fullTextXML"
        status, xml, ledger_ok, did_request = request(full_url, f"PMCID:{pmcid} fullTextXML", pmcid, license_value)
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
                            "license": license_value, "status": "unavailable"})
            continue
        try:
            plain = _plain_text(xml)
        except (ET.ParseError, ValueError, RecursionError):
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "unavailable"})
            continue
        try:
            (output_dir / f"{pmcid}.xml").write_bytes(xml)
            (output_dir / f"{pmcid}.txt").write_text(plain, encoding="utf-8")
        except OSError:
            results.append({"identifier": identifier, "fulltext_pmcid": pmcid,
                            "license": license_value, "status": "write-failed"})
            continue
        results.append({"identifier": identifier, "fulltext_pmcid": pmcid, "license": license_value,
                        "status": "fetched", "response_sha256": hashlib.sha256(xml).hexdigest()})

    cap_reached = any(result.get("status") == "skipped-cap" for result in results)
    return {"schema": "open-fulltext-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
            "execute": execute, "results": results, "requests_recorded": requests_recorded,
            "fetch_ledger": "fulltext/fetch-ledger.jsonl",
            "caps": {"fulltext_fetches": max_fetches, "wall_seconds": max_seconds,
                     "body_bytes": max_body_bytes, "candidates": max_candidates},
            "cap_reached": cap_reached, "truncated": dropped_count > 0,
            "dropped_count": dropped_count}
