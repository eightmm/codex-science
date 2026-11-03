---
name: workflow-experiment-design
description: "Conduct a fixed six-stage preregistered experiment-design procedure for lab or computational studies, from question and independent-unit power planning through randomisation, frozen analysis, controls and independent review handoff. Audit a finished analysis against its frozen plan and label every deviation exploratory. Use before collection or for post-hoc audit; this pack does not run experiments or establish causal, physical or clinical validity."
license: MIT
---

# Workflow Experiment Design

This conductor fixes order, validation gates and immutable handoffs around
`$cx-statistical-inference-experimental-design`, `$cx-statistical-decision-analysis`
and `$cx-experimental-uncertainty-propagation`. Load their selected references;
reuse their methods and existing statistics runtime without restating them.
The coordinator retains rigor classification and independent `$science-review`.

## Decision contract

Before seeing outcomes, state the question, estimand, population/system,
observation window, experimental unit, observational unit, assignment mechanism,
primary outcome, baseline, claim IDs, falsifier and permitted inference.
Distinguish assignment units from technical observations: images, cells,
repeated runs or time points do not increase the independent sample count.
Freeze the primary family and thresholds, missing-data and exclusion rules,
stopping, controls, assumed effect, variance source, attrition and per-unit cost.
Use only externally justified or genuinely independent pilot effect assumptions;
this study's own result cannot supply its planning effect size.
Record uncertainties, sensitivity alternatives, rejected methods and applicability.
Stop for an unresolved choice that changes interpretation; infer reversible details.

## Reference usage

Read [stages](references/stages.md) before preregistration, frozen-plan handoff
or post-hoc audit, and [the local record contract](references/records.md) before
authoring records or invoking the validator. Use [the ordered plan](references/plan.json)
as the existing manifest `plan` array; do not introduce a new step shape.
Consult [the reference index](references/index.json) for controlled routes.
Record materially controlling reference paths and SHA-256 values in the existing
`reference-use-ledger`; reference instructions are procedure, not study evidence.

## Workflow

1. **State the question.** Use `$cx-statistical-inference-experimental-design` to
   fix the question, estimand, assignment unit/mechanism and primary outcome
   before any outcome is seen. Save `question.json` and its hash.
2. **Plan power, sample and cost.** Use the same design skill, the uncertainty
   skill for variance provenance, and the decision skill for cost-sensitive
   alternatives. Save effect/variance source identities and `power.json` with
   analyzable and recruited counts per arm, allocation, attrition, target power,
   cost per unit and cost unit. The validator checks a declared two-group normal
   approximation; specialist designs require specialist methods and review.
3. **Plan randomisation and blinding.** Save `randomisation.json` with assignment
   and blinding seeds, allocation method and concealment. Record why full masking
   is impossible when applicable; never silently pretend it occurred.
4. **Freeze analysis.** Save `analysis-plan.json`, hash its exact bytes, and
   record the primary family, multiplicity, thresholds, missingness, stopping
   and exclusions. Sequential designs require an explicit stopping rule and
   error-control specification; fixed-horizon power does not validate monitoring.
5. **Declare controls and negative-result handling.** Save `controls.json` with
   control IDs, failure handling and retention of negative, null, failed and
   unavailable results. A failed control withholds material interpretation.
6. **Hand off independently before collection.** Save `handoff.json` binding
   all five inputs by path plus hash. Validate `preregister.json`, then hand
   the packet to `$science-review` through the coordinator before collection.
   `ready-for-independent-review` is a handoff status, never review approval.

For a finished study, select `--mode audit`: preserve the frozen bytes and the
plan actually used, snapshot the complete results inventory, compare the
analysis family and rules, and label every changed outcome, added/dropped
comparison, changed threshold or post-hoc exclusion `exploratory` with a reason.
Retain failed controls and all negative/null/unavailable results unchanged.
Never rewrite the original plan to erase a deviation. Recheck after correcting
the record; stop rather than repeatedly relaxing validation to obtain a pass.

## Outputs

Save the six stage records, a pack index, validator report, source assumptions
and immutable input identities; audit adds the used plan, analysis, complete
results inventory and exhaustive exploratory deviation list. Local schema
names and exact fields are in [records](references/records.md).
Return supported, contradicted, inconclusive and unavailable claim IDs,
dependencies/conflicts, sensitivity and uncertainty, rejected alternatives,
limitations, and the smallest falsifiable next action. Keep domain records as
ordinary manifest artifacts, with separate claim-register entries; do not add
global schema keys or interpret local audit statuses as claim-register statuses.
Register every path and SHA-256 through `$science-provenance`.
Use one coordinator checkpoint per run with the six ordered stage IDs; advance
existing manifest/checkpoint steps through their existing commands.
Record revisions as new files and invalidate stale review through the existing
review flow. The producer never marks its own output reviewed.

## Boundaries

The validator refuses hash mismatches, pseudoreplication, own-result power,
unlabelled post-hoc changes, ignored multiplicity, unaccounted allocation or
attrition, absent stopping, and omitted negative/null results. It also refuses
association promoted to causality, numerical agreement promoted to physical or
clinical validity, unavailable evidence promoted to negative evidence, and
review approval promoted to truth. Failed controls and negative results remain.
These checks validate records, not actual masking, timing or scientific truth.
No experiment execution, installation, network, download, GPU, remote or heavy
compute is performed. The checked-in examples are synthetic fixtures only.
Stop at authority gates before installation, restricted transfers, a new host,
GPU/remote/heavy compute or interpretation-changing choices; ordinary stage
progress requires no repeated human approval. Essential missing records are
`unavailable`, never fabricated and never counted as negative evidence.
Require independent `$science-review` for the precollection handoff and for
material post-hoc interpretation; approval never establishes truth.
