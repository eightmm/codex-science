"""Conservative public-source adapters used by Connector Contract v2."""
from __future__ import annotations

import json
import math
import re
import urllib.parse
from pathlib import Path
from typing import Any, Callable

from codex_science.connectors import fetch_json, post_json, parse_esearch_ids
from codex_science.connectors import _graphql_data, _received_records

VARIANT_RE = re.compile(r"^(?:chr)?([0-9XYM]+)[:\-](\d+)[:\-]([ACGT]+)[:\-]([ACGT]+)$", re.I)
GNOMAD_VARIANT_RE = re.compile(r"^(?:chr)?(1[0-9]|2[0-2]|[1-9]|X|Y|MT?)[:\-]([1-9][0-9]*)[:\-]([ACGT]+)[:\-]([ACGT]+)$", re.I)
GNOMAD_ECHO_RE = re.compile(r"^(?:chr)?([0-9XY]+|MT?)[:\-](\d+)[:\-]([ACGT]+)[:\-]([ACGT]+)$", re.I)
UNIPROT_RE = re.compile(r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})(?:-\d+)?$", re.I)


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
    return value.strip()


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _allele_frequency(value: Any, field: str) -> str:
    if value is None or value == "":
        return ""
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"gnomAD upstream error: {field} allele frequency must be a finite number")
    if not 0 <= value <= 1:
        raise ValueError(f"gnomAD upstream error: {field} allele frequency must be between 0 and 1")
    return str(value)


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


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list) and all(isinstance(member, str) for member in value):
        return value
    raise ValueError("response openfda names and product types must be strings or lists of strings")


class NCBIESearchConnector:
    database = ""
    record_url = ""
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"db": self.database, "term": query, "retmode": "json", "retmax": limit})
        payload = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
        ids = [_identifier(value) for value in _received_records(parse_esearch_ids(payload))[:limit]]
        return [{"id": identifier, "title": "", "database": self.database, "url": self.record_url.format(id=_quote(identifier))} for identifier in _received_records(ids)[:limit]]

class ClinVarConnector(NCBIESearchConnector):
    database = "clinvar"
    record_url = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{id}/"

class DBSNPConnector(NCBIESearchConnector):
    database = "snp"
    record_url = "https://www.ncbi.nlm.nih.gov/snp/{id}"

class GEOConnector(NCBIESearchConnector):
    database = "gds"
    record_url = "https://www.ncbi.nlm.nih.gov/gds/{id}"

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        records = super().search(query, limit=limit)
        for record in records:
            if re.fullmatch(r"G(?:SE|DS|PL|SM)[0-9]+", record["id"], re.I):
                record["url"] = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={_quote(record['id'])}"
        return records


class GnomADConnector:
    def __init__(self, *, post_json: Callable[[str, dict[str, Any]], Any] = post_json) -> None:
        self._post_json = post_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, _ = _validate(query, limit)
        match = GNOMAD_VARIANT_RE.fullmatch(query)
        if match is None or match[3].upper() == match[4].upper():
            raise ValueError("gnomAD query must be chr-pos-ref-alt on GRCh38")
        chromosome, position, reference, alternate = match.groups()
        chromosome = chromosome.upper()
        variant_id = f"{chromosome}-{position}-{reference.upper()}-{alternate.upper()}"
        graphql = "query Variant($variantId: String!, $datasetId: DatasetId!) { variant(variantId: $variantId, dataset: $datasetId) { variant_id chrom pos ref alt exome { ac an af } genome { ac an af } } }"
        payload = self._post_json("https://gnomad.broadinstitute.org/api", {"query": graphql, "variables": {"variantId": variant_id, "datasetId": "gnomad_r4"}})
        data = _graphql_data(payload, "gnomAD")
        if "variant" not in data:
            raise ValueError("gnomAD upstream error: response must contain data.variant")
        item = data["variant"]
        if item is None:
            return []
        if not isinstance(item, dict):
            raise ValueError("gnomAD upstream error: response variant must be an object or null")
        returned_id = _record_id(item, "variant_id")
        if returned_id:
            returned = GNOMAD_ECHO_RE.fullmatch(returned_id)
            expected = ("M" if chromosome == "MT" else chromosome, int(position), reference.upper(), alternate.upper())
            if returned is None or ("M" if returned[1].upper() == "MT" else returned[1].upper(), int(returned[2]), returned[3].upper(), returned[4].upper()) != expected:
                raise ValueError("gnomAD identity mismatch: response variant_id did not match normalized query")
        else:
            returned_chromosome = item.get("chrom")
            returned_position = item.get("pos")
            returned_reference = item.get("ref")
            returned_alternate = item.get("alt")
            returned_chromosome = re.sub(r"^chr", "", returned_chromosome, flags=re.I).upper() if isinstance(returned_chromosome, str) else None
            # gnomAD reports the mitochondrial chromosome as M; MT is the same chromosome, as in the variant_id check.
            if (returned_chromosome is None
                    or ("M" if returned_chromosome == "MT" else returned_chromosome) != ("M" if chromosome == "MT" else chromosome)
                    or isinstance(returned_position, bool) or not isinstance(returned_position, (int, str))
                    or str(returned_position) != position
                    or not isinstance(returned_reference, str) or returned_reference.upper() != reference.upper()
                    or not isinstance(returned_alternate, str) or returned_alternate.upper() != alternate.upper()):
                raise ValueError("gnomAD identity mismatch: response coordinates missing or did not match normalized query")
        exome, genome = item.get("exome"), item.get("genome")
        if not isinstance(exome, (dict, type(None))) or not isinstance(genome, (dict, type(None))):
            raise ValueError("gnomAD upstream error: response exome and genome must be objects or null")
        exome, genome = exome or {}, genome or {}
        return [{"id": _record_id(item, "variant_id") or variant_id, "title": variant_id, "assembly": "GRCh38", "exome_af": _allele_frequency(exome.get("af"), "exome.af"), "genome_af": _allele_frequency(genome.get("af"), "genome.af"), "url": f"https://gnomad.broadinstitute.org/variant/{variant_id}?dataset=gnomad_r4"}]


def _encode_url(item: dict[str, Any]) -> str:
    path = item.get("@id")
    if isinstance(path, str) and path.startswith("/") and not path.startswith("//") and "\\" not in path and path.isprintable() and " " not in path:
        return f"https://www.encodeproject.org{path}"
    return f"https://www.encodeproject.org/{_quote(_record_id(item, 'accession', '@id'))}/"


class ENCODEConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"searchTerm": query, "format": "json", "limit": limit, "frame": "object"})
        payload = self._fetch_json(f"https://www.encodeproject.org/search/?{params}")
        return [{"id": _record_id(item, "accession", "@id"), "title": str(item.get("title") or item.get("description") or item.get("accession") or ""), "type": str((item.get("@type") or [""])[0] if isinstance(item.get("@type"), list) else item.get("@type") or ""), "url": _encode_url(item)} for item in _received_records(_response_items(payload, ("@graph",)))[:limit] if _record_id(item, "accession", "@id")]


class JASPARConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://jaspar.elixir.no/api/v1/matrix/?{urllib.parse.urlencode({'search': query, 'page_size': limit})}")
        return [{"id": _record_id(item, "matrix_id"), "title": str(item.get("name") or item.get("matrix_id") or ""), "collection": str(item.get("collection") or ""), "url": f"https://jaspar.elixir.no/matrix/{_quote(_record_id(item, 'matrix_id'))}"} for item in _received_records(_response_items(payload, ("results",)))[:limit] if _record_id(item, "matrix_id")]


def _unibind_url(value: Any) -> str:
    if isinstance(value, str) and value.startswith("https://unibind.uio.no/"):
        return value
    return "https://unibind.uio.no/"


class UniBindConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = self._fetch_json(f"https://unibind.uio.no/api/datasets?{urllib.parse.urlencode({'search': query, 'limit': limit})}")
        items = _response_items(payload, ("results",), allow_list=True)
        return [{"id": _record_id(item, "id", "dataset_id"), "title": str(item.get("tf_name") or item.get("name") or item.get("id") or ""), "species": str(item.get("species") or ""), "url": _unibind_url(item.get("url"))} for item in _received_records(items)[:limit] if _record_id(item, "id", "dataset_id")]


class ArrayExpressConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": f"{query} AND collection:arrayexpress", "pageSize": limit})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/biostudies/api/v1/search?{params}")
        return [{"id": _record_id(item, "accession"), "title": str(item.get("title") or item.get("accession") or ""), "repository": "ArrayExpress/BioStudies", "release_date": str(item.get("release_date") or ""), "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{_quote(_record_id(item, 'accession'))}"} for item in _received_records(_response_items(payload, ("hits",)))[:limit] if _record_id(item, "accession")]


METABOLIGHTS_ID_RE = re.compile(r"^MTBLS[0-9]+$")


def _metabolights_record(entry: Any) -> dict[str, str] | None:
    identifier = _record_id(entry, "id")
    if not METABOLIGHTS_ID_RE.fullmatch(identifier):
        return None
    fields = entry.get("fields")
    names = fields.get("name") if isinstance(fields, dict) else None
    first = next((name for name in (names if isinstance(names, list) else [names]) if isinstance(name, str) and name.strip()), "")
    return {"id": identifier, "title": first.strip() or identifier, "release_date": "", "url": f"https://www.ebi.ac.uk/metabolights/{_quote(identifier)}"}


class MetaboLightsConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "format": "json", "size": limit, "fields": "name"})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/ebisearch/ws/rest/metabolights?{params}")
        if not isinstance(payload, dict):
            raise ValueError("response must contain a result list: entries")
        records = (_metabolights_record(entry) for entry in _received_records(_response_items(payload, ("entries",)))[:limit])
        return [record for record in records if record]


class OpenFDAConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        if '"' in query or "\\" in query:
            raise ValueError("OpenFDA query must not contain double quotes or backslashes")
        expression = f'openfda.generic_name:"{query}"+openfda.brand_name:"{query}"'
        payload = self._fetch_json(f"https://api.fda.gov/drug/label.json?{urllib.parse.urlencode({'search': expression, 'limit': limit})}")
        results = []
        for item in _received_records(_response_items(payload, ("results",)))[:limit]:
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
                names = _text_list(openfda.get("brand_name")) or _text_list(openfda.get("generic_name"))
                product_types = _text_list(openfda.get("product_type")) or [""]
                results.append({"id": identifier, "title": str(names[0] if names else identifier), "product_type": str(product_types[0]), "url": "https://open.fda.gov/apis/drug/label/"})
        return results


class BindingDBConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None: self._fetch_json = fetch_json
    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        if UNIPROT_RE.fullmatch(query) is None:
            raise ValueError("BindingDB query must be a UniProt accession")
        payload = self._fetch_json(f"https://bindingdb.org/axis2/services/BDBService/getLigandsByUniprot?{urllib.parse.urlencode({'uniprot': query, 'response': 'application/json'})}")
        items = _response_items(payload, ("affinities", "ligands"))
        return [{"id": _record_id(item, "monomerid", "ligand_id"), "title": str(item.get("ligand_name") or item.get("smiles") or item.get("monomerid") or ""), "affinity_type": str(item.get("affinity_type") or item.get("type") or ""), "affinity": str(item.get("affinity") or item.get("value") or ""), "url": "https://bindingdb.org/"} for item in _received_records(items)[:limit] if _record_id(item, "monomerid", "ligand_id")]


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
        items = _response_items(payload, self.result_keys, allow_list=True)
        results = []
        for item in _received_records(items)[:limit]:
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
        if not isinstance(payload, dict):
            raise ValueError("release snapshot must be an object")
        releases = payload.get("releases", [])
        if not isinstance(releases, list) or any(not isinstance(item, dict) for item in releases):
            raise ValueError("snapshot releases must be a list of objects")
        needle = query.lower()

        def matches(value: Any) -> bool:
            if isinstance(value, str):
                return needle in value.lower()
            if isinstance(value, dict):
                return any(matches(child) for child in value.values())
            if isinstance(value, list):
                return any(matches(child) for child in value)
            return False

        return _received_records([dict(item) for item in releases if matches(item)])[:limit]
