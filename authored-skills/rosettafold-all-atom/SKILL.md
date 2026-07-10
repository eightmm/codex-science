---
name: rosettafold-all-atom
description: "Run RoseTTAFold All-Atom for proteins, nucleic acids, small molecules, metals, covalent modifications, and higher-order assemblies. Use when its Hydra input model and confidence metrics fit the problem and licensed dependencies are available."
license: MIT
---

# RoseTTAFold All-Atom

Use `$cx-modeling-problem-execution` for concrete structures and continue through
input preparation, inference, analysis, and review.

## Gate and workflow

1. Ask once before cloning a pinned commit, creating the environment/container,
   downloading large sequence/template databases and weights, installing
   separately licensed SignalP, and running GPU compute. Verify each dependency's terms.
2. Validate protein/nucleic-acid FASTA, ligand SDF/SMILES, metals, covalent bond
   atom indices/chirality, chain IDs, and Hydra config. Pin checkpoints,
   database snapshots, cycles, seeds, hardware, and container digest.
3. Smoke-test an official example. Run into `artifacts/<run-id>/rfaa/`; retain
   inputs/config, MSAs/templates, PDB, pLDDT/PAE/PDE metrics, logs, mappings,
   environment, and failures.
4. Inspect covalent/metal geometry, chirality, ligand state, interfaces, clashes,
   and confidence; do not reduce quality to one mean metric.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- SignalP and other dependencies may have separate licenses and cannot be
  silently downloaded or redistributed.
- Predicted docks and `pae_inter` are prioritization signals, not affinity.

