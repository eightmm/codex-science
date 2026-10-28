"""Source-specific true-pagination operations for Connector Contract v3."""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping

from codex_science.connectors import parse_esearch_ids
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


def _required_value(payload: Any, key: str) -> Any:
    if not isinstance(payload, Mapping):
        raise ValueError(f"invalid response object while reading {key}")
    if key not in payload:
        raise ValueError(f"missing {key}")
    return payload[key]


def _required_mapping(payload: Any, key: str) -> Mapping[str, Any]:
    value = _required_value(payload, key)
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid {key}: expected object")
    return value


def _required_list(payload: Any, key: str) -> list[Any]:
    value = _required_value(payload, key)
    if not isinstance(value, list):
        raise ValueError(f"invalid {key}: expected list")
    return value


def _required_integer(payload: Any, key: str, *, minimum: int = 0) -> int:
    value = _required_value(payload, key)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"invalid {key}: expected integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {key}: expected integer") from error
    if result < minimum:
        raise ValueError(f"invalid {key}: must be >= {minimum}")
    return result


def _pagination_drift(source: str, error: ValueError) -> ValueError:
    detail = str(error)
    if not detail.startswith(("missing ", "invalid ")):
        detail = f"invalid response: {detail}"
    return ValueError(f"schema-drift: {source} pagination {detail}")


def _pubmed_result(payload: Any) -> Mapping[str, Any]:
    result = _required_mapping(payload, "esearchresult")
    parse_esearch_ids(payload)
    _required_list(result, "idlist")
    return result


def _europepmc_results(payload: Any) -> list[Any]:
    result_list = _required_mapping(payload, "resultList")
    return _required_list(result_list, "result")


def _pdb_results(payload: Any) -> list[Any]:
    return _required_list(payload, "result_set")


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
        try:
            result = _pubmed_result(payload)
            count = _required_integer(result, "count")
            current = (
                _required_integer(result, "retstart")
                if "retstart" in result else page_index * request.page_size
            )
        except ValueError as error:
            raise _pagination_drift(self.source, error) from error
        returned = len(result["idlist"])
        next_start = current + returned
        if returned == 0 or next_start >= count:
            return None
        parsed = urllib.parse.urlsplit(page_request.url)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        params["retstart"] = str(next_start)
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), parsed.fragment))
        return PageRequest("GET", url, {}, cursor=str(next_start))

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        result = _pubmed_result(payload)
        ids = result["idlist"]
        return [
            {"id": str(identifier), "title": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"}
            for identifier in ids
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
        try:
            returned = _europepmc_results(payload)
        except ValueError as error:
            raise _pagination_drift(self.source, error) from error
        if not isinstance(payload, Mapping) or "nextCursorMark" not in payload:
            try:
                hit_count = _required_value(payload, "hitCount")
                if isinstance(hit_count, bool) or not isinstance(hit_count, int) or hit_count < 0:
                    raise ValueError("invalid hitCount: expected non-negative integer")
                if hit_count > page_index * request.page_size + len(returned):
                    raise ValueError("missing nextCursorMark")
            except ValueError as error:
                if str(error) == "missing hitCount":
                    error = ValueError("missing nextCursorMark")
                raise _pagination_drift(self.source, error) from error
            return None
        try:
            cursor = payload["nextCursorMark"]
            if not isinstance(cursor, str):
                raise ValueError("invalid nextCursorMark: expected string")
        except ValueError as error:
            raise _pagination_drift(self.source, error) from error
        if not returned:
            return None
        if not cursor or cursor == page_request.cursor:
            return None
        parsed = urllib.parse.urlsplit(page_request.url)
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        params["cursorMark"] = cursor
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(params), parsed.fragment))
        return PageRequest("GET", url, {}, cursor=cursor)

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        results = _europepmc_results(payload)
        records = []
        for item in results:
            identifier = str(item.get("id") or "")
            source = str(item.get("source") or "")
            if identifier:
                record = {
                    "id": identifier,
                    "title": str(item.get("title") or identifier),
                    "source": source,
                    "doi": str(item.get("doi") or ""),
                    "publication_date": str(item.get("firstPublicationDate") or ""),
                    "url": f"https://europepmc.org/article/{source}/{identifier}",
                }
                pmcid = item.get("pmcid")
                if isinstance(pmcid, str) and re.fullmatch(r"PMC\d+", pmcid.strip(), re.IGNORECASE):
                    record["pmcid"] = pmcid.strip().upper()
                records.append(record)
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
        try:
            page_meta = _required_mapping(payload, "page_meta")
            next_url = _required_value(page_meta, "next")
            if next_url is not None and next_url != "" and not isinstance(next_url, str):
                raise ValueError("invalid page_meta.next: expected string or null")
        except ValueError as error:
            raise _pagination_drift(self.source, error) from error
        if next_url is None or next_url == "":
            return None
        if next_url.startswith("/"):
            next_url = "https://www.ebi.ac.uk" + next_url
        parsed = urllib.parse.urlsplit(next_url)
        cursor = dict(urllib.parse.parse_qsl(parsed.query)).get("offset")
        return PageRequest("GET", next_url, {}, cursor=cursor)

    def normalize(self, payload: Any) -> list[dict[str, Any]]:
        molecules = _required_list(payload, "molecules")
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
    empty_status_codes: frozenset[int] = frozenset({204})

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
        try:
            result_set = _pdb_results(payload)
            total = _required_integer(payload, "total_count")
        except ValueError as error:
            raise _pagination_drift(self.source, error) from error
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
        result_set = _pdb_results(payload)
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
