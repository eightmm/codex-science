---
name: public-omics-dataset-discovery
description: "Discover and triage reusable public transcriptomics, proteomics, metabolomics, microbiome, and supplementary-study datasets. Use when a research question needs external data rather than only literature."
license: MIT
---

# Public Omics Dataset Discovery

1. Define organism, tissue/cell type, disease/perturbation, assay, sample unit, minimum metadata, license, and download budget.
2. Search BioStudies/ArrayExpress, PRIDE/ProteomeXchange, MGnify, and relevant GEO/MetaboLights resources using the smallest source set.
3. Build a candidate table with accession, release, cohort/sample count, assay/platform, controls, raw/processed files, size, license/terms, publication, and exclusion reason.
4. Inspect manifests before download; ask before large transfers or controlled-access data.
5. Select datasets by study design and metadata fitness, not query rank. Record every inclusion/exclusion decision.

Return recommended datasets, rejected near matches, harmonization risks, download plan, and a minimal validation analysis. Repository presence is not quality or reuse permission.

Record the complete candidate table with `$science-provenance`; run `$science-review` before final selection.
