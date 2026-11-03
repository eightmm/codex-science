---
name: workflow-stability-shelf-life
description: "Check synthetic attribute measurements over storage time using frozen batch pooling and a one-sided mean bound against a specification. Use for supplied stability-study fixtures with censored-value controls and capped extrapolation; refuse expiry or product suitability conclusions."
license: MIT
---

# Stability regression arithmetic

This conductor checks supplied synthetic fixtures only. It adds no execution engine,
performs no measurements and cannot assign a labelled shelf life.

## Decision contract

Freeze the attribute, units, time unit, storage condition, specification limit and
direction, batch identities, increasing time grid including zero, minimum batches
and time points, linear model, sequential slope/intercept poolability rule and its
significance level, one-sided 95 percent mean-response bound and extrapolation
multiple. Hash the protocol before admitting results. The example freezes three
batches, four times, alpha 0.25 and twice the observed duration. A hash records
identity; historical freeze timing remains unverified.

The deliverable is descriptive arithmetic on synthetic measured values. A failed
poolability test selects individual fits. The earliest bound crossing is a
numerical result conditional on model assumptions. It cannot establish product
quality, safety, expiry, regulatory acceptability or clinical relevance. A changed
specification after outcomes needs an exploratory label and recomputation.

## Reference usage

Read [references/index.json](references/index.json), then [references/stages.md](references/stages.md) before protocol freeze,
data admission, computation or claim writing. Read [references/plan.json](references/plan.json) before
creating the coordinator plan. Record each controlling reference path and SHA-256
in the existing reference-use-ledger through `$science-provenance`. References
constrain procedure; they are not evidence. Never guess fields or command options.

## Workflow

1. **01-rule-freeze.** Create and hash the immutable synthetic protocol before
   reading results; use the existing manifest plan step shape. Keep one checkpoint
   for the run, with the five ordered stage IDs from `references/plan.json`.
2. **02-data-qc.** Admit hash-bound batch/time measurements, finite results and
   consistent units. Refuse duplicate, non-increasing, negative or missing baseline
   times and counts below the frozen minima. Carry below-quantification values as
   null censored results with their limits. Retain them; this OLS reference refuses
   censored fits rather than replacing them with zero.
3. **03-regression.** Run the small CPU-only synthetic fixture first with
   `python3 scripts/validate_stability_shelf_life_pack.py examples/workflow-stability-shelf-life/pack.json`.
   Compute each batch fit, slope-equality F test, then intercept-equality F test
   only if slopes permit it. Pool only if both pass. Use the appropriate one-sided
   mean-response confidence bound and solve its earliest crossing only inside the
   frozen horizon. Never substitute a prediction interval or two-sided bound.
4. **04-summary.** Preserve n, residual degrees of freedom, both test outcomes or
   the explicit skipped-intercept status, selected model, observed duration,
   extrapolation cap and crossing or `not-reached-within-observed-range`. Record
   failed controls, negative results, excluded alternatives and assumptions.
5. **05-handoff.** Register immutable path-plus-hash domain records as ordinary
   artifacts, and adjudicate claim IDs separately in the existing claim-register.
   Use `$science-provenance` and coordinator-owned `$science-review`; this pack
   leaves review unavailable and never attests independent review or rigor.

The validator reads only, writes nothing, uses no network, installation, new host,
GPU, remote or heavy compute. Correct one specific malformed input and rerun once;
preserve the refusal and original files. Missing essential input is unavailable.
Never weaken a control or discard a negative result to obtain acceptance.

## Outputs

Pack-local records are `stability-shelf-life-pack-v1`,
`stability-shelf-life-protocol-v1`, `stability-shelf-life-data-v1`,
`stability-shelf-life-report-v1`, `stability-shelf-life-evidence-v1` and the returned
`stability-shelf-life-result-v1`. Fixture-only expected and negative-case envelopes
are specified in `references/stages.md`. None changes global sidecar schemas.

Return normalized inputs and assumptions, artifact identities and execution
provenance, per-batch and selected fits, poolability tests, pointwise uncertainty,
counts and degrees of freedom, conflicts and shared dependencies, unavailable
review and bounded claims. Maintain supported, contradicted, inconclusive and
unavailable claim IDs in the coordinator's existing register; computed records
cannot justify a positive claim status. Attach the smallest falsifiable next
check: inspect whether new synthetic observations violate the linear residual
assumptions before revising the frozen model in a separately labelled run.

## Boundaries

Refuse association presented as causality, numerical agreement presented as
physical or clinical validity, review approval presented as truth, and absent
records presented as negative evidence. Positive claim statuses cannot cite
computed or review-approval records. Any unavailable citation requires unavailable
status; empty evidence requires unavailable status. One synthetic fixture cannot
establish replication. Labels such as external, independent or preregistered
cannot override a source path or hash alias of this study's own artifacts.

The lexical claim guard is conservative, English-only and incomplete, including
negations; its exact wording families and additional domain refusals are in
`references/stages.md`. Do not paraphrase around a refusal. Independent source,
record and method review, model adequacy, residual normality, equal variance and
independence remain unverified. A pointwise confidence bound is not simultaneous
coverage across all times or batches. No result from this pack labels shelf life.

Stop for missing immutable input, failed QC, censored fitting, degenerate
regression or a material interpretation-changing choice. Ask the human only
before an interpretation-changing change, installation, restricted transfer,
new host or GPU/remote/heavy compute; the offline fixture requires none of those.
