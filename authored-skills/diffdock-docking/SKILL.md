---
name: diffdock-docking
description: "Run a pinned DiffDock release for diffusion-based protein-ligand pose prediction. Use for candidate pose generation from receptor coordinates and ligand structures, especially without a fixed pocket; do not interpret DiffDock confidence as affinity."
license: MIT
---

# DiffDock Docking

## Gate and preflight

Follow `$cx-compute-environment`. Ask once before cloning/installing a pinned
commit, downloading weights, and using GPU compute. Name all network hosts and
never send private structures to a hosted service without approval.

## Workflow

1. Prepare inputs with `$cx-molecular-input-preparation`; record receptor
   assembly/state and every ligand microstate.
2. Pin repository commit, environment lock, checkpoint checksum, inference
   configuration, seed, samples per complex, and hardware.
3. Smoke-test on the upstream example, then predict each complex into an isolated
   output directory. Preserve all generated poses and confidence values.
4. Convert outputs without changing atom order or stereochemistry; verify atom
   mapping and clashes.
5. Treat confidence as within-model pose ranking. Apply
   `$cx-docking-validation`; use an independent affinity model or experiment for
   affinity claims.

## Boundaries

- Confidence is neither probability of binding nor binding affinity.
- Check training/template overlap for benchmark targets and ligands.
- For predicted receptors, report receptor uncertainty and avoid claiming
  precision in low-confidence pockets.

