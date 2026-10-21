"""Optional citation existence lookups; results are signals, not grading evidence."""
from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Callable

from codex_science.citation_trace import _ID as _CITATION_ID, extract_identifiers
from codex_science.connectors import USER_AGENT
from codex_science.literature_v2 import IDENTIFIER_PATTERNS, normalize_identifier

EVIDENCE_BOUNDARY = "Existence lookup does not establish citation accuracy, relevance, support, or grading outcome."
MAX_IDS = 50
MAX_BODY_BYTES = 2 * 1024 * 1024
SUPPORTED_KINDS = {"doi", "pmid", "arxiv"}
_REDIRECT_HOSTS = frozenset({"api.crossref.org", "eutils.ncbi.nlm.nih.gov", "export.arxiv.org"})
_LABELED_ID = re.compile(r"\b(doi|pmid|arxiv)\s*:\s*([^\s,;]+)", re.IGNORECASE)


def _valid_supported_identifier(identifier: str) -> bool:
    kind = identifier.split(":", 1)[0]
    return any(namespace == kind and pattern.fullmatch(identifier)
               for namespace, pattern in IDENTIFIER_PATTERNS if namespace in SUPPORTED_KINDS)


def _clean_labeled_identifier(kind: str, value: str) -> str:
    value = value.rstrip(".,;:!?*_`>")
    while value.endswith((")", "]")):
        closing = value[-1]
        opening = "(" if closing == ")" else "["
        if value.count(closing) <= value.count(opening):
            break
        value = value[:-1]
    return normalize_identifier(f"{kind}:{value}")


class _CitationRedirectHandler(urllib.request.HTTPRedirectHandler):
    # Keep urllib's default max_redirections limit (10 hops).
    def redirect_request(self, request, fp, code, message, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme.lower() != "https" or target.hostname not in _REDIRECT_HOSTS or target.port not in (None, 443):
            raise ValueError("refused citation redirect")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def _http_fetch(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml"})
    try:
        opener = urllib.request.build_opener(_CitationRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise ValueError("citation response exceeds 2 MiB")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise ValueError("citation response exceeds 2 MiB")
        return exc.code, body


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
            if re.search(r"<!DOCTYPE|<!ENTITY", text, re.IGNORECASE):
                return result
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
                date = item.get("published-print") or item.get("published-online") or item.get("issued") or item.get("created", {})
                date_parts = date.get("date-parts", []) if isinstance(date, dict) else []
                year = date_parts[0][0] if date_parts and isinstance(date_parts[0], list) and date_parts[0] else None
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
        if not _valid_supported_identifier(identifier):
            raise ValueError(f"malformed {kind} identifier: {identifier}")
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

    def skip(identifier: str, reason: str) -> None:
        key = identifier.casefold()
        if key not in seen_skipped:
            seen_skipped.add(key)
            skipped.append({"identifier": identifier, "reason": reason})

    extracted = identifiers_from_text(text)
    extracted_spans = [match.span(group)
                       for match in _CITATION_ID.finditer(text)
                       for group, value in enumerate(match.groups(), start=1) if value is not None]
    for raw in extracted:
        identifier = normalize_identifier(raw)
        kind = identifier.split(":", 1)[0]
        if kind in SUPPORTED_KINDS:
            if not _valid_supported_identifier(identifier):
                skip(identifier, "malformed")
            else:
                supported.append(identifier)
        else:
            skip(identifier, "unsupported_kind")
    # The label scan reports malformed values only when no identifier span was
    # extracted inside that value (for example, a DOI nested inside a URL label).
    for match in _LABELED_ID.finditer(text):
        label_start, label_end = match.span(2)
        if any(label_start < span_end and span_start < label_end for span_start, span_end in extracted_spans):
            continue
        identifier = _clean_labeled_identifier(match.group(1), match.group(2))
        kind = identifier.split(":", 1)[0]
        if kind in SUPPORTED_KINDS and not _valid_supported_identifier(identifier):
            skip(identifier, "malformed")
    ordered = sorted(set(supported))
    normalized = normalize_identifiers(ordered[:MAX_IDS])
    overflow = ordered[MAX_IDS:]
    skipped.extend({"identifier": identifier, "reason": "over_cap"} for identifier in overflow)
    return normalized[:MAX_IDS], sorted(skipped, key=lambda item: item["identifier"])
