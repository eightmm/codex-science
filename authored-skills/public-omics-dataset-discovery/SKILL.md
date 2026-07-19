---
name: public-omics-dataset-discovery
description: "Discover and triage reusable public transcriptomics, proteomics, metabolomics, microbiome, and supplementary-study datasets. Use when a research question needs external data rather than only literature."
license: MIT
---

# Public Omics Dataset Discovery

## Decision contract
Define organism, tissue or cell state, disease or perturbation, assay, sample unit, comparator, minimum metadata, reuse terms, raw-versus-processed need, storage and compute budget, and a validation analysis before searching.
## Workflow
Search only relevant repositories, deduplicate cross-listed studies, and build a candidate ledger with accession and version, cohort and sample counts, design and controls, assay and platform, batch structure, raw and processed files, checksums and size, metadata completeness, publication, terms, and explicit inclusion or exclusion reason.
Inspect manifests and sample annotations before transfer; assess leakage, pseudoreplication, donor overlap, confounding, missing controls, file accessibility, harmonization burden, and whether the study can identify the requested estimand.
## Outputs
Return ranked datasets, rejected near matches, a study-design fitness score with rationale, harmonization and bias risks, exact download plan, expected cost, and the smallest smoke analysis that can invalidate the selection.
## Boundaries
Repository presence, citation count, or query rank is not evidence of quality or permission; do not download large or controlled data before approval, never silently substitute samples or endpoints, record the full candidate ledger and snapshots with `$science-provenance`, and run `$science-review` before final selection.
