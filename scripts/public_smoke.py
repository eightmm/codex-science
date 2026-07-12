#!/usr/bin/env python3
"""Run explicit, read-only smoke queries against every public MCP source."""

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
        ("mygene", MyGeneConnector(), "TP53"),
        ("ensembl", EnsemblConnector(), "TP53"),
        ("ncbi_gene", NCBIGeneConnector(), "TP53"),
        ("gwas_catalog", GWASCatalogConnector(), "asthma"),
        ("opentargets", OpenTargetsConnector(), "TP53"),
        ("gtex", GTExConnector(), "TP53"),
        ("hpa", HumanProteinAtlasConnector(), "TP53"),
        ("bgee", BgeeConnector(), "TP53"),
        ("biostudies", BioStudiesConnector(), "TP53"),
        ("cbioportal", CBioPortalConnector(), "TP53"),
        ("chebi", ChEBIConnector(), "aspirin"),
        ("rhea", RheaConnector(), "glucose"),
        ("pride", PRIDEConnector(), "TP53"),
        ("proteomexchange", ProteomeXchangeConnector(), "PXD000001"),
        ("mgnify", MGnifyConnector(), "gut"),
        ("rnacentral", RNACentralConnector(), "TP53"),
        ("finngen", FinnGenConnector(), "10:112998590-C-T"),
        ("biobank_japan", BioBankJapanConnector(), "10:112998590-C-T"),
        ("ukb_topmed", UKBTopMedConnector(), "10:112998590-C-T"),
    )
    for name, connector, query in checks:
        results = connector.search(query, limit=1)
        if not results:
            raise SystemExit(f"{name}: no results")
        print(f"{name}: ok ({results[0]['id']})")


if __name__ == "__main__":
    main()
