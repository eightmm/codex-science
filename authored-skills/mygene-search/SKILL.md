---
name: mygene-search
description: "Normalize human gene symbols and aliases to Entrez, Ensembl, and taxonomic identifiers with MyGene.info. Use before cross-database gene, target, expression, or variant research when identifiers are incomplete or inconsistent."
license: MIT
---

# MyGene Search

1. Call `science_search_mygene` with the supplied symbol, alias, or identifier and `limit<=10`.
2. Prefer exact human-symbol matches; retain every returned identifier and taxon instead of guessing among aliases.
3. Cross-check consequential mappings with `$cx-ensembl-search` or `$cx-ncbi-gene-search`.
4. Record query, returned IDs, access time, and source URL with `$science-provenance`.

Do not merge genes, isoforms, pseudogenes, or species solely by name similarity. A search hit is identifier evidence, not biological or clinical evidence.

Source basis: [MyGene.info API](https://docs.mygene.info/en/latest/doc/query_service.html).
