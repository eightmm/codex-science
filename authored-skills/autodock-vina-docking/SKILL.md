---
name: autodock-vina-docking
description: "Run reproducible local protein-ligand docking with AutoDock Vina and Meeko. Use for pose generation, redocking, or small virtual screens when a receptor and a justified binding pocket are available; do not use a Vina score as experimental affinity."
license: MIT
---

# AutoDock Vina Docking

## Decision contract

Define whether the deliverable is a pose, a redocking validation, or an exploratory ranking; identify receptor, ligand microstates, intended pocket, evidence cutoff, and a prespecified pose-success criterion. Treat docking as pose generation, not affinity measurement. Record claim IDs and the control or observation that could falsify each material pose claim. A missing receptor state, ligand state, or pocket definition that changes the question is a stop condition.

## Workflow

1. Follow `$cx-compute-environment` and ask once before installing pinned Vina, Meeko, or preparation dependencies and before compute. Require `$cx-molecular-input-preparation` outputs and an explicit pocket definition.
2. Validate atom mapping, stereochemistry, charges, receptor assembly/state, and pocket coordinates. Record Vina/Meeko versions, receptor state, ligand microstates, box center and size in Å, exhaustiveness, modes, energy range, CPU count, and seed.
3. Smoke-test one ligand. Confirm the search box encloses the intended pocket and each ligand can rotate without clipping. Run a positive-control redock before screening.
4. Retain raw PDBQT, log, config, and converted SDF poses under `artifacts/<run-id>/vina/`. For a screen, process each ligand state independently and preserve failures; never silently keep only successful molecules.
5. Compare poses using a prespecified criterion, commonly top-k symmetry-aware heavy-atom RMSD to a valid reference pose. Keep pose ranking separate from compound ranking. Use cold-target/ligand controls and decoys for comparative screening claims; then apply `$cx-docking-validation`.
6. Record commands, environment, control results, exclusions, and artifacts with `$science-provenance`; obtain `$science-review` before material conclusions.

## Outputs

Return normalized receptor/ligand-state inputs; a machine-readable per-ligand execution table with status, score, pose criterion, control result, and failure reason; supported, contradicted, inconclusive, and unavailable claim IDs; pose diversity, uncertainty, exclusions, limitations, and next discriminating action. Preserve apo/holo and assembly/template provenance and hashes. Process completion is not scientific validation.

## Boundaries

Vina energy is a model score, not measured binding free energy or IC50/Kd. A score or successful run alone cannot establish affinity, binding, or enrichment. Do not leak a held-out bound pose into pocket construction or ligand initialization. Invalid or mismatched atom states, failed controls, or an undefined pocket leave conclusions inconclusive. Report applicability limits and ask before any gated installation or compute.
