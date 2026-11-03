---
name: workflow-meta-analysis-evidence
description: "Pool already-extracted study effects with frozen eligibility, cohort deduplication, comparable scales, heterogeneity and sensitivity gates. Use for quantitative evidence synthesis; use literature-review for retrieval. Never infer causality or patient care."
license: MIT
---

# Meta-analysis Evidence

Role: conductor. Consume already-extracted study effects through five fixed
stages. Reuse `$cx-literature-review` for retrieval, study identity, `cohort_id`
and `independence_group`; this pack adds no retrieval or execution engine.

## Decision contract

Freeze the question, population/system, eligibility and evidence cutoff in the
question and eligibility text, effect measure, sign convention, unit, fixed or
random model, minimum independent studies, I squared and tau squared thresholds,
and subgroup list before reading extracted effects. Hash the complete protocol.
A material change creates a new revision and an exploratory interpretation; never
silently rewrite the frozen record. The deliverable is statistical evidence only.
Association never establishes causality, physical validity or clinical validity.

The coordinator owns rigor classification and one existing checkpoint per run,
with ordered IDs `stage-01` through `stage-05`. Reuse the manifest `plan` fields
in [the template](references/plan.json). The pack cannot certify its own review.
Missing essential choices stop dependent interpretation. Record assumptions,
source bias, applicability, uncertainty, contradictions and a falsifier before
synthesis. Synthetic examples are fixtures, never scientific evidence.

## Reference usage

Read [stages and schemas](references/stages.md) before protocol freeze, any
hash-bound handoff, pooling or claim validation. Read [plan](references/plan.json)
before registering coordinator steps. Select via `references/index.json` and
record controlling paths plus hashes in the existing `reference-use-ledger`
through `$science-provenance`. References constrain procedure, not source truth.

## Workflow

1. **Protocol freeze.** Write `protocol.json`, preserving eligibility, effect
   direction, thresholds and rejected alternatives. Hash it before inspecting
   `studies.json`. Freeze model and minimum independent studies (at least two).
2. **Extraction.** Reuse the literature-review study and cohort identities.
   Record effect, positive variance or standard error, both sample sizes, scale,
   unit, participant identities and source output paths plus hashes. Preserve
   negative, unavailable and failed-control records without inventing values.
   The complete table, including excluded rows, must contain at most 200 studies.
3. **Independence and comparability.** Count each cohort, independence group
   and participant once; explicitly exclude duplicates with reasons. Refuse
   mixed scales or opposite direction, and different units without a recorded
   positive conversion applied to effects and squared to variances. Record
   every exclusion and subgroup's timing; post-result changes must be labelled
   exploratory. Retain all original rows, including failed controls.
4. **Pooling and sensitivity.** Use the stdlib reference calculation in
   `src/codex_science/meta_analysis_pack.py` on harmonized independent effects.
   Record inverse-variance fixed effect and DerSimonian-Laird random effects,
   normal 95% intervals, Cochran Q, tau squared, I squared and leave-one-out
   estimates. Disclose every sign reversal. A fixed-effect headline is refused
   when either frozen heterogeneity threshold is exceeded. An inadequate study
   count makes pooling unavailable; no pooled estimate or positive synthesis
   claim is allowed. The descriptive Egger intercept is exploratory and unavailable with fewer
   than three studies or constant precision; it never diagnoses publication bias.
5. **Bounded claims and review handoff.** Run `python3
   scripts/validate_meta_analysis_pack.py <bundle-directory>` from the repository
   root. Resolve all refusals as one batch without hiding failed or negative
   evidence, or retain unavailable output. Register each domain record as an
   ordinary artifact, with separate existing `claims.json` claim-register entries.
   Hand protocol, records, conversions, exclusions, dependencies, sensitivity,
   limitations and immutable hashes to independent `$science-review` in record,
   source and method modes. Review remains pending until the coordinator's
   independent process finishes. Producer rechecking is not independent review.

Start with the offline synthetic fixture at
`examples/workflow-meta-analysis-evidence/synthetic/`; it has a planted
heterogeneous effect and a leave-one-out sign reversal. No network, installation,
remote compute or GPU action is implemented. A failed check is retained; do not
retry unchanged inputs or weaken thresholds to obtain a pass.

## Outputs

Return `pack.json` and its five ordered stage references: `protocol.json`,
`studies.json`, `gate.json`, `pooling.json`, `handoff.json`; plus `evidence.json`,
hashed source records, one hash-bound existing `checkpoint.json`, and separate
`claims.json`. Exact pack-local schemas,
field types, limits and the read-only validation result are in the stages
reference. The plan uses only existing fields, and introduces no global schema,
receipt or claim-register key. Register hashes with `$science-provenance`.

Also return normalized assumptions, dependencies, conflicts, applicability,
uncertainty, exclusion rationale, rejected alternatives, unavailable claim IDs,
failed controls, negative results and the smallest falsifiable next action.
A numerical match is record consistency, never empirical validation. Review
approval never becomes evidence of truth.

## Boundaries

Refuse overlapping cohorts/participants, scale or sign mixing, undocumented unit
conversion, missing/non-positive variance, inadequate study counts, undisclosed
sensitivity reversals, non-exploratory post-result choices and heterogeneity-rule
violations. Positive claims cannot cite review approval or computed records,
regardless of their inference label. Conservative wording checks refuse causal,
therapeutic, clinical-action, efficacy, binding, affinity, inhibition, activation
and mechanism wording; see the exact list in the stages reference. Empty claim
support requires `unavailable`, which cannot assert positive evidence. Missing
evidence is `unavailable`, never negative evidence.

Human gates apply only before installation, restricted transfer, a new host,
GPU/remote/heavy compute or interpretation-changing choices. Routine reversible
offline work proceeds. This pack authorizes none of those gated actions. Preserve
source restrictions and privacy; never include identifying participant data in a
redistributed fixture. Real participant linkage requires an approved local,
pseudonymous identity scheme and independent assessment of its completeness.

L4 means the checked-in synthetic acceptance and seeded refusals are exercised;
it establishes no live-source fidelity, chronological proof of preregistration,
semantic completeness, physical validity or clinical recommendation.
