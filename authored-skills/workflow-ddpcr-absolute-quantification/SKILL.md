---
name: workflow-ddpcr-absolute-quantification
description: "Check already-read droplet digital PCR partition counts with frozen controls, Poisson copy concentration, exact binomial bounds and concordant replicate pooling. Use for supplied synthetic count tables; exclude copy-number state, gene dosage and medical conclusions."
license: MIT
---

# ddPCR Absolute Quantification

Role: conductor with an offline reference analyzer. Every supplied example and expected artifact is a synthetic fixture. This pack checks count arithmetic on local CPU; it does not read fluorescence, set droplet thresholds, validate an assay or determine sample suitability.

## Decision contract

Before reading counts, freeze sample/well identities and NTC roles, partition volume in uL, minimum accepted partitions, maximum positive NTC partitions, saturation bound, dilution correction multiplier, reaction-to-sample multiplier, confidence level, exact Clopper-Pearson method, replicate wells per sample and the relative lambda agreement bound. Hash those rule bytes first. Record the question, descriptive claim IDs, system, evidence cutoff, baseline, uncertainty, falsifier, exclusions, missingness and permitted inference. A hash establishes identity; it cannot establish historical preregistration.

The point estimate is lambda = -ln(1-p), p = positive/total, followed by concentration = lambda / partition_volume_ul times dilution_factor times reaction_to_sample_scaling, in copies per sample-equivalent uL. Both multipliers are corrections, never dilution fractions to divide twice. Pool by summing positive and total partitions only after all frozen technical wells pass QC and agree. Technical wells do not increase sample n. Equal-volume independent partitions, accurate readout, volume and correction factors are assumptions requiring method review. Interval coverage excludes their uncertainty and post-selection effects.

The tiny synthetic fixture has two A wells with 2/4 positives each and a zero-positive NTC: pooled p = 4/8, lambda = ln(2), concentration = 12 ln(2). A second zero-positive sample has a positive upper bound; it never establishes absence. The acceptance test concerns software arithmetic only.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, opening counts, computing quantities, validating a bundle or handing off claims. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing `reference-use-ledger`; procedural references are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Use `$cx-statistical-decision-analysis` to frame uncertainty. Preserve immutable `ddpcr-rules-v1` bytes and SHA-256 before counts admission. Preserve original revisions and rejected alternatives. Any later threshold change requires exploratory labelling, recomputation and retention of the original rules; interpretation-changing choices need a human decision.
2. **02-count-qc.** Admit the path-plus-hash `ddpcr-counts-v1` table. Require unique frozen well IDs, real nonnegative integer positive/total counts, positive <= total, enough accepted partitions and explicit NTCs under the frozen maximum. Missing counts require unavailable rows with null counts, never zeros. Preserve failed controls and negative results.
3. **03-quantification.** Run `scripts/validate_ddpcr_absolute_quantification_pack.py` on the synthetic fixture first. Compute exact Clopper-Pearson positive-fraction bounds and transform their endpoints monotonically through -ln(1-p) and the frozen scaling. Refuse reported quantification of saturated wells, p = 1, inadequate partitions or failed NTCs. Stop replicate pooling when relative lambda range exceeds the frozen bound; return unavailable sample concentration and retain individual well results. Never replace Poisson correction with p directly or the exact interval with a normal approximation.
4. **04-summary.** Preserve every sample, well, count, failure reason and interval. Report sample n, quantified/unavailable denominators, NTC status and mean concentration over quantified samples only. No unavailable value enters a mean. Retain uncertainty, dependencies, conflicts, exclusions, sensitivity needs and the smallest falsifiable next measurement.
5. **05-handoff.** Register domain records as ordinary artifacts with `$science-provenance`, with separate entries in the existing claim register. Hand rules, original counts, full results, failed revisions, negative controls, reference ledger, environment/code identities, hashes and bounded claims to `$science-review` in record, source and method modes. The coordinator owns rigor classification, the one checkpoint and independent receipt registration. The pack always leaves review unavailable.

Use these ordered stage IDs in one coordinator checkpoint per run; add no execution engine. Retry only after correcting a named input defect and preserve failed revisions. Resolve reversible display preferences internally. Stop for essential missing inputs or interpretation-changing ambiguity.

## Outputs

Pack-local schemas are `ddpcr-pack-v1`, `ddpcr-rules-v1`, `ddpcr-counts-v1`, `ddpcr-report-v1`, `ddpcr-evidence-v1` and `ddpcr-result-v1`. The stages reference defines their exact fields and limits. Existing manifests, receipts, claim registers and MCP contracts are unchanged.

Return normalized assumptions and immutable identities, per-well and pooled sample estimates or unavailable reasons, exact intervals, controls, denominators, inclusion/exclusion rationale, dependencies, conflicts, rejected alternatives, uncertainty, applicability and limitations. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately; a computed match cannot support a positive scientific claim.

Synthetic inputs, expected artifacts and seeded mutations are in `examples/workflow-ddpcr-absolute-quantification/`. Frozen questions and CPU budgets are in `benchmarks/workflow-ddpcr-absolute-quantification/tasks.json`. L4 means offline fixture acceptance in `tests/test_workflow_ddpcr_pack.py`; it establishes no physical or clinical validity.

## Boundaries

Refuse text claiming copy-number state, gene dosage, disease, sample suitability, causal mechanisms, therapeutic effects, clinical relevance, efficacy or physical validity, regardless of the claim kind label. The stages reference defines a conservative, incomplete English lexical gate. Association is never causality. Numerical agreement is never physical or clinical validity. Review approval is never truth. Computed or review records cannot support positive claims. Unavailable evidence always requires unavailable claims; empty evidence also requires unavailable. A single synthetic fixture cannot establish replication. External, independent or preregistered labels cannot alias supplied artifacts by path or hash.

This route uses standard-library code and offline synthetic fixtures only: no network, downloads, installation, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice. No per-stage permission prompt is required. Preserve failed controls and negative results. Absence of a record is unavailable, never negative evidence.
