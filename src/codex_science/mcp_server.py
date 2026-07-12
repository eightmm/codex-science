"""Minimal read-only MCP server for the catalog and public connectors."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from codex_science.catalog import load_inventory, search_inventory
from codex_science.connectors import (
    AlphaFoldConnector,
    ArxivConnector,
    BgeeConnector,
    BioBankJapanConnector,
    BioStudiesConnector,
    CBioPortalConnector,
    ChEBIConnector,
    ChEMBLConnector,
    ClinicalTrialsConnector,
    EnsemblConnector,
    EuropePMCConnector,
    FinnGenConnector,
    GTExConnector,
    GWASCatalogConnector,
    HumanProteinAtlasConnector,
    InterProConnector,
    MGnifyConnector,
    MyGeneConnector,
    NCBIGeneConnector,
    OLSConnector,
    OpenAlexConnector,
    OpenTargetsConnector,
    PDBConnector,
    PRIDEConnector,
    ProteomeXchangeConnector,
    PubChemConnector,
    PubMedConnector,
    QuickGOConnector,
    RNACentralConnector,
    ReactomeConnector,
    RheaConnector,
    STRINGConnector,
    UKBTopMedConnector,
    UniProtConnector,
)
from codex_science.life_science import plan_life_science_research


PROTOCOL_VERSION = "2025-06-18"


def _tool(name: str, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    }


TOOLS = (
    _tool("science_search_skills", "Search the audited local scientific skill catalog."),
    _tool("science_search_pubmed", "Search PubMed through the public NCBI API."),
    _tool("science_search_arxiv", "Search arXiv through its public Atom API."),
    _tool("science_search_uniprot", "Search UniProtKB through its public REST API."),
    _tool("science_search_pdb", "Search experimental structures through the RCSB PDB Search API."),
    _tool("science_search_chembl", "Search ChEMBL molecules through its public REST API."),
    _tool("science_search_pubchem", "Resolve compounds and properties through PubChem PUG REST."),
    _tool("science_search_europepmc", "Search life-science literature through Europe PMC."),
    _tool("science_search_openalex", "Search scholarly works through OpenAlex."),
    _tool("science_search_clinical_trials", "Search studies through ClinicalTrials.gov API v2."),
    _tool("science_search_interpro", "Search protein families and domains through InterPro."),
    _tool("science_search_quickgo", "Search Gene Ontology terms through QuickGO."),
    _tool("science_search_ols", "Search biomedical ontologies through EMBL-EBI OLS."),
    _tool("science_search_reactome", "Search pathways and reactions through Reactome ContentService."),
    _tool("science_search_string", "Resolve proteins through the STRING API."),
    _tool("science_search_alphafold", "Fetch AlphaFold DB model metadata by UniProt accession."),
    _tool("science_search_mygene", "Normalize human gene identifiers through MyGene.info."),
    _tool("science_search_ensembl", "Resolve human gene symbols through Ensembl REST."),
    _tool("science_search_ncbi_gene", "Resolve human genes through NCBI Entrez Gene."),
    _tool("science_search_gwas_catalog", "Resolve traits through GWAS Catalog REST API v2."),
    _tool("science_search_opentargets", "Search Open Targets entities through its public GraphQL API."),
    _tool("science_search_gtex", "Resolve GTEx genes and genome-build metadata."),
    _tool("science_search_hpa", "Search Human Protein Atlas gene records."),
    _tool("science_search_bgee", "Search healthy wild-type expression genes through Bgee."),
    _tool("science_search_biostudies", "Discover public studies through BioStudies."),
    _tool("science_search_cbioportal", "Resolve cancer genes through cBioPortal."),
    _tool("science_search_chebi", "Search chemical entities through ChEBI."),
    _tool("science_search_rhea", "Search curated biochemical reactions through Rhea."),
    _tool("science_search_pride", "Discover public proteomics projects through PRIDE."),
    _tool("science_search_proteomexchange", "Fetch a ProteomeXchange dataset by PXD accession."),
    _tool("science_search_mgnify", "Discover public microbiome studies through MGnify."),
    _tool("science_search_rnacentral", "Search non-coding RNA records through RNAcentral."),
    _tool("science_search_finngen", "Search FinnGen PheWAS by normalized GRCh38 variant."),
    _tool("science_search_biobank_japan", "Search BioBank Japan PheWAS by normalized variant."),
    _tool("science_search_ukb_topmed", "Search UKB/TOPMed PheWAS by normalized variant."),
    _tool(
        "science_plan_life_science_research",
        "Plan bounded entity normalization, evidence lanes, provenance, and synthesis for a life-science question.",
    ),
)


class CodexScienceMCP:
    def __init__(self, inventory_path: Path) -> None:
        self.inventory_path = inventory_path
        self.connectors = {
            "science_search_pubmed": PubMedConnector(),
            "science_search_arxiv": ArxivConnector(),
            "science_search_uniprot": UniProtConnector(),
            "science_search_pdb": PDBConnector(),
            "science_search_chembl": ChEMBLConnector(),
            "science_search_pubchem": PubChemConnector(),
            "science_search_europepmc": EuropePMCConnector(),
            "science_search_openalex": OpenAlexConnector(),
            "science_search_clinical_trials": ClinicalTrialsConnector(),
            "science_search_interpro": InterProConnector(),
            "science_search_quickgo": QuickGOConnector(),
            "science_search_ols": OLSConnector(),
            "science_search_reactome": ReactomeConnector(),
            "science_search_string": STRINGConnector(),
            "science_search_alphafold": AlphaFoldConnector(),
            "science_search_mygene": MyGeneConnector(),
            "science_search_ensembl": EnsemblConnector(),
            "science_search_ncbi_gene": NCBIGeneConnector(),
            "science_search_gwas_catalog": GWASCatalogConnector(),
            "science_search_opentargets": OpenTargetsConnector(),
            "science_search_gtex": GTExConnector(),
            "science_search_hpa": HumanProteinAtlasConnector(),
            "science_search_bgee": BgeeConnector(),
            "science_search_biostudies": BioStudiesConnector(),
            "science_search_cbioportal": CBioPortalConnector(),
            "science_search_chebi": ChEBIConnector(),
            "science_search_rhea": RheaConnector(),
            "science_search_pride": PRIDEConnector(),
            "science_search_proteomexchange": ProteomeXchangeConnector(),
            "science_search_mgnify": MGnifyConnector(),
            "science_search_rnacentral": RNACentralConnector(),
            "science_search_finngen": FinnGenConnector(),
            "science_search_biobank_japan": BioBankJapanConnector(),
            "science_search_ukb_topmed": UKBTopMedConnector(),
        }

    @staticmethod
    def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return self._error(None, -32600, "Invalid Request")
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if request_id is None and method and method.startswith("notifications/"):
            return None
        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "codex-science", "version": "0.1.0"},
                    "instructions": (
                        "Read-only scientific catalog and public-source search. Validate primary sources, "
                        "respect source licenses, and never treat search output as clinical advice."
                    ),
                },
            )
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            return self._result(request_id, {"tools": list(TOOLS)})
        if method == "tools/call":
            return self._call_tool(request_id, request.get("params", {}))
        return self._error(request_id, -32601, f"Unknown method: {method}")

    def _call_tool(self, request_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "Invalid tool parameters")
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in {tool["name"] for tool in TOOLS} or not isinstance(arguments, dict):
            return self._error(request_id, -32602, f"Unknown or invalid tool: {name}")
        try:
            extra = set(arguments) - {"query", "limit"}
            if extra:
                raise ValueError(f"Unexpected arguments: {', '.join(sorted(extra))}")
            query = arguments.get("query", "")
            limit = arguments.get("limit", 5)
            if not isinstance(query, str):
                raise TypeError("Query must be a string")
            if not query.strip() or len(query) > 500:
                raise ValueError("Query must contain 1 to 500 characters")
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise TypeError("Limit must be an integer")
            if not 1 <= limit <= 10:
                raise ValueError("Limit must be between 1 and 10")
            if name == "science_search_skills":
                payload = search_inventory(load_inventory(self.inventory_path), query, limit=limit)
            elif name == "science_plan_life_science_research":
                payload = plan_life_science_research(query)
            else:
                payload = self.connectors[name].search(query, limit=limit)
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, -32602, str(exc))
        except Exception as exc:  # network and remote-service failures remain explicit tool errors
            return self._result(
                request_id,
                {"content": [{"type": "text", "text": f"Connector error: {exc}"}], "isError": True},
            )
        return self._result(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]},
        )


def run_stdio(inventory_path: Path) -> None:
    server = CodexScienceMCP(inventory_path)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = server.handle(request)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            response = CodexScienceMCP._error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
