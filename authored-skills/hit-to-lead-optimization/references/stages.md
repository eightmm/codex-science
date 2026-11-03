# Stage contracts

## intake

Freeze target, seed/parent chemical identities, objective assay/unit/source-kind and prospective versus held-out purpose.

## plan

Search current generator, property and docking methods; freeze constraints, scaffold/identity splits, controls and selection budget.

## pilot

Check preparation and scoring on the smallest approved control batch before generation or optimization.

## generate

Generate or import candidates; preserve ancestry, source methods, all failed attempts and chemical identity normalization.

## evaluate

Compute or import endpoint-bound properties and matched control results; retain unavailable values.

## select

Apply frozen constraints then cost/diversity-bounded Pareto selection through the existing next-experiment planner.

## review

Register inputs, method identities, full funnel and selection; independently review and define the next falsifying assay.

## Pack-local record

The input uses `schema_version: 1`, a `contract` and its canonical SHA256
(`codex_science.virtual_screening.fingerprint`). Freeze `target_id`, `decision`,
`selection_context` (`prospective` or `held_out_evaluation`), `objectives` and
`selection`. Each objective has `id`, `direction` (`maximize`/`minimize`), `unit`,
`assay_id`, `source_kind` (`measured`/`predicted`/`computed`), optional nonnegative
`weight` (default 1; at least one positive), and optional finite `minimum`/`maximum`.
Selection follows the existing planner: positive `batch_size`,
nonnegative `budget`, positive `diversity_group_cap`, and `minimum_controls`.

Every candidate has a unique `id` and `chemical_identity`, target, nullable parent
ID, `partition` (`train`/`candidate`), declared `scaffold_group`, `training_overlap`
(`none`/`known`/`unknown`), nonnegative `cost`, optional boolean `control`, and
`properties`. Property records carry `value`, `unit`, `assay_id`, `source_kind`;
null/absent required values exclude the row without erasing its denominator.
A parent must exist and ancestry must be acyclic. Scaffold reuse is allowed for
prospective analogue design; a train/candidate scaffold collision is refused for
held-out evaluation. Chemical identity/scaffold declarations are not authenticated
by this helper; normalize stereochemistry, tautomers and protonation upstream.

`controls` contains unique IDs and boolean `passed` outcomes. Missing/failed
controls suppress the proposal. Objective thresholds and overlap exclusions
precede selection. No eligible row or an empty selected batch is inconclusive.
The output preserves all rows, exclusions, eligible count and existing-planner
proposal. Its non-executing information-gain proxy is not an information-theoretic
estimate and the wrapper disables uncertainty weighting. Properties from different
assays, units or source kinds cannot silently share an objective.

## Output and acceptance

Supplied-property ranking and declared-scaffold diversity only. No chemical validation, generator, docking, QSAR/ADMET calibration, measured affinity or synthesis assessment is established.

The synthetic fixture exercises `hit-to-lead-result-v1` only. Preserve every candidate and
exclusion reason; zero survivors and unavailable endpoints are valid outcomes.
A frozen hash detects edits, not prospective preregistration or authentic assays.

## Execution and measured-outcome handoff

The shared [campaign guide](../../../docs/CAMPAIGN_WORKFLOWS.md) documents
`scripts/run_campaign.py INPUT --workspace DIR --state-dir DIR` (planning) and
explicit `--execute`, `--retry-failed`, `--wait-seconds` options. Declare each
stage's input/code/output files and dependencies; stdout helpers can write their
JSON through the shared driver's declared stdout handoff. Use
`capture_campaign_runtime.py` for the real executable and declared model/DB files.

After a new assay, construct a separate `campaign-feedback-v1` input and pass it
with the CSV to `scripts/import_campaign_feedback.py`. Preserve candidate IDs,
candidate construct and target-construct identities, assay units, replicate IDs,
failed/censored outcomes and held-out roles. The initial update is an explicit
parent-outcome heuristic, not a trained surrogate or calibrated active learner.
