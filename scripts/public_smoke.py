#!/usr/bin/env python3
"""Run explicit, read-only smoke queries against every public MCP source."""

from codex_science.connectors import (
    AlphaFoldConnector,
    ArxivConnector,
    ChEMBLConnector,
    ClinicalTrialsConnector,
    EuropePMCConnector,
    InterProConnector,
    OLSConnector,
    OpenAlexConnector,
    PDBConnector,
    PubChemConnector,
    PubMedConnector,
    QuickGOConnector,
    ReactomeConnector,
    STRINGConnector,
    UniProtConnector,
)


def main() -> None:
    checks = (
        ("pubmed", PubMedConnector(), "protein folding"),
        ("arxiv", ArxivConnector(), "symbolic mathematics"),
        ("uniprot", UniProtConnector(), "hemoglobin"),
        ("pdb", PDBConnector(), "hemoglobin"),
        ("chembl", ChEMBLConnector(), "aspirin"),
        ("pubchem", PubChemConnector(), "aspirin"),
        ("europepmc", EuropePMCConnector(), "protein folding"),
        ("openalex", OpenAlexConnector(), "protein folding"),
        ("clinical_trials", ClinicalTrialsConnector(), "breast cancer"),
        ("interpro", InterProConnector(), "kinase"),
        ("quickgo", QuickGOConnector(), "apoptosis"),
        ("ols", OLSConnector(), "apoptosis"),
        ("reactome", ReactomeConnector(), "apoptosis"),
        ("string", STRINGConnector(), "TP53"),
        ("alphafold", AlphaFoldConnector(), "P69905"),
    )
    for name, connector, query in checks:
        results = connector.search(query, limit=1)
        if not results:
            raise SystemExit(f"{name}: no results")
        print(f"{name}: ok ({results[0]['id']})")


if __name__ == "__main__":
    main()
