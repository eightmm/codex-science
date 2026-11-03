# Screening stage and analysis contract

## Stage handoffs

Use the ordered IDs in plan.json with existing pending/completed/blocked semantics.
Each handoff preserves run/stage ID, input/output relative paths and SHA-256,
target/library/mapping identity, software/configuration identity, command/log refs,
attempt counts, status, exclusions, control status and the next unresolved choice.
Changing target state, information boundary, split, ranking or threshold requires
a new frozen contract, never rewriting observed evidence. A hash is not proof of
preregistration; preserve a before-execution snapshot and actual execution log.

Intake emits prepared-input/chemical-state and label provenance; plan emits method,
split and control ledgers; pilot emits actual smoke/redock evidence; execute emits
all attempts and raw outputs; analysis emits the table below; select emits the
qualified shortlist; review emits the existing review receipt and claim register.
No stage output alone establishes later-stage completion.

## Pack-local record

`examples/virtual-screening-campaign/screening.json` is the complete minimal shape.
The offline helper accepts JSON with these fields:

- `schema_version: 1`, `run_id`, `contract`, `contract_sha256`.
- Contract: `target_id`, `score_name`, `score_direction` (`higher`/`lower`),
  `aggregation: best_observed_pose_across_states`, `tie_policy: fractional`,
  positive integer `top_k`, `minimum_ap_gain` in [0,1], `minimum_enrichment` >=1,
  `score_threshold` (finite raw score or null), `evaluation_partition: test`,
  `pocket_source` (`independent_reference`, `explicit_residues`, `validated_prediction`).
- `compounds`: unique `id` and unique `chemical_identity`, target ID, partition
  (`train`, `validation`, `test`), `scaffold_group`, explicit boolean or null
  `active`, and `training_overlap` (`none`, `unknown`, `known`). Identity means the
  prespecified parent compound, not a different ID for each tautomer or pose.
- `states`: unique `id`, valid `compound_id`, and unique per-compound
  `state_identity`. Each compound needs a state; each state needs a planned attempt.
- `planned_attempts`: unique `id`, `state_id`. Enumerate all requested poses/runs
  before execution. Engines with variable emitted modes need an explicit mapping
  from requested runs to emitted poses and failures before using this helper.
- `results`: a subset of planned IDs; `status: ok` requires finite `score`;
  `failed`/`missing` require `reason` and no score. Absent results become explicit
  missing rows. Never omit planned attempts or convert failed scores into zero.
- `controls`: unique `id`, `kind`, boolean `essential`, status (`passed`, `failed`,
  `unavailable`) and `evidence_ref`. At least one essential `positive_redock` and
  all essential controls must pass. Outcome evidence is reviewed separately.

Compute `contract_sha256` using SHA-256 of UTF-8 JSON with sorted keys, compact
separators and no NaN. The helper checks this exact fingerprint. Input/output
file bytes also receive normal provenance hashes; the canonical object fingerprint
does not replace those file hashes.

Run from the verified plugin root:

```sh
python3 scripts/analyze_virtual_screening.py <input.json>
```

Stdout is JSON only. Save it to a new run-local artifact, verify exit code before
registration, and never redirect over inputs or an existing reviewed artifact.
Malformed records produce an error JSON and nonzero exit; valid scientific/control
failures produce an inspectable inconclusive result, not a process exception.

## Metrics and denominator

The supported frozen rule selects each compound's best observed score across all
declared states/poses. It retains every attempt and flags incomplete attempts.
This rule can favor compounds with larger search budgets: compare state/pose
counts, prespecify comparable budgets and evaluate sensitivity before inference.
No averaging of incompatible score fields or scoring functions is supported.

Orient score so larger is better, then use the existing SBDD average-precision
semantics: all tied scores enter at a single threshold. AP is explicitly average
precision, not trapezoidal PR-AUC. At k, allocate a tie group's expected positive
fraction to remaining slots; this is tie-averaged enrichment, not an ordered
top-k shortlist. Report the entire boundary tie group for real selection.
AP baseline is labeled-set prevalence (constant scores); expected random EF is 1.
Metrics use all labeled evaluable test compounds before shortlist filtering.
Both positive and negative labels are required. Missing labels are never negatives.
The helper provides no bootstrap CI and no cross-target aggregation. For material
benchmark claims use target/scaffold-aware uncertainty through docking-validation.

## Failure and decision rules

Reject duplicate compound/state/attempt IDs or chemical identities, wrong parents/
targets, nonfinite scores, invalid labels, known test training overlap, scaffold
groups crossing partitions, leaked/unknown pocket origins and stale contract hashes.
Do not retry invalid inputs silently. Scaffold and training declarations cannot
prove absence of actual leakage; inspect sources and record unresolved overlap.

Failed/unavailable essential controls, unknown training overlap, missing attempts,
missing test labels, absent metric classes, zero retained compounds or failed frozen
metric thresholds produce `acceptance: inconclusive` with reasons. Computed metrics
remain inspectable conditional statistics. `accepted_analysis` requires complete
declared inputs/controls and passing thresholds; it never validates affinity or
experimental binding. Preserve no-label and zero-survivor outcomes and propose the
smallest discriminating action rather than inventing scores or relaxing thresholds.
