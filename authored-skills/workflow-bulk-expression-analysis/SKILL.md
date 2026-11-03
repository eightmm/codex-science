---
name: workflow-bulk-expression-analysis
description: "Conduct a fixed-stage bulk expression differential analysis from an admitted dataset and declared design through QC, a frozen contrast, multiplicity-controlled testing, supplied gene-set enrichment, and independent review handoff. Use for bulk RNA expression association questions; not single-cell analysis, causal mechanisms, clinical inference, or automatic installation and execution of external tools."
license: MIT
---

# Bulk Expression Analysis Workflow

Role: conductor composed with an offline reference analyzer. Output states statistical evidence only. The checked-in synthetic fixtures test software behavior, not biological validity.

## Decision contract

Declare the exact question, organism, tissue and cell context, assay, sample unit, population, evidence cutoff, permitted descriptive or associational claims, and claim IDs. Use `$cx-public-omics-dataset-discovery` for dataset fitness and `$cx-expression-cell-context` for assay and identifier interpretation. Reuse their admitted records; the reference runner does not query sources.

Record groups, independent biological replicates, batch, covariates, genome version, annotation version and identifier namespace. Technical replicates never increase biological sample size. Fix the minimum replicates, library-size and detection thresholds, sample-outlier rule, contrast orientation, model, complete testing family, BH alpha, enrichment alpha and explicit background universe before examining outcomes. Hash the specification before computing any test statistic. The default fixture minimum is three replicates per group; this is a software threshold, not a power calculation.

The deliverable is an unreviewed statistical evidence bundle. A planted synthetic effect and a null gene set are controls. Failure to recover the planted genes, a failed QC control, an unsupported model, or an incompatible identity falsifies reference acceptance. Real studies need a design-specific power analysis, normalization assessment, batch adjustment and sensitivity analysis. Stop for missing essential inputs or interpretation-changing ambiguity; choose reversible presentation details without another gate.

## Reference usage

Read [the reference index](references/index.json), then [stages and record contracts](references/stages.md) before QC, freezing, analysis, validation or handoff. Use [the plan template](references/plan.json) for the existing manifest `plan` step shape; do not extend the manifest or checkpoint schemas. Record hashes of materially controlling references in the existing `reference-use-ledger`.

## Workflow

1. **01-design — dataset fitness and design.** Admit exact input paths and SHA-256 identities, reuse the two discovery/context skills, preserve sample and donor dependencies, and verify organism, genome/annotation versions and identifier namespaces across tables and supplied gene sets. Record missing evidence as `unavailable` and preserve rejected alternatives.
2. **02-qc — fixed controls.** Measure library size, detected genes, library-size outliers and batch-versus-condition structure. Refuse perfectly confounded batches. Retain every failed control and excluded sample with reason, measurement and the fixed threshold; never silently delete an outlier. Refuse fewer retained replicates than the declared minimum.
3. **03-freeze — immutable analysis.** Freeze the contrast, model, thresholds, full hypothesis family and enrichment universe with a canonical SHA-256 before testing. Preserve that record when revising. A contrast or threshold changed after results requires an `exploratory` label and a new analysis hash, never a rewritten original. Hashes bind declared content; they do not independently prove historical timing.
4. **04-testing — differential association.** Run the CPU-only synthetic reference CLI described in the reference. It applies a two-sided Welch test to log2(CPM+1), reports the effect as second contrast group minus first, and applies BH to every tested gene. Refuse missing correction and correction over a post-test subset. No result is a causal or clinical claim. For real counts, DESeq2 or edgeR style dispersion models are gated extension points; this pack never installs or executes them. Nonempty covariates are refused by the reference rather than silently ignored.
5. **05-enrichment — supplied collection.** Use the supplied, version-matched gene-set collection and an explicit universe containing all tested genes. Compute an upper-tail hypergeometric probability and BH across all supplied sets, including empty and null sets. Preserve negative results and collection members outside the universe as excluded by the declared intersection rule. A pathway association does not identify a causal mechanism.
6. **06-handoff — bounded claims.** Keep all QC measurements, negative results, exclusions, dependencies, unavailable evidence, limitations and exploratory revisions. Register domain records as ordinary artifacts with `$science-provenance`; write separate entries in the existing claim register. Provide the immutable input identities, frozen specification, logs, outputs and falsifiable next action to `$science-review`. Rigor classification, review independence and review receipt registration belong to the coordinator.

Use one coordinator checkpoint per run and advance these ordered stage IDs on that checkpoint. The reference runner creates no checkpoint, execution engine, manifest mutation or review receipt. Retry only after correcting an identified input problem; retain the failed record and use a new output path when inputs change. Do not retry numerical failure by weakening a control.

## Outputs

- Input count table (`bulk-expression-counts-v1`) and supplied collection (`bulk-expression-gene-sets-v1`), each explicitly labelled synthetic fixtures for the reference route.
- Design, frozen and current specifications, immutable input identities, exclusion records, stage order and declared claims (`bulk-expression-pack-v1`).
- QC, all gene effects and p/q values, all supplied set enrichment results, input/specification hashes, exploratory status and limitations (`bulk-expression-result-v1`). The reference leaves review `unavailable`.
- Separate existing claim-register entries for supported, contradicted, inconclusive and unavailable claims; conflicts, rejected alternatives, applicability, uncertainty, sensitivities and the next discriminating measurement in the coordinator's handoff. Do not add domain keys to existing records.

The runnable example is `examples/workflow-bulk-expression-analysis/pack.json`; acceptance targets and the 13 negative examples are indexed alongside it. Frozen questions and CPU budgets are in `benchmarks/workflow-bulk-expression-analysis/tasks.json`. L4 means fixture acceptance tested through unittest discovery, not scientifically validated differential expression in real cohorts.

## Boundaries

Refuse association presented as causality, numerical agreement presented as physical or clinical validity, a missing record presented as negative evidence, or review approval presented as truth. The validator conservatively refuses causal/mechanistic/clinical claim vocabulary; independent review still checks meaning and omitted confounders. It cannot adjudicate every natural-language paraphrase.

No network, GPU, remote job, download, installation or external executable is part of this reference route. Only separately authorized installation, restricted transfer, a new host, GPU/remote/heavy compute, or interpretation-changing choices require a human decision gate. Do not ask permission at every stage of an admitted offline run.

Stop for identifier/annotation mismatch, unavailable essential files, invalid hash, failed controls, insufficient replicates, undocumented exclusion, unlabeled post-result changes, missing or selectively applied correction, or an invalid enrichment universe. Preserve nulls and failed controls in the coordinator's evidence record. A successful process and an independent review approval do not establish truth. Bulk RNA does not establish expressing cell type, protein activity, biological mechanism or clinical efficacy.
