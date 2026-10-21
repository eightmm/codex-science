---
name: diffdock-docking
description: "Run a pinned DiffDock release for diffusion-based protein-ligand pose prediction. Use for candidate pose generation from receptor coordinates and ligand structures, especially without a fixed pocket; do not interpret DiffDock confidence as affinity."
license: MIT
---

# DiffDock Docking

## Decision contract

State whether the objective is pose generation or pose benchmark evaluation, the target and ligand states, receptor source/state, permitted inference, evidence cutoff, and a prespecified pose acceptance criterion. Assign claim IDs for material pose conclusions and state what control or observation would falsify them. Missing input identity or a benchmark split that cannot be protected is a stop condition.

## Workflow

1. Follow `$cx-compute-environment`. Ask once before cloning/installing a pinned commit, downloading weights, and using GPU compute. Name all network hosts and never send private structures to a hosted service without approval.
2. Prepare inputs with `$cx-molecular-input-preparation`; record receptor assembly/state and every ligand microstate. Validate atom identities, stereochemistry, coordinate frame, and mapping before execution.
3. Pin repository commit, environment lock, checkpoint checksum, inference configuration, seed, samples per complex, and hardware. Record model/training provenance and assess training/template overlap for benchmark targets and ligands.
4. Smoke-test on the upstream example and validate output schema and atom mapping. Then predict each complex into an isolated output directory. Preserve all generated poses, confidence values, logs, and failures.
5. Convert outputs without changing atom order or stereochemistry; verify atom mapping and clashes. Evaluate against a valid reference with a prespecified symmetry-aware pose criterion and an appropriate baseline; preserve all cases and exclusions. Apply `$cx-docking-validation` before any comparative or validation claim.
6. Save inputs, configuration, outputs, environment, and hashes under the run artifact directory with `$science-provenance`. Obtain `$science-review` before presenting material conclusions; distinguish process completion from scientific validation.

## Outputs

Return normalized structures and microstates; a machine-readable complex table with execution status, pose metrics, confidence, controls, exclusion/failure reasons, and reference identity; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty, applicability domain, dependencies, limitations, and smallest falsifiable next action. Keep every generated pose and artifact hash.

## Boundaries

Confidence is neither probability of binding nor binding affinity; it is within-model pose ranking. Use an independent affinity model or experiment for affinity claims. Predicted receptors require explicit uncertainty, especially in low-confidence pockets. Training/template overlap, atom-map failures, missing controls, or invalid references prevent a validation claim. Do not send private structures to hosted services without approval.
