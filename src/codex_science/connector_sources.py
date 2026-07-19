"""Registry of public source clients and their typed operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

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
from codex_science.typed_connectors import (
    ArrayExpressConnector,
    BindingDBConnector,
    ClinVarConnector,
    ComplexPortalConnector,
    DBSNPConnector,
    EMDBConnector,
    ENCODEConnector,
    GEOConnector,
    GnomADConnector,
    IntActConnector,
    JASPARConnector,
    MetaboLightsConnector,
    OpenFDAConnector,
    UniBindConnector,
    VersionedSnapshotConnector,
)


@dataclass(frozen=True)
class SourceSpec:
    key: str
    tool_name: str
    description: str
    factory: Callable[[], Any]
    maturity: str = "live-smoke-tested"
    operations: tuple[str, ...] = ("search",)
    query_semantics: str = "free-text"

    def public_contract(self) -> dict[str, Any]:
        return {
            "source": self.key,
            "tool": self.tool_name,
            "description": self.description,
            "maturity": self.maturity,
            "operations": list(self.operations),
            "query_semantics": self.query_semantics,
            "source_contract_version": "2",
        }


_SOURCE_ROWS: tuple[tuple[str, str, str, Callable[[], Any], str, str], ...] = (
    ("pubmed", "science_search_pubmed", "Search PubMed through the public NCBI API.", PubMedConnector, "live-smoke-tested", "free-text"),
    ("arxiv", "science_search_arxiv", "Search arXiv through its public Atom API.", ArxivConnector, "live-smoke-tested", "free-text"),
    ("uniprot", "science_search_uniprot", "Search UniProtKB through its public REST API.", UniProtConnector, "live-smoke-tested", "free-text"),
    ("pdb", "science_search_pdb", "Search experimental structures through the RCSB PDB Search API.", PDBConnector, "live-smoke-tested", "free-text"),
    ("chembl", "science_search_chembl", "Search ChEMBL molecules through its public REST API.", ChEMBLConnector, "live-smoke-tested", "free-text"),
    ("pubchem", "science_search_pubchem", "Resolve compounds and properties through PubChem PUG REST.", PubChemConnector, "live-smoke-tested", "free-text"),
    ("europepmc", "science_search_europepmc", "Search life-science literature through Europe PMC.", EuropePMCConnector, "live-smoke-tested", "free-text"),
    ("openalex", "science_search_openalex", "Search scholarly works through OpenAlex.", OpenAlexConnector, "live-smoke-tested", "free-text"),
    ("clinical_trials", "science_search_clinical_trials", "Search studies through ClinicalTrials.gov API v2.", ClinicalTrialsConnector, "live-smoke-tested", "free-text"),
    ("interpro", "science_search_interpro", "Search protein families and domains through InterPro.", InterProConnector, "live-smoke-tested", "free-text"),
    ("quickgo", "science_search_quickgo", "Search Gene Ontology terms through QuickGO.", QuickGOConnector, "live-smoke-tested", "free-text"),
    ("ols", "science_search_ols", "Search biomedical ontologies through EMBL-EBI OLS.", OLSConnector, "live-smoke-tested", "free-text"),
    ("reactome", "science_search_reactome", "Search pathways and reactions through Reactome ContentService.", ReactomeConnector, "environment-sensitive", "free-text"),
    ("string", "science_search_string", "Resolve proteins through the STRING API.", STRINGConnector, "live-smoke-tested", "gene-or-protein"),
    ("alphafold", "science_search_alphafold", "Fetch AlphaFold DB model metadata by UniProt accession.", AlphaFoldConnector, "live-smoke-tested", "uniprot-accession"),
    ("mygene", "science_search_mygene", "Normalize human gene identifiers through MyGene.info.", MyGeneConnector, "live-smoke-tested", "gene"),
    ("ensembl", "science_search_ensembl", "Resolve human gene symbols through Ensembl REST.", EnsemblConnector, "live-smoke-tested", "gene"),
    ("ncbi_gene", "science_search_ncbi_gene", "Resolve human genes through NCBI Entrez Gene.", NCBIGeneConnector, "live-smoke-tested", "gene"),
    ("gwas_catalog", "science_search_gwas_catalog", "Resolve traits through GWAS Catalog REST API v2.", GWASCatalogConnector, "live-smoke-tested", "trait"),
    ("opentargets", "science_search_opentargets", "Search Open Targets entities through its public GraphQL API.", OpenTargetsConnector, "live-smoke-tested", "entity"),
    ("gtex", "science_search_gtex", "Resolve GTEx genes and genome-build metadata.", GTExConnector, "live-smoke-tested", "gene"),
    ("hpa", "science_search_hpa", "Search Human Protein Atlas gene records.", HumanProteinAtlasConnector, "live-smoke-tested", "gene"),
    ("bgee", "science_search_bgee", "Search healthy wild-type expression genes through Bgee.", BgeeConnector, "live-smoke-tested", "gene"),
    ("biostudies", "science_search_biostudies", "Discover public studies through BioStudies.", BioStudiesConnector, "live-smoke-tested", "free-text"),
    ("cbioportal", "science_search_cbioportal", "Resolve cancer genes through cBioPortal.", CBioPortalConnector, "live-smoke-tested", "gene"),
    ("chebi", "science_search_chebi", "Search chemical entities through ChEBI.", ChEBIConnector, "live-smoke-tested", "compound"),
    ("rhea", "science_search_rhea", "Search curated biochemical reactions through Rhea.", RheaConnector, "live-smoke-tested", "reaction"),
    ("pride", "science_search_pride", "Discover public proteomics projects through PRIDE.", PRIDEConnector, "live-smoke-tested", "free-text"),
    ("proteomexchange", "science_search_proteomexchange", "Fetch a ProteomeXchange dataset by PXD accession.", ProteomeXchangeConnector, "live-smoke-tested", "pxd-accession"),
    ("mgnify", "science_search_mgnify", "Discover public microbiome studies through MGnify.", MGnifyConnector, "live-smoke-tested", "free-text"),
    ("rnacentral", "science_search_rnacentral", "Search non-coding RNA records through RNAcentral.", RNACentralConnector, "live-smoke-tested", "rna"),
    ("finngen", "science_search_finngen", "Search FinnGen PheWAS by normalized GRCh38 variant.", FinnGenConnector, "live-smoke-tested", "grch38-variant"),
    ("biobank_japan", "science_search_biobank_japan", "Search BioBank Japan PheWAS by normalized variant.", BioBankJapanConnector, "live-smoke-tested", "variant"),
    ("ukb_topmed", "science_search_ukb_topmed", "Search UKB/TOPMed PheWAS by normalized variant.", UKBTopMedConnector, "live-smoke-tested", "variant"),
    ("gnomad", "science_search_gnomad", "Fetch gnomAD v4 frequency context for a normalized GRCh38 variant.", GnomADConnector, "fixture-tested-experimental", "grch38-variant"),
    ("clinvar", "science_search_clinvar_v2", "Search ClinVar through NCBI E-utilities with a replayable receipt.", ClinVarConnector, "fixture-tested", "variant-or-condition"),
    ("dbsnp", "science_search_dbsnp_v2", "Search dbSNP through NCBI E-utilities with a replayable receipt.", DBSNPConnector, "fixture-tested", "rsid-or-variant"),
    ("encode", "science_search_encode", "Search ENCODE records through the public portal API.", ENCODEConnector, "fixture-tested-experimental", "free-text"),
    ("jaspar", "science_search_jaspar", "Search JASPAR transcription-factor matrices.", JASPARConnector, "fixture-tested", "transcription-factor"),
    ("unibind", "science_search_unibind", "Search UniBind transcription-factor binding datasets.", UniBindConnector, "fixture-tested-experimental", "transcription-factor"),
    ("geo", "science_search_geo", "Search GEO DataSets through NCBI E-utilities.", GEOConnector, "fixture-tested", "free-text"),
    ("arrayexpress", "science_search_arrayexpress", "Search ArrayExpress studies through BioStudies.", ArrayExpressConnector, "fixture-tested-experimental", "free-text"),
    ("metabolights", "science_search_metabolights", "Search MetaboLights public studies.", MetaboLightsConnector, "fixture-tested-experimental", "free-text"),
    ("bindingdb", "science_search_bindingdb", "Retrieve BindingDB ligand records for a UniProt accession.", BindingDBConnector, "fixture-tested-experimental", "uniprot-accession"),
    ("openfda", "science_search_openfda", "Search openFDA drug labeling records.", OpenFDAConnector, "fixture-tested-experimental", "drug-name"),
    ("emdb", "science_search_emdb", "Search EMDB cryo-EM map records.", EMDBConnector, "fixture-tested-experimental", "free-text"),
    ("complex_portal", "science_search_complex_portal", "Search Complex Portal assemblies.", ComplexPortalConnector, "fixture-tested-experimental", "free-text"),
    ("intact", "science_search_intact", "Search IntAct molecular interactions.", IntActConnector, "fixture-tested-experimental", "free-text"),
    ("eqtl_catalogue", "science_search_eqtl_catalogue", "Search the checked-in eQTL Catalogue release inventory; bulk evidence must be separately hashed.", lambda: VersionedSnapshotConnector("eqtl-catalogue-releases.json"), "snapshot-contract", "release-or-study"),
)

SOURCE_SPECS: tuple[SourceSpec, ...] = tuple(
    SourceSpec(key, tool, description, factory, maturity, ("search",), semantics)
    for key, tool, description, factory, maturity, semantics in _SOURCE_ROWS
)
SOURCE_BY_KEY = {spec.key: spec for spec in SOURCE_SPECS}
SOURCE_BY_TOOL = {spec.tool_name: spec for spec in SOURCE_SPECS}
