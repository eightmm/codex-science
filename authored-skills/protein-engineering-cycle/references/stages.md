# Identity and scope

`protein-engineering-input-v1` requires an explicit boolean `synthetic`, a cycle,
construct and assay ID, and one native `protein-variant-input-v1` under
`variant_input`. The native input supplies the canonical reference, numbering
offset, score definitions, controls, model statuses and unique substitutions.
Its initial assay scores must be `missing`: raw replicate rows are authoritative.
Only canonical substitutions are supported; indels require another mapping route.

`variant_roles` covers every variant as `feedback`, `evaluation` or `candidate`.
`model_training_variant_ids` declares supervised evaluation exposure; an evaluation
variant cannot appear there. This check cannot independently inspect training data.
`candidate_parents`, `candidate_costs` and `diversity_groups` each cover every
candidate. Parents must have feedback roles, never evaluation roles. The frozen
`maximum_parent_distance` is a positive integer Hamming-distance cap.

# Measurements and analysis

Each measurement records `variant_id`, `construct_id`, `assay_id`, `units`,
`independent_replicate_id`, `status` and `value`. `ok` requires a finite number;
`failed`/`missing` require null and a reason. The variant/replicate pair is unique.
The caller must aggregate technical repeats and distinguish independent cultures
or biological units before import. Values, including negative outcomes, remain
in the output with all failed and missing rows.

The helper averages successful independent replicate values within each variant.
SE is the sample standard deviation divided by sqrt(n), available only for n>1.
`minimum_replicates` must be >=2. An observed feedback parent needs that many
successful replicates to inform selection; failed or missing records do not
count. Evaluation-only Spearman uses complete, sufficient evaluation variants
and the native tie-aware rank implementation. It never contributes to planning.

# Selection and failure semantics

`objective_weights` contains nonnegative `parent_observed` and `supplied_model`
weights with a positive total. Multiply assay/model values by their declared
direction to form utilities, then use the existing next-experiment planner's
separate per-objective normalization, Pareto fronts and budget/diversity
constraints. Raw model scores are never averaged with assay values: different
explicit score units are allowed because only normalized dimensionless objectives
are combined. Positive affine rescaling within either objective preserves
normalized objectives up to floating-point precision. This arithmetic invariance
is not model/assay calibration. All uncertainty
selection bonuses are zero: an SE is not information gain or calibrated model
uncertainty. The proposal retains the planner's `executed: false` boundary.

Failed/unavailable essential controls, insufficient parent replicates or missing
model scores exclude the candidate with reasons. Zero eligible candidates returns
`no-admissible-candidates` and null proposal rather than throwing away the run.
Identity/unit/WT/role inconsistencies, evaluation leakage and duplicate replicate
rows are input failures. No auto repair or silent assay transfer is permitted.

# Review and handoff

Register the frozen input, all measurement rows, supplied score provenance,
analysis result and relevant method descriptor as ordinary artifacts in the same
coordinator run. Independent review checks the role split, construct/assay mapping,
replicate independence and exclusions. A passed computation is not measured
fitness improvement; the next falsifiable validation is a new matched assay.
