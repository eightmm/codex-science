"""Conservative public-source adapters used by Connector Contract v2."""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from codex_science.connectors import fetch_json, post_json

VARIANT_RE = re.compile(r"^(?:chr)?([0-9XYM]+)[:\-](\d+)[:\-]([ACGT]+)[:\-]([ACGT]+)$", re.I)
UNIPROT_RE = re.compile(r"^[A-NR-Z][0-9][A-Z0-9]{3}[0-9](?:-\d+)?$", re.I)


def _validate(query: str, limit: int) -> tuple[str, int]:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    if isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    return query, limit


class NCBIESearchConnector:
    database = ""
    record_url = ""
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"db": self.database, "term": query, "retmode": "json", "retmax": limit})
        payload = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
        return [{"id": str(identifier), "title": query, "database": self.database, "url": self.record_url.format(id=identifier)} for identifier in payload.get("esearchresult", {}).get("idlist", [])[:limit]]

class ClinVarConnector(NCBIESearchConnector):
    database = "clinvar"
    record_url = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{id}/"

class DBSNPConnector(NCBIESearchConnector):
    database = "snp"
    record_url = "https://www.ncbi.nlm.nih.gov/snp/{id}"

class GEOConnector(NCBIESearchConnector):
    database = "gds"
    record_url = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={id}"


class GnomADConnector:
    def __init__(self, *, post_json: Callable[[str, dict[str, Any]], Any] = post_json) -> None:
        self._post_json = post_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, _ = _validate(query, limit)
        match = VARIANT_RE.fullmatch(query)
        if match is None:
            raise ValueError("gnomAD query must be chr-pos-ref-alt on GRCh38")
        chromosome, position, reference, alternate = match.groups()
        variant_id = f"{chromosome.upper()}-{position}-{reference.upper()}-{alternate.upper()}"
        graphql = "query Variant($variantId: String!, $datasetId: DatasetId!) { variant(variantId: $variantId, dataset: $datasetId) { variant_id chrom pos ref alt exome { ac an af } genome { ac an af } } }"
        payload = self._post_json("https://gnomad.broadinstitute.org/api", {"query": graphql, "variables": {"variantId": variant_id, "datasetId": "gnomad_r4"}})
        item = payload.get("data", {}).get("variant")
        if not isinstance(item, dict):
            return []
        exome, genome = item.get("exome") or {}, item.get("genome") or {}
        return [{"id": str(item.get("variant_id") or variant_id), "title": variant_id, "assembly": "GRCh38", "exome_af": str(exome.get("af") or ""), "genome_af": str(genome.get("af") or ""), "url": f"https://gnomad.broadinstitute.org/variant/{variant_id}?dataset=gnomad_r4"}]


class ENCODEConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"searchTerm": query, "format": "json", "limit": limit, "frame": "object"})
        payload = self._fetch_json(f"https://www.encodeproject.org/search/?{params}")
        return [{"id": str(item.get("accession") or item.get("@id") or ""), "title": str(item.get("title") or item.get("description") or item.get("accession") or ""), "type": str((item.get("@type") or [""])[0] if isinstance(item.get("@type"), list) else item.get("@type") or ""), "url": f"https://www.encodeproject.org{item.get('@id', '')}"} for item in payload.get("@graph", [])[:limit] if item.get("accession") or item.get("@id")]


class JASPARConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://jaspar.elixir.no/api/v1/matrix/?{urllib.parse.urlencode({'search': query, 'page_size': limit})}")
        return [{"id": str(item.get("matrix_id") or ""), "title": str(item.get("name") or item.get("matrix_id") or ""), "collection": str(item.get("collection") or ""), "url": f"https://jaspar.elixir.no/matrix/{item.get('matrix_id', '')}"} for item in payload.get("results", [])[:limit] if item.get("matrix_id")]


class UniBindConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://unibind.uio.no/api/datasets?{urllib.parse.urlencode({'search': query, 'limit': limit})}")
        items = payload if isinstance(payload, list) else payload.get("results", [])
        return [{"id": str(item.get("id") or item.get("dataset_id") or ""), "title": str(item.get("tf_name") or item.get("name") or item.get("id") or ""), "species": str(item.get("species") or ""), "url": str(item.get("url") or "https://unibind.uio.no/")} for item in items[:limit] if item.get("id") or item.get("dataset_id")]


class ArrayExpressConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": f"{query} AND collection:arrayexpress", "pageSize": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/biostudies/api/v1/search?{params}")
        return [{"id": str(item.get("accession") or ""), "title": str(item.get("title") or item.get("accession") or ""), "repository": "ArrayExpress/BioStudies", "release_date": str(item.get("release_date") or ""), "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{item.get('accession', '')}"} for item in payload.get("hits", [])[:limit] if item.get("accession")]


class MetaboLightsConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://www.ebi.ac.uk/metabolights/ws/studies?{urllib.parse.urlencode({'search': query})}")
        items = payload.get("content", payload.get("studies", [])) if isinstance(payload, dict) else []
        return [{"id": str(item.get("studyIdentifier") or item.get("accession") or ""), "title": str(item.get("title") or item.get("studyIdentifier") or ""), "release_date": str(item.get("releaseDate") or ""), "url": f"https://www.ebi.ac.uk/metabolights/{item.get('studyIdentifier') or item.get('accession') or ''}"} for item in items[:limit] if item.get("studyIdentifier") or item.get("accession")]


class OpenFDAConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        expression = f'openfda.generic_name:"{query}"+openfda.brand_name:"{query}"'
        payload = self._fetch_json(f"https://api.fda.gov/drug/label.json?{urllib.parse.urlencode({'search': expression, 'limit': limit})}")
        results = []
        for item in payload.get("results", [])[:limit]:
            openfda = item.get("openfda") or {}
            ids = openfda.get("spl_id") or openfda.get("application_number") or []
            identifier = str(ids[0]) if ids else str(item.get("id") or "")
            if identifier:
                names = openfda.get("brand_name") or openfda.get("generic_name") or []
                results.append({"id": identifier, "title": str(names[0] if names else identifier), "product_type": str((openfda.get("product_type") or [""])[0]), "url": "https://open.fda.gov/apis/drug/label/"})
        return results


class BindingDBConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        if UNIPROT_RE.fullmatch(query) is None:
            raise ValueError("BindingDB query must be a UniProt accession")
        payload = self._fetch_json(f"https://bindingdb.org/axis2/services/BDBService/getLigandsByUniprot?{urllib.parse.urlencode({'uniprot': query, 'response': 'application/json'})}")
        items = payload.get("affinities", payload.get("ligands", [])) if isinstance(payload, dict) else []
        return [{"id": str(item.get("monomerid") or item.get("ligand_id") or ""), "title": str(item.get("ligand_name") or item.get("smiles") or item.get("monomerid") or ""), "affinity_type": str(item.get("affinity_type") or item.get("type") or ""), "affinity": str(item.get("affinity") or item.get("value") or ""), "url": "https://bindingdb.org/"} for item in items[:limit] if item.get("monomerid") or item.get("ligand_id")]


class SimpleSearchConnector:
    endpoint = ""
    result_keys: tuple[str, ...] = ("results", "entries", "data")
    id_keys: tuple[str, ...] = ("id", "accession")
    title_keys: tuple[str, ...] = ("title", "name", "label")
    home = ""
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(self.endpoint.format(query=urllib.parse.quote(query, safe=""), limit=limit))
        items: Any = payload
        if isinstance(payload, dict):
            for key in self.result_keys:
                if isinstance(payload.get(key), list):
                    items = payload[key]
                    break
        if not isinstance(items, list):
            return []
        results = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            identifier = next((str(item[key]) for key in self.id_keys if item.get(key) not in (None, "")), "")
            if not identifier:
                continue
            title = next((str(item[key]) for key in self.title_keys if item.get(key) not in (None, "")), identifier)
            results.append({"id": identifier, "title": title, "url": self.home})
        return results

class EMDBConnector(SimpleSearchConnector):
    endpoint = "https://www.ebi.ac.uk/emdb/api/search/{query}?rows={limit}"
    id_keys = ("emdb_id", "accession", "id")
    home = "https://www.ebi.ac.uk/emdb/"

class ComplexPortalConnector(SimpleSearchConnector):
    endpoint = "https://www.ebi.ac.uk/intact/complex-ws/search/{query}?page=0&pageSize={limit}"
    result_keys = ("elements", "results", "data")
    id_keys = ("complexAc", "accession", "id")
    title_keys = ("complexName", "name", "title")
    home = "https://www.ebi.ac.uk/complexportal/"

class IntActConnector(SimpleSearchConnector):
    endpoint = "https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/{query}?page=0&pageSize={limit}"
    result_keys = ("content", "results", "data")
    id_keys = ("interactionAc", "ac", "id")
    title_keys = ("description", "name", "title")
    home = "https://www.ebi.ac.uk/intact/"


class VersionedSnapshotConnector:
    def __init__(self, filename: str, *, root: Path | None = None) -> None:
        self.path = (root or Path(__file__).resolve().parents[2] / "connectors") / filename
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        needle = query.lower()
        return [dict(item) for item in payload.get("releases", []) if needle in json.dumps(item, ensure_ascii=False).lower()][:limit]
