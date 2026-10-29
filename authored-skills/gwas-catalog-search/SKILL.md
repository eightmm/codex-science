---
name: gwas-catalog-search
description: "Resolve traits and discover curated human genetic association evidence with GWAS Catalog REST API v2. Use for trait, locus, variant, ancestry, study, and locus-to-gene research."
license: MIT
---

# GWAS Catalog Search

## Decision contract

Before searching, record the question, trait and ontology scope, variant/locus
or gene, species and genome assembly, ancestry, evidence cutoff, and whether
the requested evidence is curated lead associations or full summary statistics.
Define relevant study designs and distinguish a reported association from a
causal claim. Assign claim status as supported, contradicted, inconclusive, or
unavailable under the GWAS reference criteria.

## Reference usage

Read [references/gwas-association-evidence.md](references/gwas-association-evidence.md)
before resolving traits, harmonizing variants or alleles, comparing studies or
ancestries, or interpreting association claims. It defines curated-record
semantics, cohort dependencies, uncertainty, controls, sensitivity, and the
catalog's applicability domain.

## Workflow

1. Resolve free-text traits with `science_search_gwas_catalog`; retain the
   selected EFO/MONDO ID and rejected alternatives. Use this legacy MCP tool
   with `query` (required) and `limit` (1–10, default 5). Record the chosen
   concept and why it matches the intended phenotype.
2. For bounded normalized retrieval, use `science_query_source_v2` with
   `source="gwas_catalog"`. `science_query_source_v2` requires `source` and
   `parameters`; optional top-level fields are `operation`, `page_size`,
   `max_pages`, and `include_snapshot`. Current v2 legacy sources accept
   required `parameters.query` (a non-empty string) and optional
   `parameters.limit` (an integer from 1 to 10).
   `science_list_source_contracts` lists available sources and operations; it
   does not return a parameter schema. Current v2 routes refuse
   `evidence_cutoff`; record the cutoff in your protocol and apply it to
   returned record dates yourself, treating missing dates as unresolved. The
   v2 adapter has no cursor pagination and returns at most 10 records. Use the
   current GWAS Catalog v2 API for broader retrieval, prefer ontology IDs for
   downstream queries, and record the exact route and parameters. If trait
   identity is ambiguous, stop and return alternatives instead of choosing
   silently.
3. Define evidence scope before retrieval: association endpoint, study or
   ancestry criteria, build, evidence cutoff, and whether lead associations or
   summary statistics are required. Record dataset-specific terms, excluded
   designs, and why the available catalog endpoint can or cannot answer the
   question.
4. Serialize exact query, filters, pagination, and cutoff. Preserve the
   response and note truncation or page caps. A failed or partial request is
   unavailable or incomplete, not a null association; bound retries to
   transient failures and respect service limits. Record page status and
   source-reported release/last-updated metadata when returned.
5. Preserve rsID, assembly, effect allele, p-value, effect estimate, study
   accession, ancestry, sample size, publication, and access date when
   available. Validate build and allele alignment; distinguish absent,
   explicit null, and unavailable fields. Record returned and excluded counts,
   candidates, and reasons when trait/population scope does not match.
6. Separate curated lead associations from full summary statistics. Classify
   each statement using the reference: report a catalog association as such;
   do not infer causality, cross-population portability, or locus-to-gene
   mechanism from a lead record alone. Record study and cohort dependencies.
7. Run the domain controls and sensitivity checks from the reference. If
   plausible trait mapping, build, ancestry, cutoff, or query choices change
   inclusion or direction materially, mark the claim inconclusive and retain
   each comparison.
8. For synthesis, compose `$cx-biomedical-entity-normalization`,
   `$cx-phewas-replication-analysis`, or `$cx-locus-to-gene-prioritization`
   as appropriate. Store exact query, association table, source releases,
   exclusions, response artifact/hash, and access time with
   `$science-provenance`; run `$science-review` on causal claims.

## Outputs

Return one `gwas-association-evidence-v1` record with required fields:
`question`, `normalized_trait`, `ontology_id`, `species`, `assembly`,
`ancestry_scope`, `evidence_scope`, `evidence_cutoff`, `query_ledger`,
`included_associations`, `excluded_candidates`, `claim_register`,
`study_dependencies`, `source_release_metadata`, `missingness`, `uncertainty`,
`limitations`, `next_falsifiable_action`, `artifact_paths`, and
`artifact_hashes`. Each claim has a stable ID and status: supported,
contradicted, inconclusive, or unavailable. Each association row preserves
returned variant, allele, effect, significance, study, population, and source
fields without filling unavailable values. For every claim, include the effect
estimate and uncertainty when returned, ancestry limitations, conflicts, and
the smallest falsifiable next query or analysis.

## Boundaries

- Association does not establish causality. Do not pool ancestries, traits, or
  effect directions without harmonization.
- Curated lead associations are not a substitute for full summary statistics;
  missing catalog records are not evidence of no association.
- Stop when trait identity, build, or allele harmonization is unresolved.
- Do not count portal mirrors or multiple reports of the same study as
  independent evidence.

Use `$science-review` for causal claims and preserve all query and response
provenance with `$science-provenance`.

Source basis: [GWAS Catalog API v2](https://www.ebi.ac.uk/gwas/rest/api/v2/docs).
