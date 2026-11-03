---
name: workflow-western-blot-densitometry
description: "Check supplied synthetic Western blot band intensities with frozen local backgrounds, antibody dilution ranges, loading controls, blot references and biological replicate uncertainty. Use for offline densitometry arithmetic; exclude abundance and medical conclusions."
license: MIT
---

# Western Blot Densitometry

Role: conductor with an offline reference analyzer. All checked-in intensities, questions and expected artifacts are synthetic fixtures. This pack checks already-measured numbers; it does not quantify images or validate an assay.

## Decision contract

Freeze and hash lane/sample/blot identities, target and loading-control antibodies, biological units, technical repeats, local per-lane background subtraction, linear dynamic ranges from a frozen synthetic dilution series, raw saturation ceilings, target-over-loading-control normalisation, one reference lane per blot, reference group, maximum loading-control CV, minimum biological n and interval method/level before opening intensities. Record the question, system, cutoff, descriptive claim IDs, baseline, uncertainty, falsifier, exclusions, missingness and rejected alternatives. Hash identity alone cannot prove historical freeze timing.

The deliverable is an offline arithmetic check. Technical lane repeats collapse to one biological-unit mean after per-blot scaling. Group means and standard errors count reliable biological units only. Fold change is the ratio of arithmetic group means; its approximate log-delta interval uses Welch-Satterthwaite degrees of freedom. Fewer than three reliable units in either group gives unavailable intervals. Zero variance cannot support a Welch interval. Independent biological units and proportional dilution intensities are assumptions. Reference-lane calibration uncertainty is not propagated. The synthetic acceptance case has control units 1, 2, 1 and contrast units 2, 4, 6, giving means 4/3 and 4, and fold change 3.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before rule freeze, intensity admission, computation, validation or claim handoff. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing reference-use-ledger. Procedure references are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Freeze wb-rules-v1 and hash its bytes before table admission. Use $cx-statistical-decision-analysis for decision framing. Preserve the original revision; a changed rule requires an exploratory label, recomputation and a human decision when interpretation changes.
2. **02-table-qc.** Admit immutable path-plus-hash wb-table-v1. Require unique frozen lane IDs, finite nonnegative raw intensities and local backgrounds, positive corrected values within each antibody's inclusive linear range and raw intensities below its saturation ceiling. Flag negative corrected, out-of-range and saturated lanes as unreliable and exclude before division or logs. Missing lanes require explicit all-null unavailable rows. Preserve failed controls and negative results.
3. **03-normalisation.** Run scripts/validate_western_blot_densitometry_pack.py on the synthetic fixture first. Stop for a missing or unreliable blot reference or loading-control CV exceeding the frozen bound. Compute target/loading control, divide by the blot reference ratio, collapse technical lanes within each biological unit, then compute group mean, standard error, fold change and Welch log-delta interval. Never count lane repeats as independent biological units.
4. **04-summary.** Preserve every lane, reason for exclusion, biological unit and denominator. Unavailable values stay unavailable; do not turn absent records into negative evidence or include unreliable lanes in summaries. Retain uncertainty, dependencies, conflicts, controls, sensitivity needs, rejected alternatives and limitations.
5. **05-handoff.** Register domain records as ordinary artifacts with $science-provenance and separate entries in the existing claim register. Hand rules, table, full results, hashes, failures, reference ledger, execution/environment identities and bounded claims to $science-review in record, source and method modes. The coordinator owns rigor classification and independent review. This pack always leaves review unavailable.

Use one coordinator checkpoint per run with these ordered stage IDs. Retry only after correcting a specific labelled defect and retain failed revisions. No execution engine, live assay, network or image processing is added.

## Outputs

Pack-local schemas: wb-pack-v1, wb-rules-v1, wb-table-v1, wb-report-v1, wb-evidence-v1 and wb-result-v1. The stages reference specifies exact fields, limits and commands. No existing manifest, receipt, claim-register or MCP schema changes.

Return immutable input identities, assumptions, lane ratios, blot scaling, biological-unit means, group means/standard errors, fold intervals or unavailable, inclusion/exclusion rationale, controls, dependencies, conflicts, applicability, uncertainty, limitations and the smallest falsifiable next measurement. The coordinator keeps supported, contradicted, inconclusive and unavailable interpretations separate. Numerical agreement cannot support a positive scientific claim.

Synthetic fixtures and negative cases live in examples/workflow-western-blot-densitometry/. Frozen questions and CPU budgets live in benchmarks/workflow-western-blot-densitometry/tasks.json. L4 denotes offline synthetic acceptance in tests/test_workflow_wb_pack.py, never assay or biological validation.

## Boundaries

Refuse claims of protein abundance, expression regulation, mechanism, clinical relevance, causality or physical validity, even under a descriptive label. The stages reference specifies the conservative, incomplete English lexical gate. Association is never causality; computed agreement is never physical or clinical validity; absent evidence is unavailable, never negative evidence; review approval is never truth. Computed records and review approval cannot support positive claims. An unavailable source requires unavailable claims; empty evidence requires unavailable status. One synthetic fixture cannot establish replication. External, independent and preregistered labels must not alias any supplied study artifact by path or hash.

This route uses standard library code, local CPU and offline synthetic fixtures only. No download, installation, network, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice. Do not prompt at every admitted offline stage. Preserve failed controls, exclusions and negative results. Never mark this pack's output independently reviewed.
