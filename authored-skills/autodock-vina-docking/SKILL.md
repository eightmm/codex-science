---
name: autodock-vina-docking
description: "Run reproducible local protein-ligand docking with AutoDock Vina and Meeko. Use for pose generation, redocking, or small virtual screens when a receptor and a justified binding pocket are available; do not use a Vina score as experimental affinity."
license: MIT
---

# AutoDock Vina Docking

## Gate and preflight

Follow `$cx-compute-environment` and ask once before installing pinned Vina,
Meeko, or preparation dependencies and before compute. Require
`$cx-molecular-input-preparation` outputs and an explicit pocket definition.

## Workflow

1. Record Vina/Meeko versions, receptor state, ligand microstates, box center and
   size in Å, exhaustiveness, modes, energy range, CPU count, and seed.
2. Smoke-test one ligand. Confirm the search box encloses the intended pocket and
   each ligand can rotate without clipping.
3. Run a positive-control redock before screening. Keep raw PDBQT, log, config,
   and converted SDF poses under `artifacts/<run-id>/vina/`.
4. For a screen, process each ligand state independently and preserve failures;
   never silently keep only successful molecules.
5. Rank poses and compounds separately. Report pose diversity and interactions,
   then apply `$cx-docking-validation`.

## Interpretation

- Vina energy is a model score, not a measured binding free energy or IC50/Kd.
- Pose success requires a prespecified criterion, commonly top-k symmetry-aware
  heavy-atom RMSD to a reference pose when that reference is valid.
- Use cold-target/ligand controls and decoys for comparative screening claims.
- Record apo/holo and assembly/template provenance; do not leak a held-out bound
  pose into pocket construction or ligand initialization.

