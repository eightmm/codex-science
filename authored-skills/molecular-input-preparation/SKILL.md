---
name: molecular-input-preparation
description: "Prepare receptors and small molecules for docking or simulation with explicit stereochemistry, protonation, tautomer, charge, conformer, cofactor, water, and pocket provenance. Use before AutoDock Vina, GNINA, DiffDock, OpenMM, GROMACS, or any protein-ligand modeling run."
license: MIT
---

# Molecular Input Preparation

## Decision contract

Define the target, biological state, ligand identity/microstate, intended downstream method, and which structural assumptions could change the result. Record the permitted inference and evidence cutoff. Ambiguous required stereochemistry, covalent chemistry, metal coordination, or biological assembly that changes the modeled system requires a stop or explicit user choice.

## Workflow

1. Prepare states before choosing a score. Use RDKit for structure checks and conformers, Meeko for Vina PDBQT, and an explicitly selected protonation/charge tool when needed.
2. Follow `$cx-compute-environment`. Ask once before installing pinned packages, downloading structures, or running compute. Never upload a private structure.
3. Record source IDs/files, biological assembly, chain mapping, bound ligands, metals, cofactors, covalent bonds, alternate locations, missing atoms, and unresolved residues. Do not silently delete waters or heteroatoms.
4. Enumerate ligand stereoisomers, tautomers, and protonation states only when chemically plausible. Preserve the user's stated state and label every generated state. Reject invalid valence and undefined required stereocenters.
5. Choose receptor protonation and histidine states for the target pH. Record method/version and every manual change. Generate deterministic 3D conformers with a recorded seed; minimize and report the force field. Assign formal/partial charges with method and version.
6. Define the pocket from a reference ligand or explicit residues/coordinates. Do not derive a benchmark pocket from the held-out bound pose.
7. Export losslessly where possible: SDF/mol for ligands, PDB/mmCIF for receptor, and PDBQT only for tools requiring it. Validate atom counts, elements, charges, bonds, stereochemistry, and coordinates after conversion. Preserve raw inputs and every failed state.
8. Save a state manifest and checksums under `artifacts/<run-id>/inputs/`; record transformations and assumptions with `$science-provenance`. Require `$science-review` before material claims based on prepared structures.

## Outputs

Return source identity, normalized receptor and ligand-state table, tool/version/seed, transformation ledger, atom mapping and validation results, exclusions/failures, uncertainty and limitations, and downstream handoff. Give material claim IDs supported/contradicted/inconclusive/unavailable status and the smallest falsifiable next action.

## Boundaries

A SMILES string is not a unique modeled microstate. Protein cleanup can change the scientific question; surface every ambiguity. Never infer bond order around metals or covalent ligands without evidence. Do not silently repair chemistry, select a favorable state after seeing docking outcomes, or treat successful conversion as scientific validation.
