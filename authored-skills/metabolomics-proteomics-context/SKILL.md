---
name: metabolomics-proteomics-context
description: "Integrate public metabolite, reaction, protein, proteomics, and study evidence. Use for pathway mechanism, biomarker context, multi-omics follow-up, or dataset selection."
license: MIT
---

# Metabolomics And Proteomics Context

## Decision contract
Role: conductor across chemical identity, reaction/pathway, and omics-study lanes. Define the biological question, species, condition, tissue/cell context, evidence cutoff, comparison, and intended claim. Normalize metabolites and chemical forms with ChEBI/PubChem and proteins with UniProt; preserve species, modification state, submitted labels, and stable identifiers. Assign distinct claims for identity, abundance, pathway context, and mechanism.

## Reference usage

Read [multiomics-context-method.md](references/multiomics-context-method.md) before integrating claims or interpreting cross-study evidence.

## Workflow

1. **Gates (ask before proceeding).** Confirm species, condition, sample context, claim scope, and whether requested data access entails credentials, large downloads, or cost; stop and ask before those actions. Record the decision and cutoff.
2. Freeze the biological question, comparison, evidence cutoff, intended claim classes, sample unit, and primary outcome; record the contract and unresolved alternatives.
3. Resolve entities using `science_search_chebi`, `science_search_uniprot`, and source-supported tools for Rhea, Reactome, PRIDE, or ProteomeXchange. Preserve species, modifications, submitted labels, and stable IDs. Legacy search tools accept `query` and optional `limit` from 1 to 10; do not guess extra arguments. For structured pagination, record the source, parameters, page size, maximum pages, cutoff, and completeness. Use a public direct-access route when a source lacks a connector; connector absence is not evidence that the source is unavailable.
4. Select Rhea/Reactome for reaction/pathway context and PRIDE/ProteomeXchange for proteomics studies; use MetaboLights/HMDB only where terms and query-specific access permit. Do not claim live coverage when access is blocked or search is not query-specific. Inspect source contracts before `science_query_source_v2` or `_v3`; verify source terms, reported release/update metadata, access time, and exact query before use; record lane rationale and access status.
5. Preserve assay platform, extraction, quantification, normalization, identification confidence, batch, sample unit, release, and file provenance. Reconcile feature-to-entity mappings and chemical forms. Record query serialization, pagination, records returned and excluded with reasons, null/missing semantics, response validation, and truncation. Use bounded retries and keep failures or inaccessible sources distinct from negative evidence. Retain exact query, page limits, cutoff, completeness, access time, files and hashes.
6. Separate feature detection, chemical identity, abundance, pathway context, dataset suitability, and mechanism claims. Assess missingness, multiple testing, effect uncertainty, peptide/protein inference, pathway over-representation assumptions, and annotation confidence. Keep evidence lanes separate until identity and dependency conflicts are resolved; deduplicate studies and shared samples across portals and map them as dependencies. Report alternative mappings and analyses that could alter interpretation.
7. Check controls for standards/blanks/QC, mass/adduct/retention or fragmentation, peptide inference/FDR, sample labels, batch and pathway universe. Vary plausible mappings, cutoffs, missingness policy, exclusions, normalization, and pathway background; record sensitivity and fragility.
8. Verify claim status (`supported`, `contradicted`, `inconclusive`, `unavailable`), evidence maps, uncertainty, dependency links, conflicts, exclusions, and limitations against the frozen contract; preserve inaccessible/null/failed outcomes, save provenance with `$science-provenance`, and send cross-omics identity or mechanism claims through `$science-review`.

## Outputs

Return normalized metabolite/protein entities and assumptions; separate evidence maps and dataset candidates; source/query/release/assay/sample-unit/estimate/confidence/missingness/provenance rows; included/excluded records with reasons; dependency links; conflicts; uncertainty; rejected alternatives; limitations; next discriminating analysis; claim register statuses. Schema `multiomics-context-evidence-v1` requires `schema_id`, `contract`, `entities`, `evidence_maps`, `dataset_candidates`, `claims`, `dependencies`, `uncertainty`, `controls`, `sensitivity`, `exclusions`, `limitations`, and `provenance`. Save queries/files/transforms/hashes with `$science-provenance`; use `$science-review` on cross-omics identity and mechanism claims.

## Boundaries
Spectral match, abundance change, pathway membership, and causal mechanism are distinct claims. Do not infer a chemical identity solely from a feature label, or infer mechanism from pathway membership. Missing assay data, unavailable terms, and null measurements are different states. Stop when entity identity or assay provenance cannot be resolved; do not silently repair mappings or combine incompatible scales.
