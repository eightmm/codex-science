"""Source-specific true-pagination operations for Connector Contract v3."""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping

from codex_science.connector_contract import QueryRequest
from codex_science.transport_v3 import PageRequest


def _query(request: QueryRequest) -> str:
    value = request.parameters.get("query")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("parameters.query is required")
    return value.strip()


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    result = int(value)
    if result < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return result


@dataclass(frozen=True)
class PubMedSearchV3:
    source: str = "pubmed"
    operation: str = "search"

    def first_request(self, request: QueryRequest) -> PageRequest:
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": _query(request),
            "retmode": "json",
            "retstart": 0,
            "retmax": request.page_size,
            "usehistory": "y",
        }
        if request.evidence_cutoff:
            params.update({"datetype": "pdat", "maxdate": request.evidence_cutoff.replace("-", "/")})
        for key in ("mindate", "maxdate", "datetype", "sort"):
            if request.parameters.get(key) not in (None, ""):
                params[key] = request.parameters[key]
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(params)
        return PageRequest("GET", url, {}, cursor="0")

    def next_request(self, request: QueryRequest, page_request: PageRequest, payload: Any, page_index: int) -> PageRequest | None:
        result = payload.get("esearchresult")
        if not isinstance(result, dict):
            raise ValueError("missing esearchresult")
        count = _integer(result.get("count", 0), "count")
        current = _integer(result.get("retstart", page_index * request.page_size), "retstart")
        returned = len(result.get("idlist") or [])
        next_start = current + returned
        if returned == 0 or next_start >= count:
            return None
        parsed = urllib.parse.urlsplit(page_request.url)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        params["retstart"] = str(next_start)
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), parsed.fragment))
        return PageRequest("GET", url, {}, cursor=str(next_start))

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        result = payload.get("esearchresult")
        if not isinstance(result, dict):
            raise ValueError("missing esearchresult")
        return [
            {"id": str(identifier), "title": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"}
            for identifier in result.get("idlist", [])
        ]

    def source_release(self, payload: Any, headers: Mapping[str, str]) -> str | None:
        return headers.get("last-modified") or headers.get("date")


@dataclass(frozen=True)
class EuropePMCSearchV3:
    source: str = "europepmc"
    operation: str = "search"

    def first_request(self, request: QueryRequest) -> PageRequest:
        query = _query(request)
        if request.evidence_cutoff:
            query = f"({query}) AND FIRST_PDATE:[* TO {request.evidence_cutoff}]"
        params = {
            "query": query,
            "pageSize": request.page_size,
            "format": "json",
            "cursorMark": "*",
            "resultType": str(request.parameters.get("result_type", "core")),
        }
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)
        return PageRequest("GET", url, {}, cursor="*")

    def next_request(self, request: QueryRequest, page_request: PageRequest, payload: Any, page_index: int) -> PageRequest | None:
        cursor = payload.get("nextCursorMark")
        returned = payload.get("resultList", {}).get("result", []) if isinstance(payload.get("resultList"), dict) else []
        if not isinstance(cursor, str) or not cursor or not returned or cursor == page_request.cursor:
            return None
        parsed = urllib.parse.urlsplit(page_request.url)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        params["cursorMark"] = cursor
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), parsed.fragment))
        return PageRequest("GET", url, {}, cursor=cursor)

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            raise ValueError("missing resultList")
        records = []
        for item in result_list.get("result", []):
            identifier = str(item.get("id") or "")
            source = str(item.get("source") or "")
            if identifier:
                records.append({
                    "id": identifier,
                    "title": str(item.get("title") or identifier),
                    "source": source,
                    "doi": str(item.get("doi") or ""),
                    "publication_date": str(item.get("firstPublicationDate") or ""),
                    "url": f"https://europepmc.org/article/{source}/{identifier}",
                })
        return records

    def source_release(self, payload: Any, headers: Mapping[str, str]) -> str | None:
        return headers.get("last-modified") or headers.get("date")


@dataclass(frozen=True)
class ChEMBLMoleculeSearchV3:
    source: str = "chembl"
    operation: str = "search"

    def first_request(self, request: QueryRequest) -> PageRequest:
        params = {"q": _query(request), "limit": request.page_size, "offset": 0}
        url = "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?" + urllib.parse.urlencode(params)
        return PageRequest("GET", url, {}, cursor="0")

    def next_request(self, request: QueryRequest, page_request: PageRequest, payload: Any, page_index: int) -> PageRequest | None:
        page_meta = payload.get("page_meta")
        if not isinstance(page_meta, dict):
            raise ValueError("missing page_meta")
        next_url = page_meta.get("next")
        if not isinstance(next_url, str) or not next_url:
            return None
        if next_url.startswith("/"):
            next_url = "https://www.ebi.ac.uk" + next_url
        parsed = urllib.parse.urlsplit(next_url)
        cursor = dict(urllib.parse.parse_qsl(parsed.query)).get("offset")
        return PageRequest("GET", next_url, {}, cursor=cursor)

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        molecules = payload.get("molecules")
        if not isinstance(molecules, list):
            raise ValueError("missing molecules")
        records = []
        for item in molecules:
            identifier = str(item.get("molecule_chembl_id") or "")
            if not identifier:
                continue
            structures = item.get("molecule_structures") or {}
            records.append({
                "id": identifier,
                "title": str(item.get("pref_name") or identifier),
                "canonical_smiles": str(structures.get("canonical_smiles") or ""),
                "url": f"https://www.ebi.ac.uk/chembl/explore/compound/{identifier}",
            })
        return records

    def source_release(self, payload: Any, headers: Mapping[str, str]) -> str | None:
        return headers.get("last-modified") or headers.get("date")


@dataclass(frozen=True)
class PDBSearchV3:
    source: str = "pdb"
    operation: str = "search"

    def _body(self, request: QueryRequest, start: int) -> bytes:
        payload = {
            "query": {"type": "terminal", "service": "full_text", "parameters": {"value": _query(request)}},
            "return_type": "entry",
            "request_options": {"paginate": {"start": start, "rows": request.page_size}},
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def first_request(self, request: QueryRequest) -> PageRequest:
        return PageRequest(
            "POST",
            "https://search.rcsb.org/rcsbsearch/v2/query",
            {"Content-Type": "application/json"},
            body=self._body(request, 0),
            cursor="0",
        )

    def next_request(self, request: QueryRequest, page_request: PageRequest, payload: Any, page_index: int) -> PageRequest | None:
        result_set = payload.get("result_set")
        if not isinstance(result_set, list):
            raise ValueError("missing result_set")
        total = _integer(payload.get("total_count", len(result_set)), "total_count")
        start = _integer(page_request.cursor or 0, "cursor")
        next_start = start + len(result_set)
        if not result_set or next_start >= total:
            return None
        return PageRequest(
            "POST",
            page_request.url,
            {"Content-Type": "application/json"},
            body=self._body(request, next_start),
            cursor=str(next_start),
        )

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        result_set = payload.get("result_set")
        if not isinstance(result_set, list):
            raise ValueError("missing result_set")
        return [
            {
                "id": str(item["identifier"]),
                "title": "",
                "score": item.get("score"),
                "url": f"https://www.rcsb.org/structure/{item['identifier']}",
            }
            for item in result_set
            if item.get("identifier")
        ]

    def source_release(self, payload: Any, headers: Mapping[str, str]) -> str | None:
        return headers.get("last-modified") or headers.get("date")


SOURCE_OPERATIONS_V3 = {
    "pubmed": PubMedSearchV3(),
    "europepmc": EuropePMCSearchV3(),
    "chembl": ChEMBLMoleculeSearchV3(),
    "pdb": PDBSearchV3(),
}
