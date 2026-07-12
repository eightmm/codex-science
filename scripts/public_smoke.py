#!/usr/bin/env python3
"""Run explicit, read-only smoke queries against every public MCP source."""

import argparse
import urllib.error
from collections.abc import Iterable
from typing import Any

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


CHECKS = (
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


def run_checks(
    checks: Iterable[tuple[str, Any, str]], allowed_http_403: set[str] | None = None
) -> int:
    allowed_http_403 = allowed_http_403 or set()
    processed = 0
    for name, connector, query in checks:
        try:
            results = connector.search(query, limit=1)
        except urllib.error.HTTPError as error:
            if error.code == 403 and name in allowed_http_403:
                print(f"{name}: environment-blocked (HTTP 403; explicitly allowed)")
                processed += 1
                continue
            raise
        if not results:
            raise SystemExit(f"{name}: no results")
        print(f"{name}: ok ({results[0]['id']})")
        processed += 1
    return processed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-http-403",
        action="append",
        default=[],
        metavar="SOURCE",
        help="Continue only when this named source returns HTTP 403",
    )
    args = parser.parse_args()
    allowed = set(args.allow_http_403)
    known = {name for name, _, _ in CHECKS}
    unknown = sorted(allowed - known)
    if unknown:
        raise SystemExit(f"Unknown source in --allow-http-403: {', '.join(unknown)}")
    run_checks(CHECKS, allowed)


if __name__ == "__main__":
    main()
