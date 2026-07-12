---
name: ncbi-gene-search
description: "Resolve human genes through NCBI Entrez Gene and preserve links to sequence, literature, variation, and GEO resources. Use for NCBI-centered gene and identifier research."
license: MIT
---

# NCBI Gene Search

1. Call `science_search_ncbi_gene` with a canonical symbol, synonym, or stable identifier.
2. Confirm species and Entrez Gene ID; cross-check MyGene and Ensembl for ambiguous symbols.
3. Follow links only for the evidence required: sequence, PubMed/PMC, ClinVar/dbSNP, GEO, or conserved domains.
4. Record database, query, IDs, release/access date, and link path with `$science-provenance`.

Do not treat Gene summaries or linked records as primary experimental evidence. Respect NCBI rate and usage policies.

Source basis: [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/).
