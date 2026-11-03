---
name: workflow-immunoassay-4pl
description: "Check supplied plate immunoassay optical densities with a frozen four-parameter logistic standard curve, replicate controls, bracketed sample interpolation and dilution parallelism. Use for already-measured synthetic OD fixtures; exclude clinical interpretation and wet-lab execution."
license: MIT
---

# Immunoassay Four-Parameter Logistic Check

Role: conductor composed with a small standard-library reference analyzer. All checked-in data are redistributable synthetic fixtures. This offline arithmetic check establishes no physical or clinical validity.

## Decision contract

Record the question, analyte, concentration units, supplied plate identity, assay system, evidence cutoff, claim IDs, uncertainty rule and falsifier. The deliverable is an unreviewed arithmetic check of an already-measured plate. Synthetic fixture acceptance is the only tested applicability domain. Missing essential inputs stop admission; an absent record is unavailable, never negative evidence.

Before responses are read, hash the complete rule record: ordered standard dilution series and replicate counts, complete plate map, blank handling, increasing 4PL parameterisation, uniform weighting, Levenberg-Marquardt start values, initial damping, tolerance and iteration cap, standard recovery band, maximum response replicate CV and dilution-parallelism ratio band. Quantifiable range is bounded by the lowest and highest accepted standards. No standard is excluded from the fit. Ask only before an interpretation-changing choice; use reversible presentation defaults otherwise. A hash records bytes and cannot prove historical preregistration.

Fixture acceptance requires recovery of the planted curve, hand-checkable residuals and uncertainty, retained failed controls and range labels with null out-of-range concentrations. Never select fitting starts, thresholds or blank handling to improve a result. Preserve the original freeze and mark a changed blank rule exploratory. Unsupported decreasing curves, other weighting methods and standard exclusion require a separately agreed method.

## Reference usage

Read [the reference index](references/index.json), [the stage and record contract](references/stages.md) and [the ordered plan](references/plan.json) before freezing rules, admitting responses, computing, validating or handing off claims. Record materially controlling reference paths and hashes in the existing `reference-use-ledger`. References guide procedure and are not scientific evidence.

## Workflow

1. **01-freeze — rule freeze.** Preserve and hash the exact analyte, units, standard series and replicates, plate map, blank rule, curve parameterisation, uniform weights, fitting controls and acceptance bands before loading responses. Use the existing manifest step shape and one coordinator checkpoint for the five ordered IDs.
2. **02-qc — data identity and controls.** Admit canonical path-plus-hash inputs through the read-only validator. Require unique well IDs, complete map coverage, consistent units, finite optical densities and at least two blanks and replicates. Compute corrected-response CVs and preserve every flag. Do not repair, drop or reinterpret failed controls.
3. **03-fit — constrained fit and interpolation.** Fit every standard replicate using the frozen method and report parameter standard errors, convergence, back-calculated recoveries and accepted standards. Stop on a non-converged or unidentifiable fit. Invert only for unknown means bracketed by the accepted standards. Below-range and above-range rows have null concentrations. Compute dilution-adjusted recovery ratios solely to check parallelism; do not report an extrapolated concentration. Retain failed and unavailable parallelism and replicate flags.
4. **04-summary — arithmetic summary.** Recompute the supplied report, including all standards, samples, failed controls, unavailable records and null results. Preserve assumptions, dependencies, conflicts, exclusions (none from fitting), limitations and rejected alternatives. A changed blank rule must be explicitly exploratory and retain the frozen original. No automatic method switching or retry; correct a known input defect before one bounded rerun.
5. **05-handoff — bounded claims and independent review.** Register ordinary domain artifacts and immutable identities with `$science-provenance`, with separate existing claim-register entries. Hand frozen inputs, reference hashes, computation, failed controls, claims and execution record to `$science-review` in record, source and method modes. The coordinator owns rigor classification, independent review and receipt registration. The smallest next action is an independent check of the frozen curve and dilution controls against the supplied synthetic inputs.

## Outputs

Pack-local schemas: `immunoassay-pack-v1`, `immunoassay-design-v1`, `immunoassay-plate-v1`, `immunoassay-report-v1`, `immunoassay-evidence-v1` and `immunoassay-result-v1`. Exact fields, public Python entry points and the one-argument CLI are specified in the stages reference. No fields are added to global manifests, checkpoints, receipts or claim registers.

Return frozen identities, normalized assumptions, complete plate QC, blank mean/CV, constrained fit with parameter errors, standard recoveries, accepted range, unknown statuses, parallelism, claim proposals and `review: unavailable`. The coordinator separately records supported, contradicted, inconclusive and unavailable conclusions. Empty or unavailable evidence requires unavailable status; review approval and computed agreement cannot support a positive claim. One synthetic plate cannot establish replication.

Examples are `examples/workflow-immunoassay-4pl/pack.json` and `pack-noisy.json`; expected results and the negative-case selectors are exercised by `tests/test_workflow_imm_pack.py`. Frozen questions, acceptance criteria and CPU budgets are in `benchmarks/workflow-immunoassay-4pl/tasks.json`. L4 describes synthetic software acceptance under unittest discovery, not a measured assay validation.

## Boundaries

Refuse extrapolation, non-converged fits, undefined inverses, unconstrained asymptotes, dropped standards, ignored parallelism or replicate-CV failures, unlabelled changes to blank subtraction, units mismatches and claims of clinical cutoffs, diagnostic accuracy, regulatory validity or patient-level meaning. Association is never causality; numerical agreement is never physical or clinical validity; reviewer approval is never truth. Failed controls and negative results remain visible.

Every positive claim checks both the declared kind and result of cited records as well as its wording. The stages reference specifies the conservative, incomplete English lexical filter; unlisted paraphrases still require independent review. External, independent and preregistered labels require checked source identities and cannot establish actual independence. A missing record is unavailable rather than negative evidence.

This route is CPU-only, offline and standard-library-only. No network, installation, download, remote job, GPU or heavy compute is authorized. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Local admitted stages need no repeated permission. The validator writes nothing, creates no execution engine and never marks its output reviewed.
