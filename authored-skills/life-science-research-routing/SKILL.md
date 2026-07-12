---
name: life-science-research-routing
description: "Route broad or multi-step life-science questions into normalized entities, the smallest independent evidence lanes, reproducible retrieval, conflict reconciliation, and review. Use for target, variant, disease, omics, structure, pharmacology, clinical, or public-dataset research requiring synthesis."
license: MIT
---

# Life-Science Research Routing

1. Call `science_plan_life_science_research` with the exact question.
2. Restate the decision, population, evidence cutoff, outputs, and non-goals. Ask only when a missing choice changes retrieval or interpretation.
3. Run `$cx-biomedical-entity-normalization` before evidence retrieval.
4. Select at most four lanes: human genetics/PheWAS, expression/cell context, structure/mechanism, chemistry/pharmacology, clinical/cancer, literature, or public datasets.
5. Use the smallest source set that can answer the question. Parallelize only independent lanes; keep normalization, conflicts, and synthesis in the coordinator.
6. Record query, source release, access time, identifiers, outputs, and hashes with `$science-provenance`.
7. Reconcile evidence with `$cx-biomedical-evidence-reconciliation`; run `$science-review` before delivery.

Return a working conclusion, evidence by lane, conflicts, limitations, and falsifiable next steps. Distinguish direct, replicated, suggestive, absent, contradictory, and unavailable evidence. Never turn population-level research into patient-specific advice.

Source basis: independently designed Codex workflow informed by FAIR provenance and the public API contracts recorded in `docs/LIFE_SCIENCE_RESEARCH_SOURCES.md`.
