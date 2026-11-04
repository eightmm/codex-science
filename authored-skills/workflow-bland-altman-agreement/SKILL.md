---
name: workflow-bland-altman-agreement
description: "Check supplied paired measurements with frozen Bland–Altman bias, limits, t intervals and proportional-bias screens. Use for synthetic method-comparison tables with matching units; exclude interchangeability, equivalence and medical conclusions."
license: MIT
---

# Bland–Altman Agreement

Role: conductor with an offline reference analyzer. Every checked-in table, expected artifact and benchmark is a synthetic fixture. This pack admits descriptive arithmetic only.

## Decision contract

Before opening measurement values, freeze unit IDs, the reference method A or B, common units, original or natural-log scale, A - B difference definition, one pair per unit or mean-per-method-before-transform replicate collapse, minimum complete pairs, the interval minimum of 30, limits multiplier 1.96, t-based confidence method and level, exact proportional-bias test and alpha, skewness/kurtosis screen bounds and the maximum allowed difference. Hash the rule bytes first. Declare question, system, evidence cutoff, descriptive claim IDs, baseline, uncertainty, exclusions, dependencies, falsifier and applicability. Hash identity cannot prove historical preregistration.

The arithmetic question is whether the computed limits lie within a predeclared symmetric difference bound. This descriptive fact never establishes method suitability. Missing methods remain unavailable and excluded from the complete-pair denominator. Replicates collapse to one value per method per unit before transformation; they never increase independent n. The reference label does not reverse the frozen A - B sign. Interpretation-changing choices require a human decision before execution.

Acceptance requires the hand-derived synthetic six-pair fixture: differences 0, 1, 2, 2, 3, 4 give bias 2 and sample SD sqrt(2). The separate 30-pair fixture exercises all three confidence intervals. These checks establish software arithmetic only. Normality and regression assumptions, heteroscedasticity, method calibration and broader applicability remain unvalidated; preserve sensitivity needs and rejected alternatives.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting values, computing quantities, validating bundles or handing off claims. Reuse [the ordered plan](references/plan.json) in the existing manifest plan shape. Record controlling reference paths and hashes in the existing reference-use-ledger. These documents guide procedure; they are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Use $cx-statistical-decision-analysis to frame uncertainty and $science-provenance to preserve immutable ba-rules-v1 bytes and hash before values. Freeze every threshold and handling rule. Keep original revisions; a later bound change requires an exploratory label and recomputation.
2. **02-pair-qc.** Admit path-plus-hash ba-pairs-v1 input. Check unique frozen unit IDs, common units, both method fields, finite values, positive original measurements for logs and declared replicate handling. Missing methods require explicit nulls and unavailable output rows. Stop on identity, scale, count or unit failures; never silently drop unpaired units.
3. **03-agreement.** Run scripts/validate_bland_altman_agreement_pack.py on the smallest synthetic fixture first. Recompute bias, sample SD, limits, t-based confidence intervals for bias and each limit when n is at least 30, exact two-sided regression t test, normality screen and the descriptive bound comparison. Fewer than 30 pairs gives unavailable intervals. Refuse relatively singular variance, failed moment controls and correlation substituted for agreement. Preserve detected proportional bias; never omit it or treat a nonsignificant test as proof of absence.
4. **04-summary.** Retain every unit, exclusion and unavailable value, complete-unit n, scale and uncertainty. Include failed controls, negative results, assumptions, conflicts, dependencies, rejected alternatives, limitations and the smallest falsifiable next action. The moment screen does not prove normality or constant variance.
5. **05-handoff.** Register domain records as ordinary artifacts with $science-provenance and separate entries in the existing claim register. Hand rules, paired inputs, immutable hashes, all results, failed revisions, controls, execution/environment identities, reference ledger and bounded claims to $science-review in record, source and method modes. The coordinator owns rigor classification and receipt registration. The pack always leaves review unavailable.

Use one coordinator checkpoint and these ordered stage IDs per run. This pack adds no execution engine. Retry only after repairing a named input defect, retaining each failed revision. Continue admitted reversible offline work without per-stage prompts. Stop for unavailable essential input or an interpretation-changing choice.

## Outputs

Pack-local schemas: ba-pack-v1, ba-rules-v1, ba-pairs-v1, ba-report-v1, ba-evidence-v1 and ba-result-v1. The stages reference specifies exact fields, limits and refusal ordering. Existing manifest, checkpoint, artifact, receipt, claim-register and MCP shapes remain unchanged.

Return normalized inputs and assumptions, path-plus-hash identities, per-unit differences and means or unavailable, exclusions, complete-unit denominator, bias, SD, limits and intervals, regression slope/t/p and detected-bias flag, moment screen, descriptive bound comparison, uncertainty, dependencies, conflicts, rejected alternatives and limitations. The coordinator separately records supported, contradicted, inconclusive and unavailable interpretations. A computed match cannot support a positive scientific claim.

Synthetic acceptance bundles and seeded mutations live in examples/workflow-bland-altman-agreement/. Frozen questions and CPU budgets live in benchmarks/workflow-bland-altman-agreement/tasks.json. L4 denotes offline acceptance in tests/test_workflow_ba_pack.py, never observational or medical validation.

## Boundaries

Refuse claims of interchangeability, clinical acceptability, equivalence or method validity, including when labelled descriptive. Refuse causal, mechanistic, therapeutic, efficacy or clinical-action wording. The stages reference lists the incomplete conservative English lexical gate. Association is never causality; numerical agreement is never physical or clinical validity; review approval is never truth. A citation to any unavailable record requires unavailable status. Empty evidence requires unavailable. Neither computation nor review approval supports positive claims. A single synthetic fixture cannot establish replication. External, independent and preregistered labels must not alias any supplied study output by path or hash.

This route uses local CPU, standard library code and offline synthetic fixtures only. No network, download, installation, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Preserve failed controls and negative results; absence of a record is unavailable, never negative evidence.
