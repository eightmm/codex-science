---
name: workflow-microbiome-composition
description: "Compare microbial community composition between two conditions from supplied sample-by-taxon integer counts. Use for 16S or shotgun taxon tables, CLR, diversity and stratified PERMANOVA; exclude sequence processing, absolute microbial load and medical decisions."
license: MIT
---

# Microbiome Composition

Role: conductor with a bounded offline reference analyzer. Output states statistical composition evidence only. All checked-in inputs, results and negative cases are synthetic fixtures.

## Decision contract

Before opening the count table, freeze and hash the question, biological population, assay, evidence cutoff, two-condition contrast, biological unit, batch, extraction batch and sequencing run variables, minimum read depth, prevalence filter, zero-handling rule and pseudocount, Shannon and Simpson indices, Aitchison distance, permutation strata, permutation count and seed, FDR alpha and minimum independent subjects per group. Record claim IDs, baseline, uncertainty rule, dependencies and a falsifier. A content hash establishes identity, never historical preregistration.

This route starts with already-counted taxon counts from 16S or shotgun profiling. It does no sequence processing, taxonomic assignment, absolute quantification, paired or repeated-subject modeling, covariate adjustment, diagnosis or intervention selection. The sample-level biological subject is the independent unit. Stop for missing essential metadata or an interpretation-changing design ambiguity; choose reversible presentation details internally.

Acceptance means reproducing the planted synthetic relative-composition shift, hand-calculated CLR/diversity/Welch/BH/PERMANOVA quantities, explicit blank and low-depth exclusions, and the seeded refusals. It establishes software behavior only. A small significant fixture does not establish power, biological importance, physical validity or clinical validity.

## Reference usage

Read [the index](references/index.json) and [stages and record contracts](references/stages.md) before freezing a design, admitting counts, transforming values, testing taxa, validating or handing off claims. Reuse [the existing manifest step shape](references/plan.json). Record controlling reference paths and hashes in the existing `reference-use-ledger`; these references are procedure, never scientific evidence.

## Workflow

1. **01-design — freeze before counts.** Use `$cx-statistical-decision-analysis` for the decision threshold and uncertainty framing. Write and hash the complete design before reading outcomes. Preserve revisions and rejected alternatives. Unlabelled pseudocount, prevalence-filter or distance changes are refused. Labelled pseudocount and prevalence sensitivity remain exploratory and at most suggestive; other methods require a separate implementation and review.
2. **02-qc — preserve identity and controls.** Admit unique sample IDs and taxon IDs with integer counts and unique biological-subject IDs. Verify each path-plus-hash identity. Compute raw depth for every sample; list and exclude biological samples below the frozen threshold. Keep negative extraction blanks visible regardless of depth. Refuse missing controls, technical pseudoreplication and condition perfectly confounded with batch, extraction batch or sequencing run. Do not repair identifiers or invent missing data.
3. **03-composition — relative information only.** Apply the frozen prevalence filter among retained biological samples. Conservatively exclude every taxon detected in any blank from testing, retaining it as untested-control. On the same remaining taxon table, compute additive-pseudocount CLR, raw-count Shannon and Simpson 1-D, and Euclidean CLR (Aitchison) distance. Use the frozen seed and number of permutations for a two-condition PERMANOVA pseudo-F; exchange condition labels only within the joint frozen strata. Stop for no exchangeable strata, zero variation or failed draws; never silently reduce the permutation denominator.
4. **04-taxa — full-family correction.** Compare CLR values with a two-sided Welch t-test per retained taxon, then Benjamini-Hochberg across every tested taxon. Below-prevalence taxa remain untested-prevalence; control taxa remain untested-control with null p/q. Refuse zero-variance or insufficient-unit inputs. Retain complete denominators, effect sizes, nulls, exclusions and negative results; a zero count is never proof of absence.
5. **05-handoff — independent review.** Run `python scripts/validate_microbiome_composition_pack.py examples/workflow-microbiome-composition/pack.json` on the synthetic fixture first. Register local domain records as ordinary artifacts with `$science-provenance` and use separate entries in the existing claim register. Hand the design, table, QC, full results, execution/environment identities, hashes, reference-use ledger, dependencies, contradictions, failed controls and limitations to `$science-review` in record, source and method modes. Rigor classification and independent review stay coordinator-owned; this pack never marks its own output reviewed.

Use one coordinator checkpoint and these five ordered stage IDs per run. This pack adds no execution engine, manifests or receipts. Correct a specific defect before one bounded retry and retain failed revisions. Never weaken controls or remove a null to pass validation.

## Outputs

Local schemas: `microbiome-pack-v1`, `microbiome-design-v1`, `microbiome-count-table-v1`, `microbiome-report-v1`, `microbiome-evidence-v1`, `microbiome-result-v1`, `microbiome-negative-cases-v1`. They add no fields to global manifests, receipts, claim registers or MCP contracts. Exact fields, resource limits and the one-argument read-only CLI are in the stages reference.

Return normalized assumptions and immutable identities, per-sample depths, low-depth and control exclusions, filtered taxon identities, CLR and diversity values, Aitchison distances, seeded stratified permutation results, per-taxon Welch values and full-family q-values, claims, rejected alternatives, uncertainty, applicability limits and the smallest falsifiable next measurement. The coordinator separately records supported, contradicted, inconclusive and unavailable interpretations using existing claim semantics. Review remains unavailable until an independent receipt exists.

Redistributable synthetic fixtures and expected artifacts live in `examples/workflow-microbiome-composition/`; frozen questions and CPU budgets live in `benchmarks/workflow-microbiome-composition/tasks.json`. L4 means offline fixture acceptance via `tests/test_workflow_microbiome_pack.py`, never real-cohort or clinical validation.

## Boundaries

Refuse relative abundance described as absolute abundance or microbial load, zero counts described as proof of absence, negative-control taxa as findings, association described as causality, dysbiosis causing disease, therapeutic targets or clinical biomarkers. Labels never override claim text. Positive claims cannot cite review approval or computed/numerical agreement, checking both record kind and result. Numerical agreement is never physical or clinical validity; review approval is never truth.

Any unavailable citation forces unavailable claim status, including mixed evidence lists and negative claims. Empty evidence is unavailable, never negative evidence. Unavailable text cannot assert positive evidence. Replicated is refused because this reference admits one synthetic study. External, independent and preregistered evidence cannot alias this study's input/output paths or hashes. The incomplete conservative English wording gate is specified in the stages reference; human review must inspect paraphrases and other languages.

Only offline local CPU fixtures and standard-library computation are supported. No installation, transfer, network, GPU, remote or heavy compute is performed. Human gates apply before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices; admitted offline stages need no repeated approval. Failed controls and negative results remain visible.
