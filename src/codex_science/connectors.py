"""Small read-only clients for public scientific data sources."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any


USER_AGENT = "codex-science/0.1 (+https://github.com/)"


def _validate(query: str, limit: int) -> tuple[str, int]:
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty")
    if len(query) > 500:
        raise ValueError("Query must be at most 500 characters")
    if not 1 <= limit <= 10:
        raise ValueError("Limit must be between 1 and 10")
    return query, limit


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


class PubMedConnector:
    def __init__(self, *, fetch_json: Callable[[str], dict[str, Any]] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"db": "pubmed", "term": query, "retmode": "json", "retmax": limit}
        )
        payload = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
        ids = payload.get("esearchresult", {}).get("idlist", [])
        return [
            {"id": str(identifier), "title": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"}
            for identifier in ids[:limit]
        ]


class ArxivConnector:
    def __init__(self, *, fetch_text: Callable[[str], str] = fetch_text) -> None:
        self._fetch_text = fetch_text

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"search_query": f"all:{query}", "start": 0, "max_results": limit}
        )
        root = ET.fromstring(self._fetch_text(f"https://export.arxiv.org/api/query?{params}"))
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        results: list[dict[str, str]] = []
        for entry in root.findall("atom:entry", namespace)[:limit]:
            url = (entry.findtext("atom:id", default="", namespaces=namespace) or "").strip()
            identifier = url.rsplit("/", 1)[-1]
            results.append(
                {
                    "id": identifier,
                    "title": " ".join((entry.findtext("atom:title", default="", namespaces=namespace) or "").split()),
                    "summary": " ".join((entry.findtext("atom:summary", default="", namespaces=namespace) or "").split()),
                    "url": url,
                }
            )
        return results


class UniProtConnector:
    def __init__(self, *, fetch_json: Callable[[str], dict[str, Any]] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "format": "json", "size": limit})
        payload = self._fetch_json(f"https://rest.uniprot.org/uniprotkb/search?{params}")
        results: list[dict[str, str]] = []
        for item in payload.get("results", [])[:limit]:
            accession = str(item.get("primaryAccession", ""))
            description = item.get("proteinDescription", {})
            title = (
                description.get("recommendedName", {}).get("fullName", {}).get("value")
                or item.get("uniProtkbId")
                or accession
            )
            results.append(
                {
                    "id": accession,
                    "title": str(title),
                    "url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
                }
            )
        return results
