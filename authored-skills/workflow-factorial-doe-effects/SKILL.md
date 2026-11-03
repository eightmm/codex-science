---
name: workflow-factorial-doe-effects
description: "Check completed two-level factorial response tables with frozen coded levels, exact design contrasts, signed alias sets, replicate pure error and centre-point curvature. Use for offline synthetic fixtures; exclude optimal conditions and mechanistic conclusions."
license: MIT
---

# Two-level Factorial Effects

Role: conductor with a small offline reference analyzer. Every checked-in response table, expected artifact and benchmark question is a synthetic fixture. This pack checks arithmetic for completed full or regular fractional designs; it does not run experiments or choose operating conditions.

## Decision contract

Before reading responses, freeze the intended question, descriptive claim IDs, system, evidence cutoff, factor IDs and low/high labels, full or named regular fraction with signed generators and resolution, run identities and replicate counts, optional centre condition, response and units, half-difference reporting rule, pure-error uncertainty rule, confidence level and run-order randomisation seed. Hash the immutable rule bytes before response admission. Define the baseline, falsifier, exclusions, missingness, rejected alternatives and applicability. A declared hash cannot prove historical preregistration.

Accept only complete two-level tables with at most four factors, exactly balanced and orthogonal columns, equal factorial replicate counts, and the frozen generators and seed order. Report half the difference of level means, including interaction columns, rather than silently doubling coefficients. A fraction yields one estimate per signed alias set. Never assign that estimate independently to the confounded terms. Within-condition replicates supply pure error; no replicates means unavailable standard errors and intervals and no significance wording. Zero pure-error variance refuses inference. Centre points require a curvature contrast, including an unavailable interval when error cannot be estimated.

The synthetic acceptance baseline is a 2^3 table with coefficients A=2, B=-3, AB=1.5, ABC=0.5, pure-error variance 2 and centre departure 4. A 2^(4-1) fraction with D=ABC has I=ABCD, A=BCD and AB=CD; the last set has coefficient 3. These checks validate software arithmetic only. Error independence, equal variance, normality, actual randomisation and observational validity require separate review.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting response tables, computing contrasts, checking claims or handing off review. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing reference-use-ledger. Procedure documents never supply scientific evidence.

## Workflow

1. **01-rule-freeze.** Use $cx-statistical-decision-analysis for the decision framing and $science-provenance to preserve doe-rules-v1 plus its path and SHA-256 before opening responses. Freeze signed generators, stated resolution, replicate counts and randomisation. Retain originals; any post-outcome coding reversal requires exploratory true and complete recomputation, with an interpretation-changing choice escalated to the coordinator.
2. **02-table-qc.** Admit doe-table-v1 through immutable path-plus-hash identities. Check unique run IDs, real integer -1/+1 levels (all zero for the optional centre), exact balance/orthogonality, complete design support, generator consistency, frozen levels/counts, finite responses and the exact seeded condition-group order. Preserve failures and negative results; never drop runs or impute missing responses to pass.
3. **03-effects.** First run scripts/validate_factorial_doe_pack.py on examples/workflow-factorial-doe-effects/pack.json. Compute signed contrast alias sets, within-condition pure-error degrees of freedom and standard errors, equal-tail Student t intervals and the required centre-versus-factorial curvature contrast. A defining word shares the intercept alias set. No pooled residual or high-order-interaction error substitution is allowed.
4. **04-summary.** Retain all conditions, observation and centre denominators, grand mean, contrasts, aliases, uncertainty and unavailable values. Record controls, failed revisions, null results, assumptions, dependencies, conflicts, sensitivity needs and the original low/high labels. Centre curvature cannot identify an individual quadratic term. No result selects optimal conditions.
5. **05-handoff.** Register rules, table, report and full validation result as ordinary artifacts through $science-provenance, with separate entries in the existing claim register. Hand hashes, execution/environment identity, reference ledger, controls, failures, rejected alternatives and bounded conclusions to $science-review in record, source and method modes. The coordinator owns rigor classification and independent review registration; this pack always leaves review unavailable.

Use one checkpoint per run and these ordered stage IDs. There is no new execution engine. Retry only after correcting a named defect; retain each failed revision. Safe display choices need no prompt. Essential missing inputs stop admission rather than becoming negative evidence.

## Outputs

Pack-local schemas: doe-pack-v1, doe-rules-v1, doe-table-v1, doe-report-v1, doe-evidence-v1 and doe-result-v1. Their exact fields, bounds and equations are in the stages reference; they change no existing manifest, receipt, sidecar or MCP contract.

Return immutable identities, normalized inputs and assumptions, the evidence/computation table, signed alias memberships, half-difference estimates, uncertainty or unavailable, curvature, denominators, inclusion/exclusion rationale, dependencies, conflicts, rejected alternatives, applicability and limitations. Record supported, contradicted, inconclusive and unavailable interpretations separately through the coordinator. State the smallest falsifiable next measurement or independent error-assumption check.

Synthetic fixtures and negative mutations live in examples/workflow-factorial-doe-effects/. Frozen questions and CPU budgets live in benchmarks/workflow-factorial-doe-effects/tasks.json. L4 denotes exercised offline fixture acceptance in tests/test_workflow_doe_pack.py, never physical, biological or process validation.

## Boundaries

Refuse optimal-condition, causal, mechanism, scale-up, process-validity, therapeutic or clinical assertions, including under a descriptive kind. The stages reference states the conservative and incomplete English wording gate. Association is never causality; numerical agreement is never physical or clinical validity; review approval is never truth. Any unavailable evidence requires unavailable status; empty evidence requires unavailable status. Unavailable claims cannot assert positive evidence. Computed or review-approval records cannot support positive claims. This fixture cannot establish replication. External, independent and preregistered sources cannot alias the supplied artifacts by path or hash.

This route is read-only, CPU-only, standard-library-only and offline. It performs no installation, network access, transfer, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfer, new hosts, GPU/remote/heavy compute or interpretation-changing choices, never routinely at each stage. Preserve failed controls and negative results; absence of evidence remains unavailable.
