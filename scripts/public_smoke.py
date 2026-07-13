#!/usr/bin/env python3
"""Run explicit, read-only smoke queries against every public MCP source."""

import argparse
import os
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


def _report_allowed_unavailable(name: str, detail: str) -> None:
    message = f"{name}: {detail} (explicitly allowed)"
    print(message)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning title=Public API unavailable::{message}")


def run_checks(
    checks: Iterable[tuple[str, Any, str]],
    allowed_http_403: set[str] | None = None,
    allowed_unavailable: set[str] | None = None,
) -> int:
    allowed_http_403 = allowed_http_403 or set()
    allowed_unavailable = allowed_unavailable or set()
    processed = 0
    failures: list[str] = []
    for name, connector, query in checks:
        try:
            try:
                results = connector.search(query, limit=1)
            except TimeoutError:
                results = connector.search(query, limit=1)
        except TimeoutError:
            if name in allowed_unavailable or "all" in allowed_unavailable:
                _report_allowed_unavailable(name, "unavailable (timeout after 2 attempts)")
                processed += 1
                continue
            failures.append(f"{name}: timeout after 2 attempts")
            continue
        except urllib.error.HTTPError as error:
            if error.code == 403 and name in allowed_http_403:
                _report_allowed_unavailable(name, "environment-blocked (HTTP 403)")
                processed += 1
                continue
            if error.code >= 500 and (
                name in allowed_unavailable or "all" in allowed_unavailable
            ):
                _report_allowed_unavailable(name, f"unavailable (HTTP {error.code})")
                processed += 1
                continue
            failures.append(f"{name}: HTTP {error.code}")
            continue
        if not results:
            failures.append(f"{name}: no results")
            continue
        print(f"{name}: ok ({results[0]['id']})")
        processed += 1
    if failures:
        raise SystemExit("public smoke failures:\n- " + "\n- ".join(failures))
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
    parser.add_argument(
        "--allow-unavailable",
        action="append",
        default=[],
        metavar="SOURCE",
        help="Continue when this named source times out twice or returns HTTP 5xx",
    )
    args = parser.parse_args()
    known = {name for name, _, _ in CHECKS}
    allowed_http_403 = set(args.allow_http_403)
    allowed_unavailable = set(args.allow_unavailable)
    unknown_http_403 = sorted(allowed_http_403 - known)
    unknown_unavailable = sorted(allowed_unavailable - known - {"all"})
    if unknown_http_403:
        raise SystemExit(f"Unknown source in --allow-http-403: {', '.join(unknown_http_403)}")
    if unknown_unavailable:
        raise SystemExit(
            f"Unknown source in --allow-unavailable: {', '.join(unknown_unavailable)}"
        )
    run_checks(CHECKS, allowed_http_403, allowed_unavailable)


if __name__ == "__main__":
    main()
