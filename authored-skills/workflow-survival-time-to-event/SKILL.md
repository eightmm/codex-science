---
name: workflow-survival-time-to-event
description: "Compare two baseline-defined groups using supplied per-subject follow-up, event flags and right censoring. Use for Kaplan-Meier curves and log-rank comparisons; exclude post-baseline group assignment, causal conclusions and medical decisions."
license: MIT
---

# Survival Time to Event

Role: conductor with an offline reference analyzer. Output states statistical evidence only. All checked-in cohorts and expected results are synthetic fixtures, never clinical evidence.

## Decision contract

Record the exact question, population, endpoint, evidence cutoff, claim IDs, baseline, two group identities, time origin, event definition, censoring rule, assignment information and timing, time unit, tie handling, alpha, minimum events, minimum subjects per group, maximum allowed censoring imbalance, uncertainty rule and falsifier before reading the subject table. Freeze the protocol bytes and SHA-256 first. Never redefine a group using survival until a later landmark. This reference handles one right-censored endpoint and two unpaired groups; it does not handle competing risks, left truncation, interval censoring, weighting, covariates or repeated subjects.

Acceptance requires the planted synthetic fixture difference, the hand-derived tiny-table KM and log-rank quantities, explicit unavailable medians, and all seeded refusals. These checks establish numerical behavior, never power, clinical validity or noninformative censoring. Hash-bound declarations cannot independently prove historical freeze timing or source independence. A real study needs source and design review, a power justification, censoring diagnostics and sensitivity to assignment, loss to follow-up and endpoint definitions. Stop for an essential missing input or an interpretation-changing ambiguity; choose reversible display preferences internally.

## Reference usage

Read [the index](references/index.json) and [stages and record shapes](references/stages.md) before protocol freeze, table admission, reference computation, validation or handoff. Reuse [the plan](references/plan.json) with the existing manifest step shape. Record controlling reference paths and hashes in the existing `reference-use-ledger`; references are procedural contracts, never independent evidence.

## Workflow

1. **01-protocol — freeze before the table.** Use the decision contract and `$cx-statistical-decision-analysis` for the decision threshold and uncertainty framing. Hash the complete frozen protocol before opening the cohort. Preserve original bytes, revisions and rejected alternatives. An unlabelled group or test change is refused; a labelled group reversal remains exploratory. Alternative tests require a separately reviewed implementation and remain unavailable in this reference.
2. **02-cohort — preserve subject identity.** Admit an already-extracted table with subject ID, positive follow-up time, event flag, censoring flag, group, latest group-assignment information time relative to baseline and time unit. Check every path-plus-hash handoff. Missing records are `unavailable`, never negative evidence. Do not infer absent subject identities or silently change time units.
3. **03-integrity — stop on failed controls.** Refuse non-finite or non-positive times, duplicate subjects, mixed units, inconsistent event/censoring flags, post-baseline assignment information, too few subjects or events and excessive censoring imbalance. Retain the failed controls and negative results in the coordinator record. Thresholds were fixed before outcomes; never weaken them to pass.
4. **04-computation — bounded comparison.** Use `scripts/validate_survival_pack.py` on the synthetic fixture first. Compute per-group Kaplan-Meier estimates, Greenwood variance and log-log confidence intervals, events before censoring at ties, and a two-sided log-rank test. A median is `unavailable` unless the curve reaches 0.5. The log-rank O/E hazard ratio must always say exploratory and makes no proportional-hazards claim. Preserve denominators, censoring fractions, nulls and all uncertainty. Zero-variance log-rank inputs are refused.
5. **05-handoff — independent review.** Register pack-local domain records as ordinary artifacts with `$science-provenance`; use separate entries in the existing claim register. Retain dependencies, conflicts, failed controls, unavailable evidence, limitations and the smallest falsifiable next measurement. Hand the protocol, table, hashes, complete results, execution/environment identities, reference-use ledger and claim register to `$science-review` in record, source and method modes. Rigor classification and independent receipt registration remain coordinator responsibilities. This pack never marks its output reviewed.

Use one coordinator checkpoint per run and the five ordered stage IDs above. The reference creates no manifest, checkpoint or execution engine. Correct a specific input defect before retrying; retain each failed revision. A second producer pass is never independent review.

## Outputs

Pack-local schemas: `survival-pack-v1`, `survival-protocol-v1`, `survival-cohort-v1`, `survival-report-v1`, `survival-evidence-v1`, `survival-result-v1`. Exact shapes, limits, handoffs and the one-argument read-only CLI appear in the stages reference. These schemas add no fields to existing manifests, receipts, claim registers or MCP contracts.

Return normalized assumptions, frozen identities, subject and event denominators, measured censoring fractions, per-time risk sets and KM uncertainty, unavailable or attained medians, log-rank observed/expected counts and p-value, exploratory O/E ratio, claims and limitations. The coordinator separately records supported, contradicted, inconclusive and unavailable interpretations using existing claim semantics, with inclusion/exclusion rationale and rejected alternatives. Absent review stays `unavailable`.

Redistributable synthetic fixtures, expected artifacts and seeded refusals live in `examples/workflow-survival-time-to-event/`; frozen questions and CPU budgets live in `benchmarks/workflow-survival-time-to-event/tasks.json`. L4 means offline fixture acceptance through `tests/test_workflow_survival_pack.py`, never real-cohort or clinical validation.

## Boundaries

Refuse association stated as causality, treatment effect, clinical recommendation, efficacy, mechanism or physical validity, including through a descriptive claim label. Positive claims cannot cite review approval or computed/numerical agreement, checking both declared record kind and result. Independent, external and preregistered labels cannot substitute for hash-bound evidence or alias study artifacts. The conservative English lexical check and its incomplete scope are specified in the stages reference. Review approval is never truth.

Unavailable cited evidence requires an unavailable claim. Replication requires two distinct cited source paths and hashes, including declared non-internal evidence that passes the anti-alias checks. All source hashes are required; ancestor descriptors are pinned and distinct artifact bytes are limited to 256 MiB in total, with hardlink aliases counted once. These checks cannot establish historical freezing or real-world independence.

This route uses local CPU and offline synthetic fixtures, with standard-library computation and no installation, download, network, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfers, a new host, GPU/remote/heavy compute or an interpretation-changing choice. Do not gate each admitted offline stage. Numerical agreement never establishes physical or clinical validity; failed controls and negative results remain visible.
