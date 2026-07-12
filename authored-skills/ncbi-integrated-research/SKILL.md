---
name: ncbi-integrated-research
description: "Run bounded NCBI-centered research across Gene, PubMed/PMC, sequence, variation, and GEO-linked records. Use when a gene, accession, sequence, or literature question requires traceable NCBI cross-links."
license: MIT
---

# NCBI Integrated Research

1. Resolve the canonical human gene with `science_search_ncbi_gene`; preserve species and Entrez ID.
2. Select only required lanes: PubMed literature, PMC open text, sequence/Datasets, ClinVar/dbSNP variation, or GEO metadata.
3. Follow explicit database links rather than repeating broad free-text searches. Bound each result set and respect NCBI rate policy.
4. Preserve database, endpoint, query, IDs, link relation, release/access time, and raw artifact path when saved.
5. Render PMIDs and DOIs as links; distinguish metadata, abstract, full text, sequence record, and curated assertion.
6. Reconcile evidence with primary publications and `$science-review` before conclusions.

Do not treat NCBI summaries as clinical guidance. Do not download large sequence or GEO payloads without a declared file and compute plan.

Store cross-database link paths and identifiers with `$science-provenance` before review.
