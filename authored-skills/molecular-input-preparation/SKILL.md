---
name: molecular-input-preparation
description: "Prepare receptors and small molecules for docking or simulation with explicit stereochemistry, protonation, tautomer, charge, conformer, cofactor, water, and pocket provenance. Use before AutoDock Vina, GNINA, DiffDock, OpenMM, GROMACS, or any protein-ligand modeling run."
license: MIT
---

# Molecular Input Preparation

Prepare states before choosing a score. Use RDKit for structure checks and
conformers, Meeko for Vina PDBQT, and an explicitly selected protonation/charge
tool when needed.

## Gate

Follow `$cx-compute-environment`. Ask once before installing pinned packages,
downloading structures, or running compute. Never upload a private structure.

## Workflow

1. Record source IDs/files, biological assembly, chain mapping, bound ligands,
   metals, cofactors, covalent bonds, alternate locations, missing atoms, and
   unresolved residues. Do not silently delete waters or heteroatoms.
2. Enumerate ligand stereoisomers, tautomers, and protonation states only when
   chemically plausible. Preserve the user's stated state and label every
   generated state. Reject invalid valence and undefined required stereocenters.
3. Choose receptor protonation and histidine states for the target pH. Record
   the method/version and every manual change.
4. Generate deterministic 3D conformers with a recorded seed; minimize and
   report the force field. Assign formal/partial charges with method and version.
5. Define the pocket from a reference ligand or explicit residues/coordinates.
   Do not derive a benchmark pocket from the held-out bound pose.
6. Export losslessly where possible: SDF/mol for ligands, PDB/mmCIF for receptor,
   and PDBQT only for tools requiring it. Validate atom counts, elements,
   charges, bonds, stereochemistry, and coordinates after conversion.
7. Save a state manifest and checksums under `artifacts/<run-id>/inputs/`.

## Boundaries

- A SMILES string is not a unique modeled microstate.
- Protein cleanup can change the scientific question; surface every ambiguity.
- Never infer bond order around metals or covalent ligands without evidence.

