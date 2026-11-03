---
name: omics-target-prioritization
description: Prioritize exploratory targets from donor-aware expression contrasts and source-linked external evidence. Use for an omics-to-target handoff with cohort/batch checks, missingness and dependency-aware evidence; not raw-count differential expression or causal target validation.
---

# Omics target prioritization

## Decision contract

Connect comparable exported expression and source evidence to a qualified target
list. Reuse `$cx-public-omics-dataset-discovery`, `$cx-expression-cell-context`,
`$cx-biomedical-entity-normalization` and `$cx-biomedical-evidence-reconciliation`
as needed. This conductor adds donor-level descriptive analysis and handoff;
it does not replace an RNA-seq or single-cell analysis backend.
Acceptance requires coherent donor/cohort/condition identities and essential
controls, all genes and evidence dependencies retained, and exploratory priorities
or an explicit empty shortlist. Freeze the sampling unit, contrast and threshold
before inspecting the outcome; unresolved confounding blocks the contrast.

## Reference usage

Read [stages](references/stages.md) before intake or analysis. Read
[method discovery](references/method-discovery.md) and dated
[method seeds](references/methods.json) before selecting an upstream analysis.
Use the existing [plan](references/plan.json) for one coordinator run.

## Workflow

1. **Freeze:** gene/construct identifiers, tissue/cell context, cohort/donor/sample
   units, reference/case conditions, pairing, batches, expression scale,
   normalization provenance, directional threshold and controls.
2. **Discover:** select public inputs and an appropriate upstream processing route.
   For single-cell data, retain patient/sample identity and cell-type context;
   use an appropriate count-based pseudobulk/model route for differential testing.
3. **Prepare:** normalize and annotate only through approved, pinned tools. Export
   comparable donor/sample log2-normalized expression and source-backed evidence.
   Keep failed samples and missing genes visible; do not substitute zeros.
4. **Analyze:** run the helper. Technical samples are averaged within donor;
   donors determine the descriptive cohort contrast. Reject unresolved condition/
   batch confounding and donor reuse across independent cohorts. Preserve
   per-cohort direction disagreements and sparse-gene exclusions. Partial batch
   imbalance retains descriptive effects but prevents target prioritization.
5. **Reconcile:** group evidence sharing a study origin or cohort. A portal copy
   is not independent replication. Retain opposing evidence and mark overlaps
   with expression cohorts; missing evidence remains unavailable.
6. **Review/handoff:** register inputs, source releases, normalization/model
   provenance, controls, cohort effects and exclusions with `$science-provenance`.
   Obtain independent `$science-review` before handing candidate target identities
   and unresolved context to virtual screening or binder design.

## Outputs

```bash
python3 <plugin-root>/scripts/analyze_omics_targets.py INPUT.json
```

The synthetic CPU input is `examples/omics-target-prioritization/input.json`.
`examples/omics-target-prioritization/batch-imbalance.json` retains a deliberately
inflated cohort effect while blocking the shortlist because of a case-only batch.
The output is `omics-target-analysis-v1`, an ordinary hashed artifact containing
all genes, cohort contrasts, dependency groups and exploratory priorities.

## Boundaries

The helper performs no normalization, cell annotation, differential-expression
testing, pathway inference or source retrieval. A difference of mean log2
expression is a descriptive contrast, not DESeq2/edgeR log-fold change or an
adjusted p-value. Evidence sources and cohort independence are supplied identities.
Expression and association do not establish causality, druggability, efficacy or
a therapeutic recommendation. Do not launch downstream campaigns automatically;
first freeze the selected target, biological context and bounded execution plan.
