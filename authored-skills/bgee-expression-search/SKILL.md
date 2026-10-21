---
name: bgee-expression-search
description: "Find ontology-aware healthy wild-type gene expression context with Bgee. Use for cross-species, anatomical, developmental-stage, or baseline-expression questions; not for disease-specific inference or proof of no expression."
license: MIT
---

# Bgee Expression Search

## Decision contract

State the gene or RNA query, organism and taxon, healthy wild-type context, anatomical and developmental scope, evidence cutoff, and whether the question is descriptive baseline expression or a comparison with another source. Use canonical gene identifiers where available; retain symbol, species, and identifier mapping. Bgee expression evidence is context-specific and must not be generalized across orthologs, stages, or anatomy.

## Workflow

1. Normalize the gene and species. Check ambiguous symbols against species and gene identifier; preserve unresolved alternatives rather than choosing by name alone.
2. Search with the read-only `science_search_bgee` connector using its `query` and optional `limit` parameters. The bundled search currently resolves human gene records; for another species or expression dimensions, use the Bgee API directly as documented by the [Bgee API guide](https://www.bgee.org/support/tutorial-api), retaining that direct path if the connector cannot answer the question. Do not treat the connector's gene-match lookup as a full expression retrieval.
3. For each selected record, capture query, endpoint/tool, access time, returned gene ID, species, release/version reported by the source, evidence type, anatomical ontology term, developmental stage, and response or artifact hash. Serialize API parameters explicitly; paginate only as the endpoint supports and record pages, returned counts, and any truncation. Validate response shape and identifiers before interpretation.
4. Retry transient failures only a bounded number of times, respect source throttling, and switch to the documented Bgee API only when it can answer the same query. A failed source is unavailable, never a negative finding. Preserve null fields, absent annotations, filtered records, and records excluded for wrong species or context as distinct states.
5. Reconcile healthy baseline evidence with GTEx/HPA or disease datasets using `$cx-expression-cell-context` only after matching gene, organism, anatomical context, assay, and evidence scope. Keep source records and dependencies distinct.

## Outputs

Return normalized gene and taxon, query and source provenance, records returned and excluded with reasons, and a machine-readable evidence table containing gene ID, evidence type, anatomy term/ontology, developmental stage, release, source record ID, and missingness. Assign claim IDs and status `supported`, `contradicted`, `inconclusive`, or `unavailable`; state uncertainty, applicability, limitations, and the smallest falsifiable next query. Save selected records, exclusions, query ledger, and hashes with `$science-provenance`. Use `$science-review` before presenting cross-species or material expression claims.

## Boundaries

Do not treat absence from one Bgee result as evidence of no expression. Do not merge orthologs or developmental stages without an explicit mapping. Expression calls are not evidence of protein abundance, function, or disease causality. Stop when species or gene identity is unresolved, a necessary source response is malformed/truncated, or the requested evidence cannot be retrieved; retain the result as unavailable or inconclusive rather than substituting an unrelated search.

Source basis: [Bgee API](https://www.bgee.org/support/tutorial-api).
