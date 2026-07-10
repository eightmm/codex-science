"""Small read-only clients for public scientific data sources."""

from __future__ import annotations

import json
import html
import re
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


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
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


class PDBConnector:
    def __init__(self, *, post_json: Callable[[str, dict[str, Any]], Any] = post_json) -> None:
        self._post_json = post_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = {
            "query": {"type": "terminal", "service": "full_text", "parameters": {"value": query}},
            "return_type": "entry",
            "request_options": {"paginate": {"start": 0, "rows": limit}},
        }
        response = self._post_json("https://search.rcsb.org/rcsbsearch/v2/query", payload)
        return [
            {
                "id": str(item.get("identifier", "")),
                "title": "",
                "score": str(item.get("score", "")),
                "url": f"https://www.rcsb.org/structure/{item.get('identifier', '')}",
            }
            for item in response.get("result_set", [])[:limit]
            if item.get("identifier")
        ]


class ChEMBLConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"q": query, "limit": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?{params}")
        results = []
        for item in payload.get("molecules", [])[:limit]:
            identifier = str(item.get("molecule_chembl_id", ""))
            if not identifier:
                continue
            structures = item.get("molecule_structures") or {}
            results.append(
                {
                    "id": identifier,
                    "title": str(item.get("pref_name") or identifier),
                    "canonical_smiles": str(structures.get("canonical_smiles") or ""),
                    "url": f"https://www.ebi.ac.uk/chembl/explore/compound/{identifier}",
                }
            )
        return results


class PubChemConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        encoded = urllib.parse.quote(query, safe="")
        properties = "Title,IUPACName,CanonicalSMILES,IsomericSMILES,MolecularFormula,MolecularWeight"
        payload = self._fetch_json(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/property/{properties}/JSON"
        )
        results = []
        for item in payload.get("PropertyTable", {}).get("Properties", [])[:limit]:
            identifier = str(item.get("CID", ""))
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("Title") or item.get("IUPACName") or identifier),
                        "molecular_formula": str(item.get("MolecularFormula") or ""),
                        "molecular_weight": str(item.get("MolecularWeight") or ""),
                        "smiles": str(
                            item.get("SMILES")
                            or item.get("ConnectivitySMILES")
                            or item.get("IsomericSMILES")
                            or item.get("CanonicalSMILES")
                            or ""
                        ),
                        "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{identifier}",
                    }
                )
        return results


class EuropePMCConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "pageSize": limit, "format": "json"})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}")
        results = []
        for item in payload.get("resultList", {}).get("result", [])[:limit]:
            identifier = str(item.get("id", ""))
            source = str(item.get("source", ""))
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("title") or identifier),
                        "source": source,
                        "doi": str(item.get("doi") or ""),
                        "url": f"https://europepmc.org/article/{source}/{identifier}",
                    }
                )
        return results


class OpenAlexConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query, "per-page": limit})
        payload = self._fetch_json(f"https://api.openalex.org/works?{params}")
        results = []
        for item in payload.get("results", [])[:limit]:
            url = str(item.get("id", ""))
            identifier = url.rsplit("/", 1)[-1]
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("display_name") or identifier),
                        "doi": str(item.get("doi") or ""),
                        "publication_year": str(item.get("publication_year") or ""),
                        "url": url,
                    }
                )
        return results


class ClinicalTrialsConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query.term": query, "pageSize": limit, "format": "json"})
        payload = self._fetch_json(f"https://clinicaltrials.gov/api/v2/studies?{params}")
        results = []
        for item in payload.get("studies", [])[:limit]:
            protocol = item.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            identifier = str(identification.get("nctId", ""))
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(identification.get("briefTitle") or identifier),
                        "status": str(status.get("overallStatus") or ""),
                        "url": f"https://clinicaltrials.gov/study/{identifier}",
                    }
                )
        return results


class InterProConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query, "page_size": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/interpro/api/entry/interpro/?{params}")
        results = []
        for item in payload.get("results", [])[:limit]:
            metadata = item.get("metadata", {})
            identifier = str(metadata.get("accession", ""))
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(metadata.get("name") or identifier),
                        "type": str(metadata.get("type") or ""),
                        "url": f"https://www.ebi.ac.uk/interpro/entry/InterPro/{identifier}/",
                    }
                )
        return results


class QuickGOConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "limit": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/QuickGO/services/ontology/go/search?{params}")
        return [
            {
                "id": str(item.get("id", "")),
                "title": str(item.get("name") or item.get("id") or ""),
                "aspect": str(item.get("aspect") or ""),
                "url": f"https://www.ebi.ac.uk/QuickGO/term/{item.get('id', '')}",
            }
            for item in payload.get("results", [])[:limit]
            if item.get("id")
        ]


class OLSConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"q": query, "rows": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/ols4/api/search?{params}")
        results = []
        for item in payload.get("response", {}).get("docs", [])[:limit]:
            identifier = str(item.get("obo_id") or item.get("short_form") or "")
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("label") or identifier),
                        "ontology": str(item.get("ontology_name") or ""),
                        "url": str(item.get("iri") or ""),
                    }
                )
        return results


def _plain_text(value: Any) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


class ReactomeConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "cluster": "true"})
        payload = self._fetch_json(f"https://reactome.org/ContentService/search/query?{params}")
        entries = [entry for group in payload.get("results", []) for entry in group.get("entries", [])]
        return [
            {
                "id": str(item.get("stId") or item.get("id") or ""),
                "title": _plain_text(item.get("name")),
                "type": str(item.get("type") or ""),
                "url": f"https://reactome.org/content/detail/{item.get('stId') or item.get('id') or ''}",
            }
            for item in entries[:limit]
            if item.get("stId") or item.get("id")
        ]


class STRINGConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"identifier": query, "limit": limit})
        payload = self._fetch_json(f"https://string-db.org/api/json/resolve?{params}")
        return [
            {
                "id": str(item.get("stringId", "")),
                "title": str(item.get("preferredName") or item.get("stringId") or ""),
                "species": str(item.get("taxonName") or ""),
                "annotation": str(item.get("annotation") or ""),
                "url": f"https://string-db.org/network/{item.get('stringId', '')}",
            }
            for item in payload[:limit]
            if item.get("stringId")
        ]


class AlphaFoldConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(
            f"https://alphafold.ebi.ac.uk/api/prediction/{urllib.parse.quote(query, safe='')}"
        )
        return [
            {
                "id": str(item.get("modelEntityId", "")),
                "title": str(item.get("uniprotDescription") or item.get("modelEntityId") or ""),
                "uniprot_accession": str(item.get("uniprotAccession") or ""),
                "global_plddt": str(item.get("globalMetricValue") or ""),
                "cif_url": str(item.get("cifUrl") or ""),
                "url": f"https://alphafold.ebi.ac.uk/entry/{item.get('uniprotAccession', '')}",
            }
            for item in payload[:limit]
            if item.get("modelEntityId")
        ]
