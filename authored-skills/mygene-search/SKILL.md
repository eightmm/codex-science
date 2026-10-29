---
name: mygene-search
description: "Normalize human gene symbols and aliases to Entrez, Ensembl, and taxonomic identifiers with MyGene.info. Use before cross-database gene, target, expression, or variant research when identifiers are incomplete or inconsistent."
license: MIT
---

# MyGene Search

## Decision contract

Record the input symbol, alias, or identifier; requested species (human by default only when specified by the task); and downstream use. Define whether the goal is exact identifier normalization or candidate discovery. Keep each returned gene and taxon as a distinct candidate until identity is resolved. Distinguish an aggregated annotation record from experimental evidence of gene function.

## Reference usage

Read [MyGene identity and aggregation evidence](references/gene-identity-evidence.md) before interpreting a query hit, choosing among identifiers, treating cross-references as confirmation, comparing species/synonym queries, or assigning claim status. It defines the provenance and dependency limits of aggregated fields and the domain-specific controls and sensitivity checks; it is not itself target-gene evidence.

## Workflow

1. Classify the request as exact identifier normalization or candidate discovery; record downstream use and require species (use human only when the task specifies it). Stop if a required species choice is unresolved.
2. Call `science_search_mygene` with the supplied symbol, alias, or identifier and `limit<=10`. The legacy MCP tool takes required `query` and optional `limit` (1–10, default 5). Direct MyGene.info API retrieval remains available for full query-service operations. Choose a route only if its operation fits the request and record exact request, tool/endpoint, and access time.
3. Prefer an exact species-matched symbol or stable-identifier match, while retaining every returned ID and taxon; do not silently choose among exact or near matches. Record all candidates and exclusions for mismatched taxa or object types with reasons.
4. Check aliases, retired or merged symbols, and stable identifier versions against the source records where available; retain candidate collisions and record which identifiers were actually returned. Pin the release/update metadata reported by MyGene and the relevant Ensembl/NCBI annotation release and assembly when cross-checking; never infer unreported versions.
5. Interpret MyGene output as an aggregated annotation/mapping record. MyGene may combine Ensembl, NCBI and other source annotations, so matching IDs or fields propagated through this aggregator and those upstream sources are not independent confirmations. Classify function claims only from cited experimental evidence, and record source dependencies and any independent evidence separately.
6. Cross-check consequential mappings with `$cx-ensembl-search` or `$cx-ncbi-gene-search`. Compare species, stable IDs, assembly, release, transcript accession/version and RefSeq/MANE basis when relevant. Report orthology evidence type and one-to-many relationships when returned; homology or aggregator cross-reference is not functional equivalence. Record agreement, conflict, and dependency.
7. Use a known gene with a stable ID as a positive control and an ambiguous alias as an ambiguity control. Verify the positive control maps to the expected species and object and that the ambiguous alias yields candidate ambiguity or an explicit disambiguation. Resolve unexpected controls before interpreting the target; record expected/observed outcomes.
8. Vary species and synonym handling, and where material vary the source release or assembly used by cross-checks. Treat the result as fragile if selected gene, taxon, transcript or downstream interpretation changes; record query variants, returned candidates and effect on the claim.
9. Record exact query, endpoint/tool, returned IDs, access time, source URL/release metadata when reported, result counts, exclusions/reasons, and response artifact/hash with `$science-provenance`. Distinguish absent fields, explicit nulls, no results, truncation, and unavailable service; retry transient errors only within a bounded policy because a failed lookup is not a negative biological result. Assign claim status (supported, contradicted, inconclusive, unavailable), uncertainty, limitations, and smallest follow-up mapping needed; check material conclusions with `$science-review` when they inform a reported biological claim. Verify identity, dependencies, controls, and provenance before returning.

The optional normalized connector route uses `source="mygene"`. `science_query_source_v2` requires `source` and `parameters`; optional top-level fields are `operation`, `page_size`, `max_pages`, and `include_snapshot`. Current v2 legacy sources accept required `parameters.query` (a non-empty string) and optional `parameters.limit` (an integer from 1 to 10). `science_list_source_contracts` lists available sources and operations; it does not return a parameter schema. Current v2 routes refuse `evidence_cutoff`; record the cutoff in your protocol and apply it to returned record dates yourself, treating missing dates as unresolved.

## Outputs

Return one `mygene-mapping-evidence-v1` object with these required fields:

- Claim identifier (`claim_id`), claim status (`claim_status`: supported, contradicted, inconclusive, or unavailable), and claim class (`claim_class`).
- Normalized input (`normalized_input`), exact query (`query`), selected mapping or unresolved candidate set (`mapping_or_candidates`), and species/taxon (`species_taxon`).
- Entrez, Ensembl, and other IDs actually returned (`returned_ids`), identifier versions (`identifier_versions`), and source/release metadata when available (`source_release`).
- Assembly and transcript/RefSeq/MANE selection when relevant (`assembly`, `transcript_selection`).
- Returned/excluded counts and reasons (`returned_count`, `excluded_count`, `exclusions`), cross-check results (`cross_checks`), and source dependency/independence notes (`source_dependencies`).
- Positive and ambiguity control outcomes (`controls`), uncertainty (`uncertainty`), and sensitivity results (`sensitivity`).
- Applicability limitation (`applicability_limit`), endpoint/tool and access time (`endpoint_or_tool`, `access_time`), response artifact/hash (`response_artifact`), and smallest follow-up mapping (`next_lookup`).

## Boundaries

Do not merge genes, isoforms, pseudogenes, or species solely by name similarity. A search hit is identifier evidence, not biological or clinical evidence. MyGene and its upstream sources are not independent when records are propagated through the aggregator. Stop before downstream analysis if a consequential mapping remains ambiguous or an empty result has not been distinguished from service failure.

Source basis: [MyGene.info API](https://docs.mygene.info/en/latest/doc/query_service.html).
