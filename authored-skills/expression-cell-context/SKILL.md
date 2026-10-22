---
name: expression-cell-context
description: "Reconcile gene expression across GTEx, Human Protein Atlas, Bgee, cell atlases, and disease datasets. Use for tissue, cell-type, developmental, baseline-versus-disease, or target-expression questions."
license: MIT
---

# Expression And Cell Context

## Decision contract
Role: conductor for assay-specific expression evidence. Define the gene, species, transcript, tissue ontology, cell type/state, disease condition, assay, comparison, evidence cutoff, and question. Assign separate claims for baseline expression, differential expression, eQTL, protein localization, and functional dependence. Freeze the comparison and primary measurement before inspecting results; record which organism, tissue, and cell-state populations the conclusion is intended to cover.

## Reference usage

Read [expression-context-method.md](references/expression-context-method.md) before comparing expression assays, interpreting absence, or making cross-assay claims.

## Workflow

1. **Gates (ask before proceeding).** Confirm the target organism, intended tissue/cell and disease scope, permitted inference, and whether any requested direct-access source or assay would require credentials, substantial downloads, or a new cost; stop and ask before such access. Record the decision and cutoff.
2. Freeze gene/transcript, ontology, assay, comparison, claim classes, primary measurement, evidence cutoff, and target population before looking at results; record the contract and unresolved identity alternatives.
3. Normalize gene/transcript and tissue/cell identifiers while retaining submitted labels, source IDs, and ontology IDs; resolve ambiguity using the available GTEx, HPA, or Bgee tools (`science_search_gtex`, `science_search_hpa`, `science_search_bgee`; each legacy tool takes `query` and optional `limit` 1–10). Record mappings and rejected alternatives.
4. Choose GTEx for bulk non-diseased tissue, HPA for tissue/cell protein and RNA context, Bgee for healthy ontology-aware expression, and cellxgene/scRNA workflows for cell-level evidence; query each source separately with verified parameters. For cellxgene/scRNA or any source without a bundled connector, use its public access route when available; connector absence is not source unavailability. Record rationale and source availability.
5. Retrieve each source separately and preserve exact query, filters, scope, pagination, reported release/update, access time, returned/excluded records and reasons; do not guess fields or pagination. Validate species, gene identity, assay, units, normalization, sample/donor counts, batch, tissue composition, and detection thresholds before comparison. Preserve nulls, filtering, and source failures distinctly; record returned and excluded records with reasons, detect truncation, bound retries, and treat query failure or unavailable assay as unavailable evidence.
6. Assign baseline, differential, eQTL, protein-localization, and functional-dependence claims separately; keep measurements and uncertainty within assay/source. Compare concordance only after matching tissue, cell state, population, and measurement scale. Track shared samples and propagated portal records as dependencies, not independent confirmation; report composition, assay-sensitivity, and state-mismatch alternatives.
7. Check the reference-specific controls and vary mapping, ontology granularity, state, threshold, normalization, and donor aggregation when they can alter the claim; record results and whether status or direction is fragile.
8. Verify the evidence table, claim status (`supported`, `contradicted`, `inconclusive`, `unavailable`), dependencies, uncertainty, conflicts, exclusions, and applicability limits against the frozen contract; preserve failures, save hashes with `$science-provenance`, and route cross-assay interpretation through `$science-review`.

## Outputs

Return normalized gene/transcript and ontology assumptions; assay-context rows with source, identifier, tissue/cell, condition, assay, units, normalization, sample/donor counts, estimate/uncertainty, threshold, release/access time, and query; included/excluded records with reasons; dependency links; conflicts; rejected alternatives; applicability limits; next discriminating experiment; claim register statuses. Schema `expression-context-evidence-v1` requires `schema_id`, `contract`, `entities`, `assay_records`, `claims`, `dependencies`, `uncertainty`, `controls`, `sensitivity`, `exclusions`, `limitations`, and `provenance`. Save queries/tables/hashes with `$science-provenance`; use `$science-review` for cross-assay conclusions.

## Boundaries
Do not infer absence from dropout or portal filtering. Bulk tissue does not identify the expressing cell type; RNA does not guarantee protein abundance or activity. Expression does not establish causal function, target engagement, or clinical actionability. Stop when species, transcript, ontology mapping, or assay scale cannot be reconciled; do not silently repair or merge measurements.
