---
name: workflow-flow-cytometry-qc
description: "Check already-acquired synthetic flow cytometry event tables against frozen compensation, singlet, live/dead and channel gates; return control-qualified counts and parent-relative percentages. Use for offline cytometry QC arithmetic, never cell identity, function or disease interpretation."
license: MIT
---

# Flow Cytometry QC

This conductor checks synthetic fixtures on the CPU, offline, using the Python
standard library. It composes rule freezing, event identity checks, compensation,
ordered gates, explicit missingness and coordinator-owned independent review.
It does not acquire events or change instrument settings.

## Decision contract

Freeze the panel with channels and fluorochromes, linear units, compensation
matrix and source identity, time-bin stability bound, area/height singlet bounds,
live/dead threshold, interval or rectangular population gates, and the FMO or
isotype control for each boundary before opening event tables. Freeze the gate
order, minimum events in a gate and minimum parent denominator for a percentage.
Record the question, sample/control identities, acquisition time units, claim IDs,
evidence cutoff, applicability, falsifier and exact code/Python revision.

The deliverable is a reproducible count/denominator table for supplied synthetic
events. The baseline is hand-checked arithmetic with unchanged frozen rules.
Acceptance requires correct compensation, every exclusion, FMO and stability
controls passing, preserved unavailable values and no interpretation beyond QC.
Threshold changes after sample outcomes require an explicit exploratory label
and a new immutable rule snapshot. Hashes cannot establish historical timing.

## Reference usage

Read [the reference index](references/index.json) to select controlling material.
Read [stages and local schemas](references/stages.md) before rule freeze, event
admission, compensation, gating or claim checking. Read [the manifest plan](references/plan.json)
before creating the run's one checkpoint. Register controlling reference hashes
in the existing reference-use-ledger through $science-provenance.

## Workflow

1. **01-rule-freeze.** Hash rules and their compensation source before events
   are read. Retain original thresholds; disclose outcome-informed choices as
   exploratory. Refuse a singular matrix or an unknown channel.
2. **02-event-qc.** Admit immutable path-plus-SHA-256 identities. Require unique
   event IDs, matching named channels, finite non-negative raw intensities,
   declared units/linear scale and monotonic per-sample time. Preserve unavailable
   samples distinctly. Already-compensated input is refused.
3. **03-compensation-gates.** Solve the measured-to-true linear system with
   partial-pivot Gaussian elimination. Apply stability, singlets, live events
   and population gates in frozen order. Check control positive percentages
   against frozen maxima. Preserve failed controls as failures; never bypass them.
4. **04-summary.** Compare reported counts, parent denominators, percentages,
   FMO checks and time-bin rates against the reference result. Small gates retain
   counts and percentage `unavailable`; missing samples never become zero.
   Preserve exclusions, failed controls, negative results and all limitations.
5. **05-handoff.** Register ordinary domain artifacts and separate claim-register
   entries with $science-provenance. Reuse one checkpoint with the ordered IDs.
   Give $science-review the frozen plan, manifest, input/output hashes, claims,
   assumptions, failed controls, dependency records and code/environment identity.
   The coordinator owns rigor classification and independent review; this pack
   never labels its output reviewed.

Use `python3 scripts/validate_flow_cytometry_qc_pack.py examples/workflow-flow-cytometry-qc/pack.json`
for the smallest offline synthetic smoke case. Correct an invalid input or report,
then rerun once; retain the failed record. Do not change thresholds to pass.
No network, downloads, installation, remote compute or GPU execution is needed.

## Outputs

Return the pack-local result described in the stages reference, frozen rules,
synthetic event table, computed report and immutable path/hash handoffs. Return
normalized assumptions, source dependencies, uncertainty, exclusions and rejected
alternatives. Keep supported, contradicted, inconclusive and unavailable claim
IDs in the coordinator's existing claim register; this pack does not extend it.
The smallest next action is independent checking of the frozen rule placement
and the counted exclusions against the supplied synthetic events.

The validator writes nothing and emits JSON on stdout. A refusal emits JSON on
stderr with `finding` and exit 2, including argument errors. `--help` is plain
usage on stdout with exit 0. There is exactly one positional bundle argument.

## Boundaries

Counts cannot identify a cell population, establish function, disease association,
diagnostic or clinical relevance. Association is never causality; numerical
agreement is never physical or clinical validity; review approval is never truth.
Missing evidence is `unavailable`, never negative evidence. A single synthetic
fixture cannot establish replication. Preserve failed controls and negative results.

Stop on missing essential inputs, altered hashes, invalid events, duplicate IDs,
failed FMO/stability controls, omitted exclusions or overreaching claim wording.
Do not silently compensate twice, repair values, substitute controls or re-place
gates. Positive claims cannot cite computed or review-approval records; unavailable
sources force unavailable claims. The English lexical wording gate is conservative
and incomplete for paraphrases; independent method/source/record review is required.

Proceed within the offline CPU scope without stage-by-stage permission prompts.
Human gates apply before installation, restricted transfers, new hosts, remote,
GPU or heavy compute, and interpretation-changing choices. These actions require
separate authority and are outside this fixture validator.
