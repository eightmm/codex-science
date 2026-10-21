---
name: expression-cell-context
description: "Reconcile gene expression across GTEx, Human Protein Atlas, Bgee, cell atlases, and disease datasets. Use for tissue, cell-type, developmental, baseline-versus-disease, or target-expression questions."
license: MIT
---

# Expression And Cell Context

## Decision contract
Role: conductor for assay-specific expression evidence. Define the gene, species, transcript, tissue ontology, cell type/state, disease condition, assay, comparison, evidence cutoff, and question. Assign separate claims for baseline expression, differential expression, eQTL, protein localization, and functional dependence. Freeze the comparison and primary measurement before inspecting results; record which organism, tissue, and cell-state populations the conclusion is intended to cover.

## Workflow
1. Normalize gene/transcript and tissue/cell identifiers while retaining source labels and ontology IDs. Resolve ambiguity with available GTEx, HPA, or Bgee tools (`science_search_gtex`, `science_search_hpa`, `science_search_bgee`; each legacy tool takes `query` and optional `limit` 1–10). For cellxgene/scRNA workflows or any source without a bundled connector, use its public access route directly when available; connector absence is not source unavailability.
2. Select GTEx for bulk non-diseased tissue, HPA for tissue/cell protein and RNA context, Bgee for healthy ontology-aware expression, and cellxgene/scRNA workflows for cell-level evidence. Query each source separately using verified source parameters; preserve exact query, filters, result scope, pagination, release/update metadata returned, and access time. Do not guess source-specific pagination or field names.
3. Validate species, gene identity, assay, units, normalization, sample/donor counts, batch, tissue composition, and detection thresholds before comparing measurements. Preserve nulls, filtering, and source failures distinctly. Record returned and excluded records with reasons, detect truncation, and bound retries. Treat a query failure or unavailable assay as unavailable evidence.
4. Keep measurements and their uncertainty within assay and source. Compare concordance only after matching tissue, cell state, population, and measurement scale. Track shared samples and propagated portal records as dependencies, not independent confirmation. Report alternative explanations such as composition, assay sensitivity, or state mismatch.

## Outputs
Return normalized entities and assumptions; an assay-context table with source, identifier, tissue/cell context, disease/state, assay, units, normalization, sample counts, estimate and uncertainty, threshold, release/access time, and query reference; records included/excluded with reasons; claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, conflicts, rejected alternatives, applicability limits, and the smallest experiment that would resolve context ambiguity. Save assay-context tables, queries, and hashes with `$science-provenance`; use `$science-review` for cross-assay conclusions.

## Boundaries
Do not infer absence from dropout or portal filtering. Bulk tissue does not identify the expressing cell type; RNA does not guarantee protein abundance or activity. Expression does not establish causal function, target engagement, or clinical actionability. Stop when species, transcript, ontology mapping, or assay scale cannot be reconciled; do not silently repair or merge measurements.
