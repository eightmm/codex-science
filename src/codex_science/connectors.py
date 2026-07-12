"""Small read-only clients for public scientific data sources."""

from __future__ import annotations

import json
import html
import math
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


def _value_text(value: Any) -> str:
    return "" if value is None else str(value)


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


class MyGeneConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"q": query, "size": limit})
        payload = self._fetch_json(f"https://mygene.info/v3/query?{params}")
        return [
            {
                "id": str(item.get("_id") or item.get("entrezgene") or ""),
                "title": str(item.get("symbol") or item.get("name") or item.get("_id") or ""),
                "description": str(item.get("name") or ""),
                "species_taxid": str(item.get("taxid") or ""),
                "url": f"https://www.ncbi.nlm.nih.gov/gene/{item.get('_id', '')}",
            }
            for item in payload.get("hits", [])[:limit]
            if item.get("_id") or item.get("entrezgene")
        ]


class EnsemblConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        symbol = urllib.parse.quote(query, safe="")
        payload = self._fetch_json(
            f"https://rest.ensembl.org/xrefs/symbol/homo_sapiens/{symbol}?external_db=HGNC"
        )
        return [
            {
                "id": str(item.get("id") or ""),
                "title": query,
                "type": str(item.get("type") or ""),
                "species": "homo_sapiens",
                "url": f"https://www.ensembl.org/Homo_sapiens/Gene/Summary?g={item.get('id', '')}",
            }
            for item in payload[:limit]
            if item.get("id")
        ]


class NCBIGeneConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"db": "gene", "term": f"{query} AND human[orgn]", "retmode": "json", "retmax": limit}
        )
        payload = self._fetch_json(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
        )
        return [
            {
                "id": str(identifier),
                "title": query,
                "url": f"https://www.ncbi.nlm.nih.gov/gene/{identifier}",
            }
            for identifier in payload.get("esearchresult", {}).get("idlist", [])[:limit]
        ]


class GWASCatalogConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"efo_trait": query, "page_size": limit})
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/gwas/rest/api/v2/efo-traits?{params}"
        )
        traits = payload.get("_embedded", {}).get("efo_traits", [])
        return [
            {
                "id": str(item.get("efo_id") or ""),
                "title": str(item.get("efo_trait") or item.get("efo_id") or ""),
                "ontology_uri": str(item.get("uri") or ""),
                "url": f"https://www.ebi.ac.uk/gwas/efotraits/{item.get('efo_id', '')}",
            }
            for item in traits[:limit]
            if item.get("efo_id")
        ]


class OpenTargetsConnector:
    def __init__(self, *, post_json: Callable[[str, dict[str, Any]], Any] = post_json) -> None:
        self._post_json = post_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        graphql = """
        query Search($queryString: String!, $page: Pagination) {
          search(queryString: $queryString, page: $page) {
            hits { id name entity description }
          }
        }
        """
        payload = self._post_json(
            "https://api.platform.opentargets.org/api/v4/graphql",
            {"query": graphql, "variables": {"queryString": query, "page": {"index": 0, "size": limit}}},
        )
        hits = payload.get("data", {}).get("search", {}).get("hits", [])
        return [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("name") or item.get("id") or ""),
                "entity": str(item.get("entity") or ""),
                "description": str(item.get("description") or ""),
                "url": f"https://platform.opentargets.org/{item.get('entity', 'target')}/{item.get('id', '')}",
            }
            for item in hits[:limit]
            if item.get("id")
        ]


class GTExConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"geneId": query, "pageSize": limit})
        payload = self._fetch_json(f"https://gtexportal.org/api/v2/reference/gene?{params}")
        return [
            {
                "id": str(item.get("gencodeId") or ""),
                "title": str(item.get("geneSymbol") or item.get("gencodeId") or ""),
                "description": str(item.get("description") or ""),
                "genome_build": str(item.get("genomeBuild") or ""),
                "url": f"https://gtexportal.org/home/gene/{item.get('gencodeId', '')}",
            }
            for item in payload.get("data", [])[:limit]
            if item.get("gencodeId")
        ]


class HumanProteinAtlasConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        encoded = urllib.parse.quote(query, safe="")
        payload = self._fetch_json(f"https://www.proteinatlas.org/search/{encoded}?format=json")
        return [
            {
                "id": str(item.get("Ensembl") or item.get("Gene") or ""),
                "title": str(item.get("Gene") or item.get("Ensembl") or ""),
                "description": str(item.get("Gene description") or ""),
                "url": f"https://www.proteinatlas.org/{item.get('Ensembl', '')}",
            }
            for item in payload[:limit]
            if item.get("Ensembl") or item.get("Gene")
        ]


class BgeeConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"page": "gene", "action": "search", "query": query, "species_id": 9606}
        )
        payload = self._fetch_json(f"https://www.bgee.org/api/?{params}")
        matches = payload.get("data", {}).get("result", {}).get("geneMatches", [])
        results: list[dict[str, str]] = []
        for match in matches[:limit]:
            item = match.get("gene", {})
            identifier = str(item.get("geneId") or "")
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("name") or identifier),
                        "description": str(item.get("description") or ""),
                        "url": f"https://www.bgee.org/gene/{identifier}",
                    }
                )
        return results


class BioStudiesConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "pageSize": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/biostudies/api/v1/search?{params}")
        return [
            {
                "id": str(item.get("accession") or ""),
                "title": str(item.get("title") or item.get("accession") or ""),
                "type": str(item.get("type") or ""),
                "release_date": str(item.get("release_date") or ""),
                "url": f"https://www.ebi.ac.uk/biostudies/studies/{item.get('accession', '')}",
            }
            for item in payload.get("hits", [])[:limit]
            if item.get("accession")
        ]


class CBioPortalConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"keyword": query, "pageSize": limit})
        payload = self._fetch_json(f"https://www.cbioportal.org/api/genes?{params}")
        return [
            {
                "id": str(item.get("entrezGeneId") or ""),
                "title": str(item.get("hugoGeneSymbol") or item.get("entrezGeneId") or ""),
                "type": str(item.get("type") or ""),
                "url": f"https://www.cbioportal.org/results/oncoprint?gene_list={item.get('hugoGeneSymbol', '')}",
            }
            for item in payload[:limit]
            if item.get("entrezGeneId")
        ]


class ChEBIConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"term": query, "size": limit})
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/chebi/backend/api/public/es_search/?{params}"
        )
        results: list[dict[str, str]] = []
        for hit in payload.get("results", [])[:limit]:
            item = hit.get("_source", hit)
            identifier = str(item.get("chebi_accession") or "")
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("name") or identifier),
                        "formula": str(item.get("formula") or ""),
                        "smiles": str(item.get("smiles") or ""),
                        "url": f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={identifier}",
                    }
                )
        return results


class RheaConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "format": "json", "limit": limit})
        payload = self._fetch_json(f"https://www.rhea-db.org/rhea/?{params}")
        return [
            {
                "id": str(item.get("id") or ""),
                "title": _plain_text(item.get("equation")),
                "status": str(item.get("status") or ""),
                "url": f"https://www.rhea-db.org/rhea/{item.get('id', '')}",
            }
            for item in payload.get("results", [])[:limit]
            if item.get("id")
        ]


class PRIDEConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"keyword": query, "pageSize": limit})
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/pride/ws/archive/v3/search/projects?{params}"
        )
        items = payload if isinstance(payload, list) else payload.get("_embedded", {}).get("projects", [])
        return [
            {
                "id": str(item.get("accession") or ""),
                "title": str(item.get("title") or item.get("accession") or ""),
                "publication_date": str(item.get("publicationDate") or ""),
                "url": f"https://www.ebi.ac.uk/pride/archive/projects/{item.get('accession', '')}",
            }
            for item in items[:limit]
            if item.get("accession")
        ]


class ProteomeXchangeConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, _ = _validate(query, limit)
        accession = query.upper()
        if re.fullmatch(r"PXD\d{6,}", accession) is None:
            raise ValueError("ProteomeXchange query must be a PXD accession")
        payload = self._fetch_json(
            "https://proteomecentral.proteomexchange.org/api/proxi/v0.1/datasets/"
            f"{urllib.parse.quote(accession)}"
        )
        if not isinstance(payload, dict):
            return []

        identifiers = payload.get("identifiers", [])
        returned_accessions = {
            str(term.get("value") or "").upper()
            for term in identifiers
            if isinstance(term, dict)
            and term.get("name") == "ProteomeXchange accession number"
        }
        if accession not in returned_accessions:
            raise ValueError("ProteomeXchange response accession did not match query")

        species = []
        for group in payload.get("species", []):
            for term in group.get("terms", []) if isinstance(group, dict) else []:
                if term.get("name") == "taxonomy: scientific name" and term.get("value"):
                    species.append(str(term["value"]))
        return [
            {
                "id": accession,
                "title": str(payload.get("title") or accession),
                "repository": "ProteomeXchange",
                "species": "; ".join(species),
                "url": f"https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID={accession}",
            }
        ]


class MGnifyConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query, "page_size": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/metagenomics/api/v1/studies?{params}")
        results: list[dict[str, str]] = []
        for item in payload.get("data", [])[:limit]:
            attributes = item.get("attributes", {})
            identifier = str(item.get("id") or attributes.get("accession") or "")
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(attributes.get("study-name") or identifier),
                        "bioproject": str(attributes.get("bioproject") or ""),
                        "url": f"https://www.ebi.ac.uk/metagenomics/studies/{identifier}",
                    }
                )
        return results


class RNACentralConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"description": query, "page_size": limit})
        payload = self._fetch_json(f"https://rnacentral.org/api/v1/rna/?{params}")
        return [
            {
                "id": str(item.get("rnacentral_id") or ""),
                "title": str(item.get("description") or item.get("rnacentral_id") or ""),
                "rna_type": str(item.get("rna_type") or ""),
                "length": str(item.get("length") or ""),
                "url": f"https://rnacentral.org/rna/{item.get('rnacentral_id', '')}",
            }
            for item in payload.get("results", [])[:limit]
            if item.get("rnacentral_id")
        ]


VARIANT_RE = re.compile(r"^(?:chr)?([0-9XYM]+):(\d+)[-:]([ACGT]+)[-:]([ACGT]+)$", re.IGNORECASE)


class _PheWASConnector:
    base_url = ""
    result_key = "phenos"

    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def _response_variant(self, payload: dict[str, Any]) -> tuple[str, str, str, str] | None:
        try:
            raw_position = payload["pos"]
            if isinstance(raw_position, bool):
                return None
            if isinstance(raw_position, int):
                position = str(raw_position)
            elif isinstance(raw_position, str) and raw_position.isdigit():
                position = str(int(raw_position))
            else:
                return None
            return (
                str(payload["chrom"]).upper().removeprefix("CHR"),
                position,
                str(payload["ref"]).upper(),
                str(payload["alt"]).upper(),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        match = VARIANT_RE.fullmatch(query)
        if match is None:
            raise ValueError("Variant must use CHR:POS-REF-ALT on the source's declared genome build")
        chromosome = match.group(1).upper()
        position = str(int(match.group(2)))
        reference = match.group(3).upper()
        alternate = match.group(4).upper()
        canonical = f"{chromosome}:{position}-{reference}-{alternate}"
        payload = self._fetch_json(
            f"{self.base_url}/api/variant/{urllib.parse.quote(canonical, safe=':-')}"
        )
        if not isinstance(payload, dict):
            return []
        expected = (chromosome, position, reference, alternate)
        if self._response_variant(payload) != expected:
            raise ValueError("PheWAS response variant did not match normalized query")
        associations = payload.get(self.result_key, [])

        def p_value(item: dict[str, Any]) -> float | None:
            try:
                if isinstance(item["pval"], bool):
                    return None
                value = float(item["pval"])
            except (KeyError, TypeError, ValueError):
                return None
            return value if math.isfinite(value) and 0 <= value <= 1 else None

        results = []
        ranked = [
            (value, item)
            for item in associations
            if isinstance(item, dict) and (value := p_value(item)) is not None
        ]
        for _, item in sorted(ranked, key=lambda pair: pair[0])[:limit]:
            identifier = str(item.get("phenocode") or item.get("trait") or "")
            if identifier:
                results.append(
                    {
                        "id": identifier,
                        "title": str(item.get("phenostring") or item.get("trait") or identifier),
                        "p_value": _value_text(item.get("pval")),
                        "beta": _value_text(item.get("beta")),
                        "sample_size": _value_text(item.get("num_samples")),
                        "variant": canonical,
                        "url": f"{self.base_url}/variant/{canonical}",
                    }
                )
        return results


class FinnGenConnector(_PheWASConnector):
    base_url = "https://r12.finngen.fi"
    result_key = "results"

    def _response_variant(self, payload: dict[str, Any]) -> tuple[str, str, str, str] | None:
        variant = payload.get("variant")
        if not isinstance(variant, dict):
            return None
        normalized = dict(variant)
        normalized["chrom"] = normalized.get("chr")
        return super()._response_variant(normalized)


class BioBankJapanConnector(_PheWASConnector):
    base_url = "https://pheweb.jp"


class UKBTopMedConnector(_PheWASConnector):
    base_url = "https://pheweb.org/UKB-TOPMed"
