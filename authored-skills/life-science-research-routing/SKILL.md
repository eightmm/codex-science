---
name: life-science-research-routing
description: "Route broad or multi-step life-science questions into normalized entities, the smallest independent evidence lanes, reproducible retrieval, conflict reconciliation, and review. Use for target, variant, disease, omics, structure, pharmacology, clinical, or public-dataset research requiring synthesis."
license: MIT
---

# Life-Science Research Routing

## Decision contract
State the decision, deliverable, population or species, evidence cutoff, causal and clinical boundary, acceptance criteria, and non-goals; ask only when an ambiguity changes retrieval or interpretation.
## Workflow
Normalize entities first, create stable claim IDs, call `science_plan_life_science_research`, and select at most four independent lanes; each lane must record its question, sources, exact queries, release or access date, inclusion and exclusion rules, outputs, and limitations.
Use the smallest source set that can discriminate the claims; parallelize only independent lanes, keep shared normalization and synthesis in the coordinator, deduplicate propagated evidence, and reconcile conflicts with `$cx-biomedical-evidence-reconciliation`.
Each lane returns a compact receipt containing claim IDs, retrieved and excluded records, source dependencies, artifact paths, confidence, and unresolved questions; a search-result list is not a completed lane.
## Outputs
Return the decision summary, lane evidence table, claim-evidence matrix, dependency and contradiction log, calibrated confidence, limitations, and the smallest falsifiable next actions; distinguish negative evidence from missing, filtered, stale, or unavailable evidence.
## Boundaries
Label evidence as direct, replicated, suggestive, absent, contradictory, or unavailable; never equate association with causality, prediction with validation, or population evidence with patient-specific advice.
Record query logs, source versions, artifacts, and lane receipts with `$science-provenance`; run `$science-review`, and stop only at a material ambiguity, approval gate, or essential unavailable evidence.
