---
name: molecular-input-preparation
description: "Prepare receptors and small molecules for docking or simulation with explicit stereochemistry, protonation, tautomer, charge, conformer, cofactor, water, and pocket provenance. Use before AutoDock Vina, GNINA, DiffDock, OpenMM, GROMACS, or any protein-ligand modeling run."
license: MIT
---

# Molecular Input Preparation

## Decision contract

Define target and biological state, ligand identity/microstate, intended downstream method, permitted inference, evidence cutoff, and assumptions that could change the result. Classify the output as a prepared-input record, not evidence that a downstream model is scientifically valid. Ambiguous required stereochemistry, covalent chemistry, metal coordination, or biological assembly that changes the modeled system requires a stop or explicit user choice.

## Reference usage

Read [references/molecular-state-and-provenance.md](references/molecular-state-and-provenance.md) before changing protonation, tautomers, stereochemistry, receptor atoms/residues, waters/cofactors/metals, chain/residue identifiers, charges, or file formats. It defines state semantics, atom mapping and hash records, independent preparation controls, sensitivity, and downstream evidence limits.

## Workflow

1. **Gate:** Follow `$cx-compute-environment`; ask once before installing pinned packages, downloading structures, or running compute. Never upload a private structure. Record approval or stop decision, source terms, and access mode before proceeding.
2. Define the downstream task and state contract; proceed only when target biological state, ligand identity, intended method, permitted inference, evidence cutoff, and decision-changing assumptions are explicit. Record the contract before selecting scores or outcomes.
3. Inventory source records; proceed only when source IDs/files, release, assembly, chain mapping, bound ligands, metals, cofactors, covalent bonds, alternate locations, missing atoms, and unresolved residues are recorded or marked unresolved. Preserve raw inputs; do not silently delete waters or heteroatoms.
4. Enumerate plausible ligand states; preserve the user's stated stereochemistry and microstate, enumerate only chemically plausible stereoisomers/tautomers/protonation states, and reject invalid valence or undefined required stereocenters. Record state IDs, atom mapping, and the reason for each included or rejected state.
5. Prepare receptor state for the stated pH; choose protonation and histidine states with an explicitly selected tool, record method/version and each manual change, and preserve unresolved states. Generate deterministic RDKit conformers with seed and force field; assign charges with method/version. Record the transform ledger and resulting atom identities.
6. Define the pocket from a reference ligand or explicit residues/coordinates; proceed only if its source is independent of any held-out bound pose in a benchmark. Record pocket definition, coordinates/residue IDs, and split provenance.
7. Export using RDKit for structure checks/conformers and Meeko for Vina PDBQT where applicable; otherwise use declared formats/tools. Prefer SDF/mol for ligands and PDB/mmCIF for receptors; use PDBQT only when required. Validate atom counts, elements, charges, bonds, stereochemistry, coordinates, chain/residue numbering, and atom mapping after conversion. Record thresholds, failures, and hashes; retain every failed state.
8. Prepare a redundant representative state with a different tool when available and compare chemistry and mapped atoms; vary plausible protonation/pH choices, tautomers, retained waters/cofactors/metals, and relevant validation thresholds. Downgrade if material state identity or downstream inputs change unresolved. Save manifest and checksums under `artifacts/<run-id>/inputs/`, record assumptions with `$science-provenance`, and require `$science-review` before material claims based on prepared structures.

## Outputs

Return `molecular-preparation-evidence-v1` with required fields: claim identifier (`claim_id`); claim class (`claim_class`: prepared-input identity or downstream handoff); source identity/release and structure provenance (`source_id`, `release`, `structure_provenance`); normalized receptor and ligand state table (`receptor_state`, `ligand_states`); pH, protonation, tautomer, stereochemistry, charge, water/cofactor/metal, and missing-atom decisions (`state_assumptions`); tool/version/seed (`tools`, `versions`, `seeds`); transformation ledger (`transformations`); atom mapping (`atom_mapping`); raw and prepared input hashes (`raw_hashes`, `prepared_hashes`); validation results and thresholds (`validation`, `thresholds`); redundant preparation and sensitivity outcomes (`controls`, `sensitivity`); exclusions and failures (`exclusions`, `failures`); uncertainty and limitations (`uncertainty`, `limitations`); downstream handoff (`downstream_handoff`); claim status (`status`: supported, contradicted, inconclusive, or unavailable); and smallest falsifiable next action (`next_action`).

## Boundaries

A SMILES string is not a unique modeled microstate. Protein cleanup can change the scientific question; surface every ambiguity. Never infer bond order around metals or covalent ligands without evidence. Do not silently repair chemistry, select a favorable state after seeing docking outcomes, or treat successful conversion as scientific validation.

## Source basis

Chemical identity and stereochemistry should be preserved across explicitly recorded transformations; structural metadata follow wwPDB/PDBx/mmCIF conventions. RDKit and Meeko are implementation tools, not evidence that a chosen microstate, charge model, or prepared receptor is biologically correct.
