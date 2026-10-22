---
name: bgee-expression-search
description: "Find ontology-aware healthy wild-type gene expression context with Bgee. Use for cross-species, anatomical, developmental-stage, or baseline-expression questions; not for disease-specific inference or proof of no expression."
license: MIT
---

# Bgee Expression Search

## Decision contract

State the gene or RNA query, organism and taxon, healthy wild-type context, anatomical and developmental scope, evidence cutoff, and whether the question is descriptive baseline expression or a comparison with another source. Use canonical gene identifiers where available; retain symbol, species, and identifier mapping. Bgee expression evidence is context-specific and must not be generalized across orthologs, stages, or anatomy. Define the claim as an observed or ontology-propagated expression call, rank, or score for the stated gene and condition; it is not proof of protein abundance, function, localization, disease relevance, or causality.

## Reference usage

- Read [references/bgee-calls-and-integration.md](references/bgee-calls-and-integration.md) before interpreting a present/absent call, rank, score, or integrated condition. It defines call semantics, evidence dependence, ontology propagation, and release pinning.
- Read [references/bgee-controls-and-sensitivity.md](references/bgee-controls-and-sensitivity.md) before comparing conditions/species, filtering calls, or interpreting missing evidence. It defines controls, threshold and ontology sensitivity, failure detection, and applicability limits.

## Workflow

1. Normalize the gene and species. Check ambiguous symbols against species and gene identifier; preserve unresolved alternatives rather than choosing by name alone. Record mapping evidence and unresolved candidates.
2. Freeze the intended healthy wild-type condition, anatomy, developmental stage, evidence cutoff, and claim class (observed call, propagated call, rank/score, or cross-source comparison). Stop if requested organism or identity remains unresolved; record the boundary.
3. Search with the read-only `science_search_bgee` connector using its `query` and optional `limit` parameters. The bundled search currently resolves human gene records; for another species or expression dimensions, use the Bgee API directly as documented by the [Bgee API guide](https://www.bgee.org/support/tutorial-api), retaining that direct path if the connector cannot answer the question. Do not treat the connector's gene-match lookup as a full expression retrieval.
4. For each selected record, capture query, endpoint/tool, access time, returned gene ID, species, release/version reported by the source, evidence type, anatomical ontology term, developmental stage, and response or artifact hash. Serialize API parameters explicitly; paginate only as the endpoint supports and record pages, returned counts, and any truncation. Validate response shape and identifiers before interpretation.
5. Distinguish directly observed from ontology-propagated evidence and preserve condition, evidence type, call quality, ranks/scores, and contributing experiments when the source exposes them. Map anatomy to UBERON and cell type to CL only when justified; record ontology version and unresolved mappings. Keep absent annotation, no call, absent call, and failed retrieval distinct.
6. Run a known housekeeping-gene and known tissue-restricted-gene sanity check in a compatible species, condition, and release when comparable evidence is available. Record expected and observed patterns; a mismatch triggers gene, ontology, evidence-integration, and coverage review.
7. Vary call-confidence/quality or expression thresholds and defensible tissue or stage groupings. Treat a claim status, rank, or condition interpretation that changes under a reasonable alternative as fragile; record settings and differences.
8. Retry transient failures only a bounded number of times, respect source throttling, and switch to the documented Bgee API only when it can answer the same query. A failed source is unavailable, never a negative finding. Preserve null fields, absent annotations, filtered records, and records excluded for wrong species or context as distinct states.
9. Reconcile healthy baseline evidence with GTEx/HPA or disease datasets using `$cx-expression-cell-context` only after matching gene, organism, anatomical context, assay, and evidence scope. Keep source records and dependencies distinct. Record any unmatched dimension and stop before interpreting it as a direct comparison.

## Outputs

Return one `bgee-expression-evidence-v1` record set with: claim identifier (`claim_id`); claim class and status (`claim_class`, `status`); normalized gene, taxon, and mapping (`gene_id`, `taxon_id`, `identifier_mapping`); condition, anatomy/cell ontology, and developmental stage (`condition`, `anatomy_ontology_id`, `cell_ontology_id`, `developmental_stage`); evidence type and direct/propagated state (`evidence_type`, `propagation_state`); endpoint and serialized query (`endpoint`, `query`); Bgee release and access time (`release`, `accessed_at`); call, quality/confidence, and returned rank/score (`call`, `call_quality`, `rank`, `score`); contributing evidence and record IDs (`experiments`, `record_ids`); exclusions, missingness, and coverage (`exclusions`, `missingness`, `coverage`); uncertainty, controls, sensitivity, applicability, limitations, and smallest falsifiable next query (`uncertainty`, `controls`, `sensitivity`, `applicability_domain`, `limitations`, `next_query`). Save selected records, exclusions, query ledger, and hashes with `$science-provenance`. Use `$science-review` before presenting cross-species or material expression claims.

## Boundaries

- Do not treat absence from one Bgee result as evidence of no expression.
- Do not merge orthologs or developmental stages without an explicit mapping.
- Expression calls are not evidence of protein abundance, function, localization, or disease causality.
- Stop when species or gene identity is unresolved, a necessary source response is malformed/truncated, or the requested evidence cannot be retrieved; retain the result as unavailable or inconclusive rather than substituting an unrelated search.

Source basis: [Bgee API](https://www.bgee.org/support/tutorial-api).
