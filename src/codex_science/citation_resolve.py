"""Optional citation existence lookups; results are signals, not grading evidence."""
from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Callable

from codex_science.citation_trace import extract_identifiers
from codex_science.connectors import USER_AGENT
from codex_science.literature_v2 import normalize_identifier

EVIDENCE_BOUNDARY = "Existence lookup does not establish citation accuracy, relevance, support, or grading outcome."
MAX_IDS = 50
SUPPORTED_KINDS = {"doi", "pmid", "arxiv"}


def _http_fetch(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _record(identifier: str, fetch: Callable[..., Any], timeout: float) -> dict[str, Any]:
    kind, value = identifier.split(":", 1)
    if kind == "doi":
        url = "https://api.crossref.org/works/" + urllib.parse.quote(value, safe="")
        source = "crossref"
    elif kind == "pmid":
        params = urllib.parse.urlencode({"db": "pubmed", "id": value, "retmode": "json"})
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + params
        source = "pubmed"
    elif kind == "arxiv":
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": value})
        source = "arxiv"
    else:
        raise ValueError(f"unsupported identifier: {identifier}")
    try:
        response = fetch(url, timeout=timeout)
        if isinstance(response, tuple) and len(response) == 2:
            status, body = response
        else:
            status, body = response.status, response.read()
        result: dict[str, Any] = {"identifier": identifier, "source": source, "http_status": int(status), "status": "unavailable"}
        if status == 404:
            result["status"] = "not_found"
            return result
        if status < 200 or status >= 300:
            return result
        text = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        if kind == "arxiv":
            root = ET.fromstring(text)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entries = root.findall("a:entry", ns)
            if not entries:
                result["status"] = "not_found"
                return result
            title = " ".join((entries[0].findtext("a:title", default="", namespaces=ns) or "").split())
            if len(entries) == 1 and title.casefold() == "error":
                result["status"] = "not_found"
                return result
            published = entries[0].findtext("a:published", default="", namespaces=ns)
            year = int(published[:4]) if published[:4].isdigit() else None
        else:
            payload = json.loads(text)
            if kind == "doi":
                item = payload["message"]
                titles = item.get("title", [])
                title = titles[0] if isinstance(titles, list) and titles else ""
                date = item.get("published-print") or item.get("published-online") or item.get("created", {})
                date_parts = date.get("date-parts", [])
                year = date_parts[0][0] if date_parts and date_parts[0] else None
            else:
                summary = payload["result"]
                item = summary.get(value)
                uids = summary.get("uids", [])
                if not isinstance(item, dict) or "error" in item or value not in {str(uid) for uid in uids}:
                    result["status"] = "not_found"
                    return result
                title = item.get("title", "")
                year = int(item["pubdate"][:4]) if str(item.get("pubdate", ""))[:4].isdigit() else None
        result["status"] = "resolved"
        if title:
            result["title"] = " ".join(str(title).split())
        if isinstance(year, int):
            result["year"] = year
        return result
    except (OSError, TimeoutError, http.client.HTTPException, ET.ParseError, ValueError, TypeError, KeyError, IndexError, AttributeError, json.JSONDecodeError, RecursionError, OverflowError):
        return {"identifier": identifier, "source": source, "status": "unavailable"}


def normalize_identifiers(ids: list[str]) -> list[str]:
    if not isinstance(ids, list) or len(ids) > MAX_IDS:
        raise ValueError("ids must be a list of at most 50 identifiers")
    normalized = []
    for raw in ids:
        if not isinstance(raw, str):
            raise TypeError("identifiers must be strings")
        identifier = normalize_identifier(raw)
        kind = identifier.split(":", 1)[0]
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"unsupported identifier kind: {kind}")
        if identifier not in normalized:
            normalized.append(identifier)
    return sorted(normalized)


def resolve_identifiers(
    ids: list[str], *, fetch: Callable[..., Any] | None = None, timeout: float = 10,
    delay: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    normalized = normalize_identifiers(ids)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout must be positive")
    if not callable(delay):
        raise TypeError("delay must be callable")
    fetcher = fetch or _http_fetch
    records = []
    for index, identifier in enumerate(normalized):
        if index:
            delay(0.1)
        records.append(_record(identifier, fetcher, float(timeout)))
    return {"schema": "citation-resolution-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
            "results": records, "skipped_identifiers": []}


def identifiers_from_text(text: str) -> list[str]:
    return [item["identifier"] for item in extract_identifiers(text)]


def supported_identifiers_from_text(text: str) -> tuple[list[str], list[dict[str, str]]]:
    supported: list[str] = []
    skipped: list[dict[str, str]] = []
    seen_skipped: set[str] = set()
    for raw in identifiers_from_text(text):
        identifier = normalize_identifier(raw)
        if identifier.split(":", 1)[0] in SUPPORTED_KINDS:
            supported.append(identifier)
        elif identifier not in seen_skipped:
            seen_skipped.add(identifier)
            skipped.append({"identifier": identifier, "reason": "unsupported_kind"})
    return normalize_identifiers(supported), sorted(skipped, key=lambda item: item["identifier"])
