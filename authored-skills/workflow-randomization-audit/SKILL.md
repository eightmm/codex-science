---
name: workflow-randomization-audit
description: "Check seeded allocation of synthetic laboratory or preclinical units to experimental arms, including frozen rules, block and stratum identities, and baseline balance; use for offline arithmetic checks, never study validity."
license: MIT
---

# Randomization allocation audit

A conductor with a bounded analyzer role for synthetic experimental-unit fixtures.

## Decision contract

Freeze the planned allocation question, unit IDs and baseline covariates, population or laboratory system, arms and integer allocation ratio, method, seed and algorithm version, named strata, block size, blinding and allocation-concealment statements, outcome-availability time, minimum units per arm and balance thresholds. Hash the rules including the unit-table path and hash before reading allocation. Record the time of that freeze and the later allocation read. These declarations cannot prove historical timing.

The deliverable answers whether the frozen seeded allocation matches the recorded allocation and whether declared baseline balance thresholds are exceeded. A mismatch, late assignment or ignored threshold falsifies the corresponding arithmetic claim. No physical, biological, causal, confirmatory or clinical inference follows. Missing essential units stay unavailable; never impute them as balanced. Keep imbalance and negative controls visible. Label multiple attempts or inspection after balance as exploratory and preserve the prior draws; never silently re-randomize.

## Reference usage

Read [the progressive reference index](references/index.json) to select references.
Read [the stage and schema contract](references/stages.md) before input admission, computation or claim handling.
Read [the fixed coordinator plan](references/plan.json) before initializing the run's single checkpoint.
Record controlling reference paths and hashes with the existing reference-use-ledger; references guide procedure and supply no scientific evidence.

## Workflow

1. `01-freeze`: fix and hash the rules and unit-table identity before allocation is read. Reuse the five-step manifest plan and one coordinator checkpoint; record code revision and Python version. Stop for a material interpretation-changing choice.
2. `02-table-qc`: inspect exact immutable synthetic unit and allocation identities. Refuse duplicates, nonfinite covariates, missing strata or units, unknown arms, and assignments recorded at or after outcome availability.
3. `03-reproduction`: run `python3 scripts/validate_randomization_audit_pack.py examples/workflow-randomization-audit/pack.json` as the smallest offline smoke input, then the supplied bundle. Regenerate the allocation, compare every unit, check ratio and block capacity, and compute overall and stratum-level continuous standardised mean differences and binary absolute risk differences. Retain threshold flags; never retry for a better balance result.
4. `04-summary`: compare all reported counts, metrics and flags to recomputation. Preserve a disclosed mismatch as `allocation-not-reproduced`, failed controls and negative results. Return bounded descriptive claims with unavailable evidence explicit, applicability, assumptions, dependencies and rejected alternatives. Identify the smallest falsifiable next action: inspect the immutable discrepant allocation row or resolve missing source evidence.
5. `05-handoff`: register domain records as ordinary artifacts and claims separately with `$science-provenance`; hand immutable paths and hashes, failures, limitations and code/environment provenance to coordinator-owned `$science-review`. The pack never certifies its own review or assigns rigor.

## Outputs

The validator emits `randomization-audit-result-v1` JSON with immutable input identities, ordered stages, protocol hash, exact reproduction flag and finding, exploratory label, per-arm and stratum counts, signed continuous SMD and signed binary risk differences with absolute-threshold flags, bounded claims and limitations. `status` remains `arithmetic-only` and `review` remains `unavailable`. Other pack-local shapes are listed in the stage reference and quality declaration.

The fixtures under `examples/workflow-randomization-audit/` and frozen benchmark questions are synthetic software controls. Their expected numbers, failure cases and hashes are inspectable; fixture success is not scientific acceptance. Preserve unsuccessful attempts rather than replacing them. Never reuse a fixture review receipt or copy fixture content as a new study result.

## Boundaries

Only offline, CPU, standard-library arithmetic over synthetic tables is supported. No installation, download, network, new host, GPU, remote or heavy compute is executed. Such actions, restricted transfers and interpretation-changing choices require the coordinator's explicit gate; ordinary read-only stages need no repeated approval.

Refuse overreaching claim wording, positive claims based on computed agreement or review approval, unavailable evidence presented as support, single-bundle replication and internal outputs relabelled as external evidence. Association never establishes causality, numerical agreement never establishes physical or clinical validity, absence is unavailable rather than negative evidence, and approval never establishes truth. The conservative English lexical check is incomplete; independent review must inspect unlisted paraphrases. Zero pooled variance or an arm below the frozen minimum is refused rather than returned as an attractive balance number.

Concurrent calls only read and emit independent JSON. Cancellation leaves the bundle unchanged and may leave partial captured stdout. Capture results atomically outside the input bundle before registering them; the validator has no output-file option. Stop for malformed input, a changed identity or failed required controls; retain their originals for review.
