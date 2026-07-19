"""Additional typed public-source connectors with conservative normalized records."""

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
    if not query:
        raise ValueError("Query must not be empty")
    if len(query) > 500:
        raise ValueError("Query must be at most 500 characters")
    if isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("Limit must be between 1 and 10")
    return query, limit


class _NCBIESearchConnector:
    database = ""
    record_url = ""

    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"db": self.database, "term": query, "retmode": "json", "retmax": limit}
        )
        payload = self._fetch_json(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
        )
        return [
            {
                "id": str(identifier),
                "title": query,
                "database": self.database,
                "url": self.record_url.format(id=identifier),
            }
            for identifier in payload.get("esearchresult", {}).get("idlist", [])[:limit]
        ]


class ClinVarConnector(_NCBIESearchConnector):
    database = "clinvar"
    record_url = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{id}/"


class DBSNPConnector(_NCBIESearchConnector):
    database = "snp"
    record_url = "https://www.ncbi.nlm.nih.gov/snp/{id}"


class GEOConnector(_NCBIESearchConnector):
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
        graphql = """
        query Variant($variantId: String!, $datasetId: DatasetId!) {
          variant(variantId: $variantId, dataset: $datasetId) {
            variant_id chrom pos ref alt exome { ac an af } genome { ac an af }
          }
        }
        """
        payload = self._post_json(
            "https://gnomad.broadinstitute.org/api",
            {
                "query": graphql,
                "variables": {"variantId": variant_id, "datasetId": "gnomad_r4"},
            },
        )
        item = payload.get("data", {}).get("variant")
        if not isinstance(item, dict):
            return []
        exome = item.get("exome") or {}
        genome = item.get("genome") or {}
        return [
            {
                "id": str(item.get("variant_id") or variant_id),
                "title": variant_id,
                "assembly": "GRCh38",
                "exome_af": str(exome.get("af") or ""),
                "genome_af": str(genome.get("af") or ""),
                "url": f"https://gnomad.broadinstitute.org/variant/{variant_id}?dataset=gnomad_r4",
            }
        ]


class ENCODEConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"searchTerm": query, "format": "json", "limit": limit, "frame": "object"}
        )
        payload = self._fetch_json(f"https://www.encodeproject.org/search/?{params}")
        return [
            {
                "id": str(item.get("accession") or item.get("@id") or ""),
                "title": str(item.get("title") or item.get("description") or item.get("accession") or ""),
                "type": str((item.get("@type") or [""])[0] if isinstance(item.get("@type"), list) else item.get("@type") or ""),
                "url": f"https://www.encodeproject.org{item.get('@id', '')}",
            }
            for item in payload.get("@graph", [])[:limit]
            if item.get("accession") or item.get("@id")
        ]


class JASPARConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query, "page_size": limit})
        payload = self._fetch_json(f"https://jaspar.elixir.no/api/v1/matrix/?{params}")
        return [
            {
                "id": str(item.get("matrix_id") or ""),
                "title": str(item.get("name") or item.get("matrix_id") or ""),
                "collection": str(item.get("collection") or ""),
                "url": f"https://jaspar.elixir.no/matrix/{item.get('matrix_id', '')}",
            }
            for item in payload.get("results", [])[:limit]
            if item.get("matrix_id")
        ]


class UniBindConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query, "limit": limit})
        payload = self._fetch_json(f"https://unibind.uio.no/api/datasets?{params}")
        items = payload if isinstance(payload, list) else payload.get("results", [])
        return [
            {
                "id": str(item.get("id") or item.get("dataset_id") or ""),
                "title": str(item.get("tf_name") or item.get("name") or item.get("id") or ""),
                "species": str(item.get("species") or ""),
                "url": str(item.get("url") or "https://unibind.uio.no/"),
            }
            for item in items[:limit]
            if item.get("id") or item.get("dataset_id")
        ]


class ArrayExpressConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode(
            {"query": f"{query} AND collection:arrayexpress", "pageSize": limit}
        )
        payload = self._fetch_json(f"https://www.ebi.ac.uk/biostudies/api/v1/search?{params}")
        return [
            {
                "id": str(item.get("accession") or ""),
                "title": str(item.get("title") or item.get("accession") or ""),
                "repository": "ArrayExpress/BioStudies",
                "release_date": str(item.get("release_date") or ""),
                "url": f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{item.get('accession', '')}",
            }
            for item in payload.get("hits", [])[:limit]
            if item.get("accession")
        ]


class MetaboLightsConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"search": query})
        payload = self._fetch_json(f"https://www.ebi.ac.uk/metabolights/ws/studies?{params}")
        items = payload.get("content", payload.get("studies", [])) if isinstance(payload, dict) else []
        return [
            {
                "id": str(item.get("studyIdentifier") or item.get("accession") or ""),
                "title": str(item.get("title") or item.get("studyIdentifier") or ""),
                "release_date": str(item.get("releaseDate") or ""),
                "url": f"https://www.ebi.ac.uk/metabolights/{item.get('studyIdentifier') or item.get('accession') or ''}",
            }
            for item in items[:limit]
            if item.get("studyIdentifier") or item.get("accession")
        ]


class OpenFDAConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        expression = f'openfda.generic_name:"{query}"+openfda.brand_name:"{query}"'
        params = urllib.parse.urlencode({"search": expression, "limit": limit})
        payload = self._fetch_json(f"https://api.fda.gov/drug/label.json?{params}")
        results: list[dict[str, str]] = []
        for item in payload.get("results", [])[:limit]:
            openfda = item.get("openfda") or {}
            identifiers = openfda.get("spl_id") or openfda.get("application_number") or []
            identifier = str(identifiers[0]) if identifiers else str(item.get("id") or "")
            if not identifier:
                continue
            brands = openfda.get("brand_name") or openfda.get("generic_name") or []
            results.append(
                {
                    "id": identifier,
                    "title": str(brands[0] if brands else identifier),
                    "product_type": str((openfda.get("product_type") or [""])[0]),
                    "url": f"https://open.fda.gov/apis/drug/label/",
                }
            )
        return results


class BindingDBConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        if UNIPROT_RE.fullmatch(query) is None:
            raise ValueError("BindingDB search requires a UniProt accession")
        params = urllib.parse.urlencode({"uniprot": query, "response": "application/json"})
        payload = self._fetch_json(
            f"https://bindingdb.org/axis2/services/BDBService/getLigandsByUniprot?{params}"
        )
        items = payload.get("affinities", payload.get("ligands", [])) if isinstance(payload, dict) else []
        return [
            {
                "id": str(item.get("monomerid") or item.get("ligand_id") or ""),
                "title": str(item.get("ligand_name") or item.get("smiles") or item.get("monomerid") or ""),
                "affinity_type": str(item.get("affinity_type") or item.get("type") or ""),
                "affinity": str(item.get("affinity") or item.get("value") or ""),
                "url": "https://bindingdb.org/",
            }
            for item in items[:limit]
            if item.get("monomerid") or item.get("ligand_id")
        ]


class EMDBConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        encoded = urllib.parse.quote(query, safe="")
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/emdb/api/search/{encoded}?rows={limit}"
        )
        items = payload if isinstance(payload, list) else payload.get("results", payload.get("entries", []))
        return [
            {
                "id": str(item.get("emdb_id") or item.get("accession") or item.get("id") or ""),
                "title": str(item.get("title") or item.get("name") or item.get("emdb_id") or ""),
                "resolution": str(item.get("resolution") or ""),
                "url": f"https://www.ebi.ac.uk/emdb/{item.get('emdb_id') or item.get('accession') or item.get('id') or ''}",
            }
            for item in items[:limit]
            if item.get("emdb_id") or item.get("accession") or item.get("id")
        ]


class ComplexPortalConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        params = urllib.parse.urlencode({"query": query, "page": 0, "pageSize": limit})
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/intact/complex-ws/search/query?{params}"
        )
        items = payload.get("elements", payload.get("content", payload.get("results", [])))
        return [
            {
                "id": str(item.get("complexAc") or item.get("accession") or item.get("id") or ""),
                "title": str(item.get("name") or item.get("complexName") or item.get("id") or ""),
                "species": str(item.get("organismName") or item.get("species") or ""),
                "url": f"https://www.ebi.ac.uk/complexportal/complex/{item.get('complexAc') or item.get('accession') or item.get('id') or ''}",
            }
            for item in items[:limit]
            if item.get("complexAc") or item.get("accession") or item.get("id")
        ]


class IntActConnector:
    def __init__(self, *, fetch_json: Callable[[str], Any] = fetch_json) -> None:
        self._fetch_json = fetch_json

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        encoded = urllib.parse.quote(query, safe="")
        payload = self._fetch_json(
            f"https://www.ebi.ac.uk/intact/ws/interaction/findInteraction/{encoded}?page=0&pageSize={limit}"
        )
        items = payload.get("content", payload.get("results", [])) if isinstance(payload, dict) else []
        return [
            {
                "id": str(item.get("interactionAc") or item.get("ac") or item.get("id") or ""),
                "title": str(item.get("interactionType") or item.get("description") or item.get("id") or ""),
                "participants": str(item.get("participantCount") or ""),
                "url": f"https://www.ebi.ac.uk/intact/interaction/{item.get('interactionAc') or item.get('ac') or item.get('id') or ''}",
            }
            for item in items[:limit]
            if item.get("interactionAc") or item.get("ac") or item.get("id")
        ]


class VersionedSnapshotConnector:
    """Search a checked-in release inventory when no stable query API is available."""

    def __init__(self, snapshot: str, *, root: Path | None = None) -> None:
        plugin_root = root or Path(__file__).resolve().parents[2]
        self.snapshot_path = plugin_root / "connectors" / "snapshots" / snapshot

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        query, limit = _validate(query, limit)
        payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        lowered = query.lower()
        records = []
        for item in payload.get("records", []):
            haystack = " ".join(str(value) for value in item.values()).lower()
            if lowered in haystack:
                records.append({key: str(value) for key, value in item.items()})
            if len(records) >= limit:
                break
        return records
