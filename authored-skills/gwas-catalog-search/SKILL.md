---
name: gwas-catalog-search
description: "Resolve traits and discover curated human genetic association evidence with GWAS Catalog REST API v2. Use for trait, locus, variant, ancestry, study, and locus-to-gene research."
license: MIT
---

# GWAS Catalog Search

## Decision contract
Before searching, record the question, trait and ontology scope, variant/locus or gene, species and assembly, ancestry, evidence cutoff, and whether the requested evidence is curated lead associations or full summary statistics. Define relevant study designs and the distinction between association evidence and a causal claim.

## Workflow
1. Resolve free-text traits with `science_search_gwas_catalog`; retain the selected EFO/MONDO ID and rejected alternatives. This legacy MCP tool accepts `query` (required) and `limit` (1–10, default 5). For paginated structured retrieval, use `science_query_source_v2` with `source="gwas_catalog"` only after checking `science_list_source_contracts`; supported top-level options include `parameters`, `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`.
2. Use the current v2 API and prefer ontology IDs over labels for downstream association queries. Serialize the exact query, filters and pagination; preserve the response and note any truncation or page cap. A failed or partial request is unavailable/incomplete, not a null association.
3. Preserve rsID, assembly, effect allele, p-value, effect estimate, study accession, ancestry, sample size, publication, and access date. Validate allele/build alignment and separate records that do not satisfy the specified trait or population scope.
4. Distinguish curated lead associations from full summary statistics; record dataset-specific terms and release metadata. Record returned and excluded counts and reasons, and distinguish missing fields, explicit nulls, no matching records, and unavailable responses.
5. Compose `$cx-biomedical-entity-normalization`, `$cx-phewas-replication-analysis`, or `$cx-locus-to-gene-prioritization` when synthesis is requested. Capture release/version or last-updated metadata reported by the source; bound retries to transient failures and respect service limits.

Store exact query, association table, source releases, exclusions, response artifact/hash, and access time with `$science-provenance`; run `$science-review` on causal claims. Do not count portal mirrors or multiple reports of the same study as independent evidence.

## Outputs
Return normalized trait and ontology ID, assembly, query ledger, included association records, excluded candidates with reasons, and study/evidence dependencies. For every claim provide a stable ID and status (supported, contradicted, inconclusive, or unavailable), effect estimate and uncertainty when returned, ancestry limitations, conflicts, and the smallest falsifiable next query or analysis.

## Boundaries
Association does not establish causality. Do not pool ancestries, traits, or effect directions without harmonization. Curated lead associations are not a substitute for full summary statistics; missing catalog records are not evidence of no association. Stop when trait identity, build, or allele harmonization is unresolved.

Source basis: [GWAS Catalog API v2](https://www.ebi.ac.uk/gwas/rest/api/v2/docs).
