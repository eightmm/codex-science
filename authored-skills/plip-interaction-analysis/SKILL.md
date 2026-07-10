---
name: plip-interaction-analysis
description: "Profile noncovalent protein-ligand interactions with a pinned PLIP release and compare interaction fingerprints across experimental structures, docking poses, or trajectory representatives. Use after structure preparation or pose generation."
license: MIT
---

# PLIP Interaction Analysis

## Workflow

1. Follow `$cx-compute-environment`; ask once before installing pinned PLIP/Open
   Babel dependencies or processing many structures.
2. Record structure source, assembly/chains, ligand identifier and atom mapping,
   protonation, waters/metals retained, and whether the pose is experimental,
   predicted, docked, or an MD frame.
3. Smoke-test one complex. Run PLIP into `artifacts/<run-id>/plip/`, preserving
   machine-readable output and exact command/version.
4. Report hydrogen bonds, hydrophobic contacts, salt bridges, pi interactions,
   halogen bonds, water bridges, and metal coordination with residue/atom IDs and
   geometry. Compare fingerprints only after consistent preparation.
5. For trajectories, cluster or sample prespecified frames and report interaction
   occupancy with autocorrelation-aware uncertainty; do not treat every frame as
   independent.

## Boundaries

- A detected contact is a geometry-based annotation, not proof of energetic
  importance or binding.
- Protonation, missing hydrogens, alternate locations, and water handling can
  change the fingerprint; state them.
- Do not infer affinity from interaction counts.

