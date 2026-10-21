---
name: plip-interaction-analysis
description: "Profile noncovalent protein-ligand interactions with a pinned PLIP release and compare interaction fingerprints across experimental structures, docking poses, or trajectory representatives. Use after structure preparation or pose generation."
license: MIT
---

# PLIP Interaction Analysis

## Decision contract

Define the interaction question (description, comparison, or trajectory occupancy), structure/pose set, ligand and receptor states, evidence cutoff, and what observation would change the interpretation. Distinguish geometry annotation from energetic or binding claims. Assign claim IDs for comparisons and prespecify the fingerprint fields and any sampling rule.

## Workflow

1. Follow `$cx-compute-environment`; ask once before installing pinned PLIP/Open Babel dependencies or processing many structures.
2. Record structure source, assembly/chains, ligand identifier and atom mapping, protonation, waters/metals retained, and whether the pose is experimental, predicted, docked, or an MD frame. Validate coordinates, chain selection, and ligand identity; preserve raw inputs.
3. Smoke-test one complex. Run PLIP into `artifacts/<run-id>/plip/`, preserving machine-readable output and exact command/version. Retain failures and explain exclusions.
4. Report hydrogen bonds, hydrophobic contacts, salt bridges, pi interactions, halogen bonds, water bridges, and metal coordination with residue/atom IDs and geometry. Compare fingerprints only after consistent preparation.
5. For trajectories, cluster or sample prespecified frames and report interaction occupancy with autocorrelation-aware uncertainty; do not treat every frame as independent. Include alternative protonation/water handling when conclusions depend on them.
6. Record scripts/configuration, output hashes, dependencies, and limitations with `$science-provenance`; obtain `$science-review` before material interpretation.

## Outputs

Return normalized structure identities and preparation assumptions; a machine-readable interaction table with type, atoms/residues, geometry, frame/replica, and status; claim IDs marked supported, contradicted, inconclusive, or unavailable; excluded structures and reasons, uncertainty, limitations, and smallest falsifiable next action. Keep raw and derived artifacts distinct.

## Boundaries

A detected contact is a geometry-based annotation, not proof of energetic importance or binding. Protonation, missing hydrogens, alternate locations, and water handling can change the fingerprint; state them. Do not infer affinity from interaction counts. Incompatible preparation, missing atoms, or inadequate trajectory sampling requires an inconclusive result.
