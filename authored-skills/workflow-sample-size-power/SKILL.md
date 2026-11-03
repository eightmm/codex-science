---
name: workflow-sample-size-power
description: "Check frozen sample sizes, detectable effects, multiplicity and attrition for planned two-group continuous or binary laboratory and preclinical outcomes; exclude clinical trial design and observed-power arguments."
license: MIT
---

# Frozen Sample Sizes and Detectable Effects

This conductor checks prospective normal-approximation arithmetic from supplied assumptions. It composes the existing `$cx-experimental-uncertainty-propagation` skill for uncertainty interpretation, `$science-provenance` for artifact registration and `$science-review` for independent review. It supplies no execution engine and never attests its own review.

## Reference usage

Read [stages and local records](references/stages.md) before freezing assumptions, computing numbers, validating a bundle or interpreting claims. Read [the ordered plan](references/plan.json) before creating the coordinator's single checkpoint. [The reference index](references/index.json) declares controlled operations. Record each controlling reference path and SHA-256 in the existing `reference-use-ledger`; a reference is procedure, never scientific evidence.

## Decision contract

Freeze the laboratory or preclinical system, planned two-group comparison, independent experimental unit, continuous or binary outcome, units, time horizon, prior-source cutoff and descriptive claim IDs before any outcome data exist. This pack excludes clinical trial design. The deliverable is a checked arithmetic scenario, with no conclusion about study adequacy or benefit.

Freeze sidedness and any one-sided justification, family alpha, multiplicity count and Bonferroni-adjusted alpha, target power, allocation ratio, minimum analyzable arm size, standard deviation or control proportion with its uncertainty range and source, minimum effect of interest justified by a prior record, plausible outcome range, attrition and sensitivity grid size. Every number needs a source or an explicit assumption label and rationale. Hash assumptions before outcomes; never select an effect from this study's own outcomes. Changes after outcomes require a preserved exploratory revision.

The acceptance criterion is reproduction of the frozen formulas and per-arm ceilings, with absolute numeric tolerance `1e-9`. Sensitivity covers the frozen nuisance endpoints. This checks arithmetic conditional on assumptions; dependence, estimated variance, small samples and source authenticity remain limitations. A changed assumption hash, failed control or mismatched power falsifies acceptance and remains visible.

## Workflow

Use one coordinator checkpoint and the exact ordered stage IDs in the plan. Execute only offline CPU operations with the standard library. Pin the repository revision, Python version and hashes of supplied source records; preserve originals and rejected alternatives.

1. **01-freeze:** record the decision contract, prior source identities and timing; hash the frozen assumptions before outcomes. Resolve only material interpretation choices with the human owner.
2. **02-qc:** validate provenance, real numeric types, probability and plausible-effect bounds, directional justification and multiplicity. Reject missing essential inputs instead of repairing them.
3. **03-computation:** use `reference_computation` from `codex_science.sample_size_power_pack` for the frozen normal formulas, sensitivity grid and per-arm attrition inflation. The three supplied synthetic fixtures are smoke controls, never observations.
4. **04-consistency:** run `python3 scripts/validate_sample_size_power_pack.py examples/workflow-sample-size-power/pack.json` for the synthetic smoke case, then the supplied bundle. The CLI accepts one bundle argument, writes nothing and emits JSON; refusal goes to stderr with exit 2. Check stated arm sizes before numeric tolerance. Preserve the refusal and failed controls; do not tune assumptions until the check passes.
5. **05-handoff:** register domain records as ordinary hashed artifacts, maintain separate claim-register entries, complete the matching coordinator plan/checkpoint steps and send the decision contract, sensitivity, source dependencies, rejected inputs and negative results to `$science-review`. Rigor classification and review approval stay with the coordinator.

No automatic retry changes inputs or methods. After correcting a demonstrated input error, preserve the original and create a new version with a recorded reason. Missing sources remain unavailable. Null, negative, conflicting and failed-control results are retained.

## Outputs

Return frozen normalized assumptions, path-plus-hash source identities, the computation and sensitivity table, QC refusals, dependencies/conflicts, limitations, excluded alternatives with reasons, and the smallest falsifiable next action (usually independent source/assumption review). The five pack-local schema names and exact fields are in the stages reference. The validator result has `evidence_level: arithmetic-only` and `review: unavailable`.

Assign stable claim IDs with status, required support, falsifier, support/contradiction, dependency, uncertainty and applicability in the existing separate claim register. Reconcile supported, contradicted, inconclusive and unavailable claims there; do not extend global payloads or use a domain record as a claim register. Register paths and SHA-256 through `$science-provenance`, including the immutable negative results and reference-use ledger.

## Boundaries

Refuse observed power as support for a null result, own-outcome effect selection, uncorrected multiplicity, unjustified one-sided tests, unrounded arm sizes, ignored attrition and inconsistent power. Refuse claims of adequacy, benefit, clinical meaning or no effect from a non-significant result. Association never establishes causality; computed agreement never establishes physical or clinical validity; review approval never establishes truth. Missing records are unavailable, never negative evidence.

The conservative English lexical claim gate and evidence rules in the stages reference apply regardless of a claim's declared label. They are incomplete and require independent review. A single synthetic fixture cannot establish replication. Positive claims cannot cite computed records, review approval or unavailable records.

Proceed with authorized reversible local checks. Human gates occur only before installation, restricted transfer, a new host, GPU/remote/heavy compute or a material interpretation-changing choice. This pack requests none of those operations. Stop for essential missing input, clinical trial requests or incompatible assumptions; record the blocker in the coordinator checkpoint. Every material conclusion requires `$science-review`; software acceptance is never scientific admission.
