---
name: mygene-search
description: "Normalize human gene symbols and aliases to Entrez, Ensembl, and taxonomic identifiers with MyGene.info. Use before cross-database gene, target, expression, or variant research when identifiers are incomplete or inconsistent."
license: MIT
---

# MyGene Search

## Decision contract
Record the input symbol, alias, or identifier; requested species (human by default only when specified by the task); and downstream use. Define whether the goal is exact identifier normalization or candidate discovery. Keep each returned gene and taxon as a distinct candidate until identity is resolved.

## Workflow
1. Call `science_search_mygene` with the supplied symbol, alias, or identifier and `limit<=10`. The legacy MCP tool takes required `query` and optional `limit` (1–10, default 5). Direct MyGene.info API retrieval remains available for full query-service operations.
2. Prefer exact human-symbol matches; retain every returned identifier and taxon instead of guessing among aliases. Record all returned candidates and explicitly exclude mismatched taxa or object types with reasons.
3. Cross-check consequential mappings with `$cx-ensembl-search` or `$cx-ncbi-gene-search`. Do not silently choose among multiple exact or near matches; carry the ambiguity into the output or stop if it changes downstream interpretation.
4. Record exact query, endpoint/tool, returned IDs, access time, source URL/release metadata when reported, result counts, exclusions and reasons, and response artifact/hash with `$science-provenance`. Distinguish absent fields, explicit nulls, no results, truncation, and unavailable service. Retry transient errors only within a bounded policy; a failed lookup is not a negative biological result.

The optional normalized connector route is `science_query_source_v2` with `source="mygene"`; top-level fields include `parameters`, `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. Check `science_list_source_contracts` for the source-specific parameter schema before using it. Check material conclusions with `$science-review` when they inform a reported biological claim.

## Outputs
Return normalized input, selected mapping (or all unresolved candidates), taxon, Entrez/Ensembl and other IDs actually returned, query/access metadata, returned and excluded counts, and cross-check results. State claim status (supported, contradicted, inconclusive, unavailable), uncertainty, limitations, and smallest follow-up mapping needed.

## Boundaries
Do not merge genes, isoforms, pseudogenes, or species solely by name similarity. A search hit is identifier evidence, not biological or clinical evidence. Stop before downstream analysis if a consequential mapping remains ambiguous.

Source basis: [MyGene.info API](https://docs.mygene.info/en/latest/doc/query_service.html).
