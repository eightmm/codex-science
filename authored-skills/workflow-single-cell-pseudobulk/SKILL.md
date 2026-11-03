---
name: workflow-single-cell-pseudobulk
description: "Compare single-cell RNA counts between conditions using donor or biological-sample pseudobulk units. Use for scRNA-seq condition contrasts with supplied cell labels; exclude cell-as-replicate tests, trajectory ordering, fate, causal mechanisms and clinical conclusions."
license: MIT
---

# Single-cell Pseudobulk

Role: conductor composed with an offline reference analyzer. Output states statistical evidence only. Synthetic fixtures establish software behavior, never biological validity.

## Decision contract

Declare the exact question, organism, tissue, population, condition contrast, assay, evidence cutoff, claim IDs, permitted descriptive or associational inference, baseline, uncertainty rule and falsifier. Reuse `$cx-public-omics-dataset-discovery` for dataset fitness and `$cx-expression-cell-context` for identifier and assay context. Missing evidence is `unavailable`; do not reconstruct absent donor, batch, label or annotation records.

Freeze and hash donor or biological sample IDs, condition, batch, chemistry, genome and annotation versions, identifier namespace, cell-label provenance, minimum independent donors, cell and gene QC thresholds, aggregation rule, tested genes and cell types, model and multiplicity family before seeing outcomes. The reference minimum of three donors per condition is a fixture control, never a power calculation. Multiple samples from one donor cannot increase the independent replicate count. Independent unpaired donors nested in condition are permitted; a donor fixed effect nested in condition, repeated donors, or perfectly confounded batch or chemistry stops this reference route.

The deliverable is unreviewed statistical evidence. Acceptance requires recovery of the planted donor-level association while the balanced planted batch effect and null gene remain nonsignificant, with failed cell controls and underfilled groups retained as explicit exclusions. A real study additionally needs a design-specific power assessment, normalization diagnostics, batch and composition sensitivity, and independent method review. Stop for unavailable essential inputs or interpretation-changing ambiguity; infer reversible presentation choices.

## Reference usage

Read [the reference index](references/index.json) and [stage and record contracts](references/stages.md) before admission, computation, validation or handoff. Use [the plan template](references/plan.json) without changing existing manifest or checkpoint shapes. Record materially controlling reference paths and hashes in the existing `reference-use-ledger`. These instructions are procedure, not scientific evidence.

## Workflow

1. **01-design — declare and freeze.** Admit immutable path-plus-SHA-256 inputs and preserve biological unit dependencies. Record supplied marker or reference evidence for every cell type. Check genome, annotation and identifier identities against counts, labels and gene sets. Freeze design and pre-result controls. External or independent labels never replace source evidence or justify aliasing study inputs or outputs.
2. **02-qc — cell and gene controls.** Use declared minimum genes and counts per cell, maximum mitochondrial fraction and supplied boolean doublet calls. Do not infer doublets. Retain measured failures and exclusions. Require the declared minimum retained cells per biological unit and cell type. Apply the frozen gene-detection threshold to pseudobulk units before testing; record every excluded gene. Missing data never become negative evidence.
3. **03-aggregation — biological units.** Aggregate raw counts by donor or biological sample and cell type using the frozen rule. The default is summation; a declared mean route has the same CPM ratios and preserves the recorded rule. Compare the declared included-unit list against recomputed QC eligibility; refuse silently included underfilled groups. Keep independent donor counts separate from cell counts.
4. **04-comparison — bounded association.** Run the CPU-only offline reference on log2(CPM+1) pseudobulk units, using a two-sided Welch test per admitted gene and BH over all tested gene/cell-type pairs. Refuse insufficient donors, zero variance, confounding, missing correction and post-test selective correction. A cell never becomes a replicate. An unlabelled post-result QC or aggregation change, or label/test-gene overlap, is refused; an exploratory revision preserves the original freeze and remains suggestive. edgeR and DESeq2 pseudobulk are separately gated extension points; this pack never installs or executes them.
5. **05-handoff — preserve and review.** Retain exclusions, nulls, failed controls, dependencies, conflicts, unavailable evidence, limitations, rejected alternatives and the smallest falsifiable next measurement. Register domain records as ordinary artifacts with `$science-provenance` and create separate entries in the existing claim register. Hand off frozen identities, outputs, logs and claims to `$science-review` in record, source and method modes. Rigor classification, review independence and receipt registration remain coordinator responsibilities.

Use one coordinator checkpoint per run and advance these five ordered stage IDs on it. The reference creates no checkpoint, manifest, execution engine or review receipt. Correct an identified input problem before retrying; preserve the failed evidence and create a new revision. Never weaken a control to obtain a passing result.

## Outputs

Pack-local schemas: `single-cell-pseudobulk-pack-v1`, `single-cell-pseudobulk-design-v1`, `single-cell-pseudobulk-counts-v1`, `single-cell-pseudobulk-gene-sets-v1`, `single-cell-pseudobulk-labels-v1`, `single-cell-pseudobulk-evidence-v1` and `single-cell-pseudobulk-result-v1`. Exact fields and the public CLI are in the stages reference. They add no fields to existing manifests, receipts or claim registers.

Return normalized assumptions, hashed inputs and frozen specification, all measured cell QC, exclusions with thresholds, pseudobulk counts and biological denominators, all tested effects and p/q values, unavailable review, uncertainty and limitations. The coordinator separately records supported, contradicted, inconclusive and unavailable conclusions using existing claim semantics and preserves conflicts and dependencies.

The redistributable synthetic example is `examples/workflow-single-cell-pseudobulk/pack.json`; its expected result and 24 seeded refusals are checked by the focused tests. Frozen questions, acceptance criteria and CPU budgets are in `benchmarks/workflow-single-cell-pseudobulk/tasks.json`. L4 means fixture acceptance tested through unittest discovery, never real-cohort validation.

## Boundaries

Refuse association stated as binding, affinity, inhibition, activation, causality, mechanism, therapeutic or clinical action, efficacy, trajectory ordering or fate. Numerical agreement never establishes physical or clinical validity. Review approval never establishes truth. Positive claims cannot cite review approval or computed agreement, regardless of the claim's kind or the cited record's other label. The stages reference gives the conservative wording filter; independent review must still assess meaning and unlisted paraphrases.

Refuse missing label evidence, circular label features without exploration, incompatible identifiers or annotations, unlabelled rule changes, silently included low-cell groups, pseudoreplication, confounding, too few biological replicates, degenerate inputs and incomplete multiplicity control. Preserve failures and negative results; absent records stay `unavailable`. Hashes bind content and cannot independently establish when a declaration was frozen or whether an asserted source was truly independent.

This route uses supplied synthetic fixtures, standard-library computation and local CPU only. No network, download, GPU, remote job, external executable or installation is authorized. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice. Do not add a gate at every stage of an admitted offline run. No result establishes expressing-cell function, protein activity, biological mechanism, physical validity or clinical efficacy.
