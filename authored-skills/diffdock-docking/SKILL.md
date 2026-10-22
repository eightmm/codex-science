---
name: diffdock-docking
description: "Run a pinned DiffDock release for diffusion-based protein-ligand pose prediction. Use for candidate pose generation from receptor coordinates and ligand structures, especially without a fixed pocket; do not interpret DiffDock confidence as affinity."
license: MIT
---

# DiffDock Docking

## Decision contract

State whether the objective is pose generation or pose benchmark evaluation, the target and ligand states, receptor source/state, permitted inference, evidence cutoff, and a prespecified pose acceptance criterion. Assign claim IDs for material pose conclusions and state what control or observation would falsify them. Missing input identity or a benchmark split that cannot be protected is a stop condition. Separate execution, pose recovery, model confidence/ranking, affinity, and experimental validity claims.

## Reference usage

Read [diffdock-evidence-and-controls.md](references/diffdock-evidence-and-controls.md) before interpreting confidence or generated-pose samples, designing a pose benchmark, evaluating training/template overlap, or reporting sensitivity and applicability. Read it before comparing model checkpoints or inference configurations.

## Workflow

1. **Gates (ask before proceeding).** Follow `$cx-compute-environment`; ask once before cloning/installing a pinned commit, downloading weights, and using GPU compute. Name all network hosts and never send private structures to a hosted service without approval. Record approvals, host boundaries, and the frozen task.
2. Prepare inputs with `$cx-molecular-input-preparation`; identify receptor assembly/state and every ligand microstate. Validate atom identities, stereochemistry, coordinate frame, and mapping; record preparation provenance and unresolved structure uncertainty.
3. State pose generation or benchmark evaluation, freeze claim IDs, split, pose criterion, reference identity, and falsifying observations; stop if held-out poses or split identity cannot be protected. Record denominator and reference use.
4. Pin repository commit, environment lock, checkpoint checksum, inference configuration, seed, samples per complex, and hardware. Record model/training provenance and assess training/template overlap for benchmark targets and ligands.
5. Smoke-test on the upstream example and validate output schema and atom mapping; record diagnostics, expected fields, and acceptance checks before processing evaluation cases.
6. Predict each complex into an isolated output directory; preserve all generated poses, confidence values, logs, and failures. Record every attempt, seed/sample identity, and execution status.
7. Convert outputs without changing atom order or stereochemistry; verify atom mapping and clashes. Evaluate against a valid reference using a prespecified symmetry-aware pose criterion and appropriate baseline; preserve all cases and exclusions, and apply `$cx-docking-validation` before comparative or validation claims.
8. **Verify/check.** Check model/checkpoint identity, atom maps, reference leakage, pose metrics, control outcomes, denominator, hashes, and claim-to-artifact links; record failed checks and keep affected claims inconclusive.
9. Save inputs, configuration, outputs, environment, material reference-use hashes, and hashes under the run artifact directory with `$science-provenance`; obtain `$science-review` before material conclusions and record uncertainty, domain limits, and the next discriminating action.

## Outputs

Return a `diffdock-pose-evidence-v1` record with required fields: run identity (`run_id`); claim register (`claim_register`); input identity (`input_identity`); model identity (`model_identity`); per-complex execution table (`execution_table`); control results (`controls`); pose evaluation (`pose_evaluation`); confidence interpretation (`confidence_interpretation`); uncertainty (`uncertainty`); applicability domain (`applicability_domain`); failures and exclusions (`failures_and_exclusions`); artifact hashes (`artifact_hashes`); hash-bound reference-use ledger (`reference_use_ledger`); and next action (`next_action`). Include normalized structures and microstates and a machine-readable complex table with execution status, pose metrics, confidence, controls, exclusion/failure reasons, and reference identity. Mark claims supported, contradicted, inconclusive, or unavailable. Keep every generated pose and artifact hash.

## Boundaries

Confidence is neither probability of binding nor binding affinity; it is a within-model pose-ranking output whose calibration and meaning depend on the pinned checkpoint and evaluation domain. Use an independent affinity model or experiment for affinity claims. Predicted receptors require explicit uncertainty, especially in low-confidence pockets. Training/template overlap, atom-map failures, missing controls, or invalid references prevent a validation claim. Do not send private structures to hosted services without approval. Process completion and high confidence do not establish experimental validity.
