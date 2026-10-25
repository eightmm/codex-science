---
name: life-science-research-routing
description: "Route broad or multi-step life-science questions into normalized entities, the smallest independent evidence lanes, reproducible retrieval, conflict reconciliation, and review. Use for target, variant, disease, omics, structure, pharmacology, clinical, or public-dataset research requiring synthesis."
license: MIT
---

# Life-Science Research Routing

## Decision contract
State the decision, deliverable, population or species, evidence cutoff, causal and clinical boundary, acceptance criteria, and non-goals; ask only when an ambiguity changes retrieval or interpretation.

## Reference usage
Read [evidence-lanes-and-reconciliation.md](references/evidence-lanes-and-reconciliation.md) when planning more than one lane, interpreting evidence classes, merging records, reconciling conflicts, or calibrating confidence. It defines independence, uncertainty, controls, sensitivity, and when a route cannot support the requested claim.

## Workflow
1. Freeze the decision, deliverable, population/species, evidence cutoff, causal and clinical boundary, acceptance criteria, and non-goals; record any ambiguity that changes retrieval or interpretation.
2. Normalize entities and preserve mapping alternatives before retrieval; record stable claim IDs, claim types, required support, falsifiers, applicability, and evidence status.
3. Call `science_plan_life_science_research` (if the MCP tool is unavailable, run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/plan_life_science_research.py" QUESTION`) and select no more than four lanes that can answer distinct, material questions; record each lane's question, claims, rationale, and stop rule.
4. Choose the smallest source set that can discriminate each claim; pin source/version/access date and record exact queries, inclusion/exclusion rules, pagination, and licensing or access constraints.
5. Execute only independent lanes in parallel; keep shared normalization, dependency grouping, and synthesis centralized; record source IDs, retrieved and excluded records, artifacts, and failures.
6. Group shared cohorts, propagated records, source portals, templates, models, and transformations before counting support; record why each evidence item is or is not independent.
7. Assign evidence class and uncertainty to each claim, distinguishing direct, replicated, suggestive, absent (negative evidence from a prespecified search), contradictory, and unavailable; keep absent evidence separate from missing, filtered, stale, or unavailable evidence, and record limitations and the strongest counterevidence.
8. Run domain-appropriate positive/negative controls and sanity checks; vary lane inclusion, source release, entity resolution, evidence cutoff, and dependency assumptions, recording any status or confidence change.
9. Route cross-lane conflicts to `$cx-biomedical-evidence-reconciliation` for reconciliation at matched population, assay, endpoint, and time scale; record its receipt and downgrade claims when findings depend on fragile assumptions or fall outside the applicability domain.
10. Verify claim-evidence links, lane receipts, and stop criteria; emit `life-science-evidence-routing-v1`, preserve query logs and artifacts with `$science-provenance`, and run `$science-review` before presenting material synthesis.

## Outputs
Emit one `life-science-evidence-routing-v1` record with required fields: `decision`, `scope`, `evidence_cutoff`, `claims`, `lanes`, the claim-evidence matrix (`claim_evidence_matrix`), `dependency_groups`, `contradictions`, `controls`, `sensitivity`, `confidence`, `limitations`, `next_actions`, and `provenance`. Keep absent evidence distinct from missing, filtered, stale, and unavailable results. Each lane receipt records its question, claim IDs, pinned sources and queries, included/excluded records, artifacts, dependencies, limitations, confidence, and unresolved questions.

## Boundaries
Label evidence as direct, replicated, suggestive, absent (negative evidence from a prespecified search), contradictory, or unavailable; distinguish absent evidence from missing, filtered, stale, or unavailable evidence. Never equate association with causality, prediction with validation, or population evidence with patient-specific advice. Record query logs, source versions, artifacts, and lane receipts with `$science-provenance`; run `$science-review`, and stop only at a material ambiguity, approval gate, or essential unavailable evidence. A routed synthesis does not itself validate clinical decisions, causal effects, or generalization beyond the observed applicability domain.
