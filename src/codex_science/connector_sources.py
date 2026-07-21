"""Registry of public source clients and their typed query contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from codex_science.connectors import (
    AlphaFoldConnector, ArxivConnector, BgeeConnector, BioBankJapanConnector,
    BioStudiesConnector, CBioPortalConnector, ChEBIConnector, ChEMBLConnector,
    ClinicalTrialsConnector, EnsemblConnector, EuropePMCConnector, FinnGenConnector,
    GTExConnector, GWASCatalogConnector, HumanProteinAtlasConnector, InterProConnector,
    MGnifyConnector, MyGeneConnector, NCBIGeneConnector, OLSConnector, OpenAlexConnector,
    OpenTargetsConnector, PDBConnector, PRIDEConnector, ProteomeXchangeConnector,
    PubChemConnector, PubMedConnector, QuickGOConnector, RNACentralConnector,
    ReactomeConnector, RheaConnector, STRINGConnector, UKBTopMedConnector, UniProtConnector,
)
from codex_science.typed_connectors import (
    ArrayExpressConnector, BindingDBConnector, ClinVarConnector, ComplexPortalConnector,
    DBSNPConnector, EMDBConnector, ENCODEConnector, GEOConnector, GnomADConnector,
    IntActConnector, JASPARConnector, MetaboLightsConnector, OpenFDAConnector,
    UniBindConnector, VersionedSnapshotConnector,
)


@dataclass(frozen=True)
class SourceSpec:
    key: str
    tool_name: str
    description: str
    factory: Callable[[], Any]
    maturity: str = "live-smoke-tested"
    query_semantics: str = "free-text"
    operations: tuple[str, ...] = ("search",)

    def public_contract(self) -> dict[str, Any]:
        return {
            "source": self.key, "tool": self.tool_name, "description": self.description,
            "maturity": self.maturity, "operations": list(self.operations),
            "query_semantics": self.query_semantics, "source_contract_version": "2",
        }


ROWS: tuple[tuple[str, str, str, Callable[[], Any], str, str], ...] = (
    ("pubmed", "science_search_pubmed", "Search PubMed through NCBI.", PubMedConnector, "live-smoke-tested", "free-text"),
    ("arxiv", "science_search_arxiv", "Search arXiv.", ArxivConnector, "live-smoke-tested", "free-text"),
    ("uniprot", "science_search_uniprot", "Search UniProtKB.", UniProtConnector, "live-smoke-tested", "free-text"),
    ("pdb", "science_search_pdb", "Search experimental structures in PDB.", PDBConnector, "live-smoke-tested", "free-text"),
    ("chembl", "science_search_chembl", "Search ChEMBL molecules.", ChEMBLConnector, "live-smoke-tested", "free-text"),
    ("pubchem", "science_search_pubchem", "Search PubChem compounds.", PubChemConnector, "live-smoke-tested", "free-text"),
    ("europepmc", "science_search_europepmc", "Search Europe PMC.", EuropePMCConnector, "live-smoke-tested", "free-text"),
    ("openalex", "science_search_openalex", "Search OpenAlex works.", OpenAlexConnector, "live-smoke-tested", "free-text"),
    ("clinical_trials", "science_search_clinical_trials", "Search ClinicalTrials.gov.", ClinicalTrialsConnector, "live-smoke-tested", "free-text"),
    ("interpro", "science_search_interpro", "Search InterPro.", InterProConnector, "live-smoke-tested", "free-text"),
    ("quickgo", "science_search_quickgo", "Search Gene Ontology through QuickGO.", QuickGOConnector, "live-smoke-tested", "free-text"),
    ("ols", "science_search_ols", "Search EMBL-EBI OLS.", OLSConnector, "live-smoke-tested", "free-text"),
    ("reactome", "science_search_reactome", "Search Reactome.", ReactomeConnector, "environment-sensitive", "free-text"),
    ("string", "science_search_string", "Search STRING proteins.", STRINGConnector, "live-smoke-tested", "gene-or-protein"),
    ("alphafold", "science_search_alphafold", "Fetch AlphaFold DB metadata.", AlphaFoldConnector, "live-smoke-tested", "uniprot-accession"),
    ("mygene", "science_search_mygene", "Normalize genes through MyGene.", MyGeneConnector, "live-smoke-tested", "gene"),
    ("ensembl", "science_search_ensembl", "Resolve genes through Ensembl.", EnsemblConnector, "live-smoke-tested", "gene"),
    ("ncbi_gene", "science_search_ncbi_gene", "Resolve NCBI genes.", NCBIGeneConnector, "live-smoke-tested", "gene"),
    ("gwas_catalog", "science_search_gwas_catalog", "Search GWAS Catalog traits.", GWASCatalogConnector, "live-smoke-tested", "trait"),
    ("opentargets", "science_search_opentargets", "Search Open Targets.", OpenTargetsConnector, "live-smoke-tested", "entity"),
    ("gtex", "science_search_gtex", "Resolve GTEx genes.", GTExConnector, "live-smoke-tested", "gene"),
    ("hpa", "science_search_hpa", "Search Human Protein Atlas.", HumanProteinAtlasConnector, "live-smoke-tested", "gene"),
    ("bgee", "science_search_bgee", "Search Bgee expression.", BgeeConnector, "live-smoke-tested", "gene"),
    ("biostudies", "science_search_biostudies", "Search BioStudies.", BioStudiesConnector, "live-smoke-tested", "free-text"),
    ("cbioportal", "science_search_cbioportal", "Search cBioPortal genes.", CBioPortalConnector, "live-smoke-tested", "gene"),
    ("chebi", "science_search_chebi", "Search ChEBI.", ChEBIConnector, "live-smoke-tested", "compound"),
    ("rhea", "science_search_rhea", "Search Rhea reactions.", RheaConnector, "live-smoke-tested", "reaction"),
    ("pride", "science_search_pride", "Search PRIDE projects.", PRIDEConnector, "live-smoke-tested", "free-text"),
    ("proteomexchange", "science_search_proteomexchange", "Resolve ProteomeXchange accessions.", ProteomeXchangeConnector, "live-smoke-tested", "pxd-accession"),
    ("mgnify", "science_search_mgnify", "Search MGnify studies.", MGnifyConnector, "live-smoke-tested", "free-text"),
    ("rnacentral", "science_search_rnacentral", "Search RNAcentral.", RNACentralConnector, "live-smoke-tested", "rna"),
    ("finngen", "science_search_finngen", "Search FinnGen PheWAS.", FinnGenConnector, "live-smoke-tested", "grch38-variant"),
    ("biobank_japan", "science_search_biobank_japan", "Search BioBank Japan PheWAS.", BioBankJapanConnector, "live-smoke-tested", "variant"),
    ("ukb_topmed", "science_search_ukb_topmed", "Search UKB/TOPMed PheWAS.", UKBTopMedConnector, "live-smoke-tested", "variant"),
    ("gnomad", "science_search_gnomad", "Fetch gnomAD v4 frequency context.", GnomADConnector, "fixture-tested-experimental", "grch38-variant"),
    ("clinvar", "science_search_clinvar_v2", "Search ClinVar.", ClinVarConnector, "fixture-tested", "variant-or-condition"),
    ("dbsnp", "science_search_dbsnp_v2", "Search dbSNP.", DBSNPConnector, "fixture-tested", "rsid-or-variant"),
    ("encode", "science_search_encode", "Search ENCODE.", ENCODEConnector, "fixture-tested-experimental", "free-text"),
    ("jaspar", "science_search_jaspar", "Search JASPAR matrices.", JASPARConnector, "fixture-tested", "transcription-factor"),
    ("unibind", "science_search_unibind", "Search UniBind datasets.", UniBindConnector, "fixture-tested-experimental", "transcription-factor"),
    ("geo", "science_search_geo", "Search GEO DataSets.", GEOConnector, "fixture-tested", "free-text"),
    ("arrayexpress", "science_search_arrayexpress", "Search ArrayExpress studies.", ArrayExpressConnector, "fixture-tested-experimental", "free-text"),
    ("metabolights", "science_search_metabolights", "Search MetaboLights.", MetaboLightsConnector, "fixture-tested-experimental", "free-text"),
    ("bindingdb", "science_search_bindingdb", "Search BindingDB by UniProt accession.", BindingDBConnector, "fixture-tested-experimental", "uniprot-accession"),
    ("openfda", "science_search_openfda", "Search openFDA drug labels.", OpenFDAConnector, "fixture-tested-experimental", "drug-name"),
    ("emdb", "science_search_emdb", "Search EMDB maps.", EMDBConnector, "fixture-tested-experimental", "free-text"),
    ("complex_portal", "science_search_complex_portal", "Search Complex Portal.", ComplexPortalConnector, "fixture-tested-experimental", "free-text"),
    ("intact", "science_search_intact", "Search IntAct interactions.", IntActConnector, "fixture-tested-experimental", "free-text"),
    ("eqtl_catalogue", "science_search_eqtl_catalogue", "Search checked-in eQTL Catalogue release metadata.", lambda: VersionedSnapshotConnector("eqtl-catalogue-releases.json"), "snapshot-contract", "release-or-study"),
)

SOURCE_SPECS = tuple(SourceSpec(*row) for row in ROWS)
SOURCE_BY_KEY = {spec.key: spec for spec in SOURCE_SPECS}
SOURCE_BY_TOOL = {spec.tool_name: spec for spec in SOURCE_SPECS}
