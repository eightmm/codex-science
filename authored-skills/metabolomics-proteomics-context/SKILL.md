---
name: metabolomics-proteomics-context
description: "Integrate public metabolite, reaction, protein, proteomics, and study evidence. Use for pathway mechanism, biomarker context, multi-omics follow-up, or dataset selection."
license: MIT
---

# Metabolomics And Proteomics Context

## Decision contract
Role: conductor across chemical identity, reaction/pathway, and omics-study lanes. Define the biological question, species, condition, tissue/cell context, evidence cutoff, comparison, and intended claim. Normalize metabolites and chemical forms with ChEBI/PubChem and proteins with UniProt; preserve species, modification state, submitted labels, and stable identifiers. Assign distinct claims for identity, abundance, pathway context, and mechanism.

## Workflow
1. Resolve entities using `science_search_chebi`, `science_search_uniprot`, and source-supported tools for Rhea, Reactome, PRIDE, or ProteomeXchange. Legacy search tools accept `query` and optional `limit` from 1 to 10; do not guess extra arguments. For structured pagination, inspect the source contract before `science_query_source_v2` or `_v3` and record source, parameters, page size, maximum pages, cutoff, and completeness. Use a public direct-access route when a source lacks a connector; connector absence is not evidence that the source is unavailable.
2. Use Rhea/Reactome for reaction/pathway context and PRIDE/ProteomeXchange for public proteomics studies. Treat MetaboLights/HMDB as terms- and availability-gated sources; do not claim live coverage when access is blocked or search is not query-specific. Verify source terms, release/update metadata as reported, access time, and exact query before use.
3. Preserve assay platform, extraction, quantification, normalization, identification confidence, batch, sample unit, release, and file provenance. Reconcile feature-to-entity mappings and chemical forms. Record query serialization, pagination, records returned and excluded with reasons, null/missing semantics, response validation, and truncation. Use bounded retries and keep failures or inaccessible sources distinct from negative evidence.
4. Assess missingness, multiple testing, effect uncertainty, and pathway over-representation assumptions. Deduplicate studies and shared samples across portals. Keep evidence lanes separate until identity and dependency conflicts are resolved; report alternative mappings and analyses that could alter the interpretation.

## Outputs
Return normalized metabolite/protein entities and assumptions; separate evidence maps and reusable dataset candidates; a table with source/query, release, assay, sample unit, estimate/confidence, missingness, and provenance; records included/excluded with reasons; claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, conflicts, uncertainty, rejected alternatives, limitations, and the smallest discriminating next analysis. Save queries, files, transformations, and hashes with `$science-provenance`. Run `$science-review` on cross-omics identity and mechanism claims.

## Boundaries
Spectral match, abundance change, pathway membership, and causal mechanism are distinct claims. Do not infer a chemical identity solely from a feature label, or infer mechanism from pathway membership. Missing assay data, unavailable terms, and null measurements are different states. Stop when entity identity or assay provenance cannot be resolved; do not silently repair mappings or combine incompatible scales.
