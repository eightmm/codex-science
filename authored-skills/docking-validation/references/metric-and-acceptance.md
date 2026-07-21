# Docking metrics and acceptance

Read before computing metrics, fixing thresholds, aggregating poses, or declaring a benchmark pass.

## Pose metrics

Report top-1 and top-k symmetry-aware heavy-atom RMSD, complete distributions, missing poses, and physical or chemical plausibility. Interaction recovery complements RMSD but does not replace geometry.

## Screening metrics

Use PR-AUC and prespecified enrichment metrics as primary measures when actives are rare. Report active/decoy counts, grouping, bootstrap intervals, and per-target results. ROC-AUC is secondary when class imbalance is material.

## Calibration and abstention

A score becomes a probability only after calibration on an appropriate held-out domain. Report reliability, Brier or log loss when relevant, subgroup calibration, and an abstention rule for unsupported chemical or target space.

## Thresholds

Fix metric, direction, threshold, confidence interval method, aggregation, exclusions, and subgroup requirements before inspecting held-out outcomes. Process completion is not an acceptance pass.

## Failure taxonomy

Distinguish preparation failure, unsupported chemistry, engine failure, no pose, invalid pose, geometric failure, interaction failure, ranking failure, calibration failure, and leakage invalidation.
