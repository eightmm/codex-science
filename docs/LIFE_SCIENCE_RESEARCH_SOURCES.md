# Agentic Life-Science Research Sources

Verified 2026-07-11. This is an independent MIT-licensed implementation. The
OpenAI Life Science Research plugin was used only to identify useful public
capability categories; its proprietary skill text and scripts are not copied.

## Execution contract

- Normalize entities before retrieval.
- Use at most four independent evidence lanes.
- Bound every public query to ten returned records.
- Preserve source, release/build, exact query, identifiers, access time, and
  artifact hash.
- Treat missing, negative, contradictory, and unavailable evidence separately.
- Never infer causality from association or provide patient-specific advice.

## Bundled read-only MCP tools

| Tool | Public source | Primary use | Important boundary |
|---|---|---|---|
| `science_search_mygene` | [MyGene.info](https://docs.mygene.info/en/latest/doc/query_service.html) | Gene normalization | Verify species and aliases |
| `science_search_ensembl` | [Ensembl REST](https://rest.ensembl.org/) | Gene IDs | Pin species/release |
| `science_search_ncbi_gene` | [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) | Entrez Gene | Respect NCBI rate policy |
| `science_search_gwas_catalog` | [GWAS Catalog v2](https://www.ebi.ac.uk/gwas/rest/api/v2/docs) | Trait/EFO resolution | Curated leads are not full summary statistics |
| `science_search_opentargets` | [Open Targets](https://platform-docs.opentargets.org/data-access/graphql-api) | Target/disease entities | Record data release |
| `science_search_gtex` | [GTEx API](https://gtexportal.org/home/apiPage) | Gene/build metadata | Tissue and release specific |
| `science_search_hpa` | [Human Protein Atlas](https://www.proteinatlas.org/about/download) | Gene/tissue context | RNA, protein, and localization differ |
| `science_search_bgee` | [Bgee API](https://www.bgee.org/support/tutorial-api) | Healthy expression context | Preserve species/stage/ontology |
| `science_search_biostudies` | [BioStudies](https://www.ebi.ac.uk/biostudies/help) | Study discovery | Inspect files and reuse terms |
| `science_search_cbioportal` | [cBioPortal](https://www.cbioportal.org/api/swagger-ui/index.html) | Cancer genes/cohorts | Denominator and assay coverage matter |
| `science_search_chebi` | [ChEBI](https://www.ebi.ac.uk/chebi/webServicesForward.do) | Chemical identity | Preserve form, charge, stereochemistry |
| `science_search_rhea` | [Rhea](https://www.rhea-db.org/help/download) | Biochemical reactions | Reaction presence is not cellular flux |
| `science_search_pride` | [PRIDE](https://www.ebi.ac.uk/pride/ws/archive/v3/swagger-ui.html) | Proteomics studies | Registration is not identification evidence |
| `science_search_proteomexchange` | [ProteomeXchange](https://proteomecentral.proteomexchange.org/) | PXD accession resolution | Keyword discovery uses PRIDE; verify repository-of-record metadata |
| `science_search_mgnify` | [MGnify](https://www.ebi.ac.uk/metagenomics/api/v1/) | Microbiome studies | Pipeline and compositional effects matter |
| `science_search_rnacentral` | [RNAcentral](https://rnacentral.org/api) | ncRNA normalization | Preserve sequence/release/species |
| `science_search_finngen` | [FinnGen R12](https://r12.finngen.fi/) | PheWAS | GRCh38; cohort-specific phenotype coding |
| `science_search_biobank_japan` | [BioBank Japan PheWeb](https://pheweb.jp/) | PheWAS | Verify build and ancestry |
| `science_search_ukb_topmed` | [UKB/TOPMed PheWeb](https://pheweb.org/UKB-TOPMed/) | PheWAS | Verify build and phenotype definition |
| `science_plan_life_science_research` | Local deterministic planner | Entity/lane/provenance plan | Planning does not retrieve evidence |

These extend the original 15 bundled public tools, for 36 total MCP tools:
34 public sources, local catalog search, and the planner.

## Availability- or terms-gated sources

| Source | Status | Reason |
|---|---|---|
| TPMI PheWAS | gated | Public endpoint returned HTTP 403 during verification |
| HMDB | gated | Public search returned HTTP 403; source-specific reuse terms apply |
| GeneBass burden | gated | No stable documented public API verified |
| eQTL Catalogue | cataloged | Prefer versioned bulk releases until a stable query API is verified |
| MetaboLights search | cataloged | Current study-list endpoint does not apply a specific search query |
| PharmGKB | gated | License and data-use terms require source-specific review |
| CIViC/IPD | cataloged | Useful sources, but not required for the first safe MCP tranche |

Gated sources may still be used after verifying current terms and access, but
Codex Science must not label them as bundled working tools.

## Agentic workflows

- `cx-life-science-research-routing`
- `cx-biomedical-entity-normalization`
- `cx-variant-evidence-synthesis`
- `cx-phewas-replication-analysis`
- `cx-locus-to-gene-prioritization`
- `cx-gene-burden-evidence`
- `cx-expression-cell-context`
- `cx-public-omics-dataset-discovery`
- `cx-translational-pharmacology-evidence`
- `cx-cancer-genomics-evidence`
- `cx-metabolomics-proteomics-context`
- `cx-biomedical-evidence-reconciliation`
- `cx-ncbi-integrated-research`

Each workflow composes source-specific skills, `$science-provenance`, and
`$science-review`; none silently converts a portal result into a causal or
clinical conclusion.
