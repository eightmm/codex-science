---
name: gwas-catalog-search
description: "Resolve traits and discover curated human genetic association evidence with GWAS Catalog REST API v2. Use for trait, locus, variant, ancestry, study, and locus-to-gene research."
license: MIT
---

# GWAS Catalog Search

1. Resolve free-text traits with `science_search_gwas_catalog`; retain the selected EFO/MONDO ID and rejected alternatives.
2. Use the current v2 API and prefer ontology IDs over labels for downstream association queries.
3. Preserve rsID, assembly, effect allele, p-value, effect estimate, study accession, ancestry, sample size, publication, and access date.
4. Distinguish curated lead associations from full summary statistics; record dataset-specific terms and release metadata.
5. Compose `$cx-biomedical-entity-normalization`, `$cx-phewas-replication-analysis`, or `$cx-locus-to-gene-prioritization` when synthesis is requested.

Association does not establish causality. Do not pool ancestries, traits, or effect directions without harmonization.

Store association tables and source releases with `$science-provenance`; run `$science-review` on causal claims.

Source basis: [GWAS Catalog API v2](https://www.ebi.ac.uk/gwas/rest/api/v2/docs).
