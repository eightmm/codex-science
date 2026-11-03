---
name: workflow-growth-curve
description: "Estimate per-well microbial or cell-culture OD growth rates, tangent lag, observed carrying-capacity proxy, integrated OD and doubling times from supplied synthetic time series. Use for frozen blank-corrected offline arithmetic checks; exclude fitness, resistance and medical conclusions."
license: MIT
---

# Growth Curve Parameter Estimation

Role: conductor with a small standard-library reference calculator. All checked-in inputs, expected artifacts and negative cases are synthetic fixtures. The reference accepts synthetic fixtures only.

## Decision contract

Before reading OD values, freeze the question, system, time unit, evidence cutoff, strain and condition identities, replicate and blank wells, biological-unit identities, background subtraction rule, blank stability tolerance, OD linear range upper bound, one model, fit method, start values, tolerance, exponential-window selection rule and length, minimum points, minimum reliable wells and maximum contamination flags. Hash this complete protocol first. This reference chooses model-free maximum log-OD slope with closed-form OLS, empty iterative start values and a frozen relative tie tolerance; logistic and Gompertz fitting require a separately reviewed implementation.

The deliverable is five per-well descriptive parameters and reliable-well summaries with n and bootstrap-free standard errors. Observed maximum OD is only a carrying-capacity proxy. Well-level uncertainty does not establish biological replication. Falsifiers are the hand-derived fixture numbers, failed blanks, grid mismatch and each seeded refusal. A real experiment, scientific validation and mechanistic interpretation remain unavailable. Material interpretation-changing choices require coordinator decisions; reversible presentation choices do not.

## Reference usage

Read [the reference index](references/index.json), [stage controls and exact local records](references/stages.md) and [the ordered plan](references/plan.json) before freezing rules, admitting data, computing quantities or preparing review. Record controlling reference paths and hashes through the existing reference-use-ledger. References describe procedure and are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Use the decision contract and `$cx-statistical-decision-analysis` for uncertainty framing. Freeze all rules and hash `growth-protocol-v1` before opening OD values. Preserve original revisions and rejected alternatives. A changed exponential-window length needs an exploratory label; other method changes stop this reference.
2. **02-data-qc.** Admit immutable path-plus-hash `growth-data-v1`. Require unique wells, finite nonnegative raw OD, strictly increasing equal time grids, stable blanks and declared evaporation, edge, contamination and upstream convergence flags. Apply pointwise blank-mean subtraction internally when frozen. Never silently interpolate, clip negative subtracted OD or log-transform zero/negative values. Retain failed controls as artifacts.
3. **03-per-well.** Run the smallest synthetic fixture through `scripts/validate_growth_curve_pack.py`. Select the largest OLS log-OD slope over the frozen point window, first among relative ties. Compute maximum specific growth rate, OD-tangent lag, observed-maximum carrying-capacity proxy, trapezoidal area and doubling time. Saturation above the raw-OD linear range, non-convergence, too few points and declared sample QC flags conservatively mark all five parameters unreliable. Keep every excluded well and reason. Nonpositive slope makes rate, lag and doubling time unreliable rather than producing an apparent growth estimate.
4. **04-group-summary.** Group by frozen strain and condition. Include reliable wells separately for each parameter, with well IDs, n, distinct biological-unit count, mean and standard error. Technical wells are never biological replicates. Below the frozen n minimum, summary and uncertainty are unavailable. Zero variance leaves uncertainty unavailable; retain the descriptive mean and denominator. Do not bootstrap or claim significance.
5. **05-handoff.** Register pack-local records as ordinary artifacts with `$science-provenance`, and put claims in separate existing claim-register entries. Preserve dependencies, conflicts, exclusions, unavailable observations, nulls, negative results, failed controls and the smallest falsifiable next action. Supply protocol, input hashes, controls, computations, environment/revision, reference ledger and claims to `$science-review` for independent record, source and method review. The coordinator owns rigor classification and review receipt registration; this pack never self-reviews.

Use one coordinator checkpoint with these ordered stage IDs and the existing manifest step shape. This pack adds no execution engine. There are no automatic retries: correct the specific defect in a new preserved revision. A second producer pass is not independent review.

## Outputs

Six pack-local schemas: `growth-pack-v1`, `growth-protocol-v1`, `growth-data-v1`, `growth-report-v1`, `growth-evidence-v1`, `growth-result-v1`. Their exact shapes and limits are in the stages reference. They add no fields to global contracts. Return normalized assumptions, immutable identities, per-well parameters and unreliability reasons, group denominators and uncertainty, bounded claim proposals, limitations and review unavailable. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately using existing claim semantics.

The accepting synthetic fixture is `examples/workflow-growth-curve/pack.json`; expected hand-derived quantities and seeded negative cases accompany it. Frozen questions and CPU budgets are in `benchmarks/workflow-growth-curve/tasks.json`. L4 means synthetic software acceptance through `tests/test_workflow_growth_pack.py`, never physical, biological or medical validation.

## Boundaries

Refuse fitness, resistance, drug effect, mechanism, clinical relevance, causal and therapeutic wording regardless of a claim's kind or status. Association is never causality; computed agreement is never physical or clinical validity; review approval is never truth. Positive statuses cannot cite review approval or computed records, checking kind and result. Missing records are unavailable, never negative evidence. Any unavailable citation requires unavailable status; empty evidence likewise. Replication is refused for synthetic fixtures. External, independent and preregistered labels must have checked identities and cannot alias study outputs by path or hash. The conservative English lexical gate is incomplete; its families are stated in the stages reference.

The route is CPU-only, offline and read-only, using standard-library arithmetic. No network, installation, downloads, GPU, remote or heavy compute are authorized. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices, never at every admitted stage. Input hashes cannot prove historical freezing, independent origins or real experimental validity. Preserve failed controls and negative results.
