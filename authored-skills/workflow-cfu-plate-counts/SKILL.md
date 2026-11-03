---
name: workflow-cfu-plate-counts
description: "Check already-counted serial-dilution colony plates with frozen countable ranges, exposure-weighted CFU per mL and exact Poisson bounds. Use for supplied synthetic counts; exclude sterility, safety, potency and medical conclusions."
license: MIT
---

# CFU Plate Counts

Role: conductor with an offline reference analyzer. All checked-in counts and expected artifacts are synthetic fixtures. This pack checks arithmetic; it does not count images, culture organisms or validate an assay.

## Decision contract

Before reading counts, freeze sample and plate IDs, per-plate dilution fractions, plated volume in mL, inclusive countable ranges, geometric dilution ratio, minimum countable plates, exposure-weighted mean rule, maximum duplicate count ratio, exact Poisson method and confidence level, and the detection upper-bound rule. Hash these rule bytes first. Define the intended question, descriptive claim IDs, system, evidence cutoff, comparison baseline, uncertainty, falsifier, exclusions and missingness. A rule hash is an identity, not independent proof of historical preregistration.

The only point estimate is sum of countable colonies divided by sum of countable plated volume equivalents. Technical duplicate plates do not increase sample n. Freeze whether independent Poisson sampling, recorded volumes and dilution fractions are acceptable assumptions; a failed dilution or duplicate control stops pooling. Sensitivity to plate exclusions and dilution uncertainty needs separate method review. The synthetic hand-derived acceptance case requires 660 colonies over 0.0022 mL-equivalent, a positive upper bound for zero counts, and an above-countable lower bound. No fixture establishes biological validity or calibrated assay detection.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting counts, computing CFU, validating artifacts or handing off claims. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing `reference-use-ledger`; procedure documents are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Freeze the decision contract and hash `cfu-rules-v1` before opening counts. Use `$cx-statistical-decision-analysis` for uncertainty framing. Preserve rejected choices and original revisions. A changed countable range needs an explicit exploratory label and recomputation; never rewrite the original rules.
2. **02-count-qc.** Admit a path-plus-hash `cfu-counts-v1` table. Check unique sample/plate identities, geometric dilutions, recorded volumes, real nonnegative integer counts and explicit spreader, uncountable or unavailable flags with null counts. A missing plate needs an unavailable row, never a zero. Preserve failures and negative results.
3. **03-cfu.** Run `scripts/validate_cfu_plate_count_pack.py` on the synthetic fixture first. Select countable plates only, stop for too few plates or duplicate disagreement, and compute the frozen weighted mean, log10 CFU/mL and equal-tail exact Garwood interval. With all plates below range report only the positive one-sided Poisson upper bound; with all above report only a countable-range lower bound. Mixed below/above plates need review. Incomplete flagged samples without countable plates stay unavailable.
4. **04-summary.** Retain every frozen sample and exclusion, report sample n, classification denominators and mean log10 across quantified samples only. Do not substitute censored bounds or unavailable values into a mean. Report the exact assumptions, controls, uncertainty, conflicts and limitations alongside the numbers.
5. **05-handoff.** Register domain records as ordinary artifacts with `$science-provenance` and separate entries in the existing claim register. Hand rules, counts, hashes, full results, negative controls, failed revisions, execution/environment identities, reference ledger and bounded claims to `$science-review` in record, source and method modes. The coordinator owns rigor classification and independent receipt registration. This pack always leaves review unavailable.

Use one coordinator checkpoint and these five ordered stage IDs per run. There is no new execution engine. Retry only after correcting a specific input defect; retain each failed revision. Stop for essential missing evidence or an interpretation-changing choice; choose reversible display preferences internally.

## Outputs

Pack-local schemas are `cfu-pack-v1`, `cfu-rules-v1`, `cfu-counts-v1`, `cfu-report-v1`, `cfu-evidence-v1` and `cfu-result-v1`. The stages reference defines exact fields and limits. No existing manifest, receipt, claim-register or MCP contract changes.

Return normalized inputs and assumptions, immutable input identities, per-sample CFU or censoring bounds, intervals, log10 quantities, inclusion/exclusion rationale, denominators, dependencies, conflicts, rejected alternatives, uncertainty, applicability, limitations and the smallest falsifiable next measurement. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately. A computed match cannot support a positive scientific claim.

Synthetic acceptance artifacts and negative cases live in `examples/workflow-cfu-plate-counts/`. Frozen questions and CPU budgets live in `benchmarks/workflow-cfu-plate-counts/tasks.json`. L4 denotes offline synthetic fixture checks in `tests/test_workflow_cfu_pack.py`, never assay, biological or clinical acceptance.

## Boundaries

Refuse text asserting sterility, safety, efficacy, potency, clinical relevance, causality, mechanism or physical validity, even under a descriptive label. The stages reference defines the conservative English lexical gate and its incomplete scope. Association is never causality. Numerical agreement is never physical or clinical validity. Review approval is never truth. Neither computed nor review-approval records can support positive claims. Unavailable evidence always requires unavailable claims, and an empty evidence list requires unavailable status. This single synthetic fixture cannot establish replication. External, independent or preregistered labels cannot alias any supplied study artifact by path or hash.

This route uses local CPU, standard library code and offline synthetic fixtures only. No network, download, installation, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute, or an interpretation-changing choice. No gate is needed at each admitted offline stage. Preserve failed controls and negative results; never turn unavailable data into negative evidence.
