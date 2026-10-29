"""Conservative public-source adapters used by Connector Contract v2."""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from codex_science.connectors import fetch_json, post_json, parse_esearch_ids

VARIANT_RE = re.compile(r"^(?:chr)?([0-9XYM]+)[:\-](\d+)[:\-]([ACGT]+)[:\-]([ACGT]+)$", re.I)
UNIPROT_RE = re.compile(r"^[A-NR-Z][0-9][A-Z0-9]{3}[0-9](?:-\d+)?$", re.I)


def _validate(query: str, limit: int) -> tuple[str, int]:
    query = query.strip()
    if not query or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    if isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    return query, limit


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("response identifier must be a non-empty string")
    return value


def _record_id(item: Any, *fields: str) -> str:
    if not isinstance(item, dict):
        raise ValueError("response record must be an object")
    for field in fields:
        if field in item and item[field] is not None:
            return _identifier(item[field])
    return ""


def _response_items(payload: Any, fields: tuple[str, ...], *, allow_list: bool = False) -> list[Any]:
    if isinstance(payload, dict):
        if payload.get("error") or payload.get("errors"):
            raise ValueError("source response contains an error")
        for field in fields:
            if field in payload:
                if isinstance(payload[field], list):
                    return payload[field]
                raise ValueError(f"response {field} must be a list")
    elif allow_list and isinstance(payload, list):
        return payload
    raise ValueError(f"response must contain a result list: {', '.join(fields)}")


class NCBIESearchConnector:
    database = ""
    record_url = ""
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"db": self.database, "term": query, "retmode": "json", "retmax": limit})
        payload = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
        parse_esearch_ids(payload)
        ids = [_identifier(value) for value in payload["esearchresult"]["idlist"][:limit]]
        return [{"id": str(identifier), "title": query, "database": self.database, "url": self.record_url.format(id=identifier)} for identifier in ids[:limit]]

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
        if not isinstance(payload, dict) or payload.get("error"):
            raise ValueError("gnomAD response must contain data.variant")
        if payload.get("errors"):
            raise ValueError("gnomAD GraphQL response contains errors")
        data = payload.get("data")
        if not isinstance(data, dict) or "variant" not in data:
            raise ValueError("gnomAD response must contain data.variant")
        item = data["variant"]
        if item is None:
            return []
        if not isinstance(item, dict):
            raise ValueError("gnomAD response variant must be an object or null")
        exome, genome = item.get("exome") or {}, item.get("genome") or {}
        return [{"id": _record_id(item, "variant_id") or variant_id, "title": variant_id, "assembly": "GRCh38", "exome_af": str(exome["af"]) if exome.get("af") is not None else "", "genome_af": str(genome["af"]) if genome.get("af") is not None else "", "url": f"https://gnomad.broadinstitute.org/variant/{variant_id}?dataset=gnomad_r4"}]


class ENCODEConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"searchTerm": query, "format": "json", "limit": limit, "frame": "object"})
        payload = self._fetch_json(f"https://www.encodeproject.org/search/?{params}")
        return [{"id": _record_id(item, "accession", "@id"), "title": str(item.get("title") or item.get("description") or item.get("accession") or ""), "type": str((item.get("@type") or [""])[0] if isinstance(item.get("@type"), list) else item.get("@type") or ""), "url": f"https://www.encodeproject.org{item.get('@id', '')}"} for item in _response_items(payload, ("@graph",))[:limit] if _record_id(item, "accession", "@id")]


class JASPARConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://jaspar.elixir.no/api/v1/matrix/?{urllib.parse.urlencode({'search': query, 'page_size': limit})}")
        return [{"id": _record_id(item, "matrix_id"), "title": str(item.get("name") or item.get("matrix_id") or ""), "collection": str(item.get("collection") or ""), "url": f"https://jaspar.elixir.no/matrix/{item.get('matrix_id', '')}"} for item in _response_items(payload, ("results",))[:limit] if _record_id(item, "matrix_id")]


class UniBindConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://unibind.uio.no/api/datasets?{urllib.parse.urlencode({'search': query, 'limit': limit})}")
        items = _response_items(payload, ("results",), allow_list=True)
        return [{"id": _record_id(item, "id", "dataset_id"), "title": str(item.get("tf_name") or item.get("name") or item.get("id") or ""), "species": str(item.get("species") or ""), "url": str(item.get("url") or "https://unibind.uio.no/")} for item in items[:limit] if _record_id(item, "id", "dataset_id")]


class ArrayExpressConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": f"{query} AND collection:arrayexpress", "pageSize": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/biostudies/api/v1/search?{params}")
        return [{"id": _record_id(item, "accession"), "title": str(item.get("title") or item.get("accession") or ""), "repository": "ArrayExpress/BioStudies", "release_date": str(item.get("release_date") or ""), "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{item.get('accession', '')}"} for item in _response_items(payload, ("hits",))[:limit] if _record_id(item, "accession")]


class MetaboLightsConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://www.ebi.ac.uk/metabolights/ws/studies?{urllib.parse.urlencode({'search': query})}")
        items = _response_items(payload, ("content", "studies"))
        return [{"id": _record_id(item, "studyIdentifier", "accession"), "title": str(item.get("title") or item.get("studyIdentifier") or ""), "release_date": str(item.get("releaseDate") or ""), "url": f"https://www.ebi.ac.uk/metabolights/{item.get('studyIdentifier') or item.get('accession') or ''}"} for item in items[:limit] if _record_id(item, "studyIdentifier", "accession")]


class OpenFDAConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        expression = f'openfda.generic_name:"{query}"+openfda.brand_name:"{query}"'
        payload = self._fetch_json(f"https://api.fda.gov/drug/label.json?{urllib.parse.urlencode({'search': expression, 'limit': limit})}")
        results = []
        for item in _response_items(payload, ("results",))[:limit]:
            if not isinstance(item, dict):
                raise ValueError("response record must be an object")
            openfda = item.get("openfda") or {}
            if not isinstance(openfda, dict):
                raise ValueError("response openfda must be an object")
            ids = _response_items(openfda, ("spl_id", "application_number")) if any(
                key in openfda for key in ("spl_id", "application_number")
            ) else []
            if not ids and "application_number" in openfda:
                ids = _response_items(openfda, ("application_number",))
            identifier = _identifier(ids[0]) if ids else _record_id(item, "id")
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
        items = _response_items(payload, ("affinities", "ligands"))
        return [{"id": _record_id(item, "monomerid", "ligand_id"), "title": str(item.get("ligand_name") or item.get("smiles") or item.get("monomerid") or ""), "affinity_type": str(item.get("affinity_type") or item.get("type") or ""), "affinity": str(item.get("affinity") or item.get("value") or ""), "url": "https://bindingdb.org/"} for item in items[:limit] if _record_id(item, "monomerid", "ligand_id")]


class SimpleSearchConnector:
    endpoint = ""
    result_keys: tuple[str, ...] = ("results", "entries", "data")
    id_keys: tuple[str, ...] = ("id", "accession")
    title_keys: tuple[str, ...] = ("title", "name", "label")
    home = ""
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def _validate_response(self, payload: Any) -> None:
        _response_items(payload, self.result_keys, allow_list=True)

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(self.endpoint.format(query=urllib.parse.quote(query, safe=""), limit=limit))
        if isinstance(payload, dict) and (payload.get("error") or payload.get("errors")):
            raise ValueError("source response contains an error")
        items: Any = payload
        if isinstance(payload, dict):
            for key in self.result_keys:
                if isinstance(payload.get(key), list):
                    items = payload[key]
                    break
        if not isinstance(items, list):
            # Preserve the legacy direct-search fallback; receipts validate the envelope.
            return []
        results = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            identifier = _record_id(item, *self.id_keys)
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
