---
name: chai1-structure-prediction
description: "Run pinned Chai-1 inference for proteins, complexes, nucleic acids, ligands, covalent bonds, templates, or restraints. Use when multimolecular structure prediction needs Chai-1-specific inputs and confidence outputs."
license: MIT
---

# Chai-1 Structure Prediction

## Gate

Ask once before installing a pinned `chai_lab` release, downloading weights,
using GPU compute, or contacting public MSA/template servers. Name each remote
host and never upload private sequences or structures without approval. Follow
`$cx-compute-environment`.

## Workflow

1. Define every entity and state: protein/RNA/DNA sequence, ligand SMILES/CCD,
   modifications, stoichiometry, covalent bonds, restraints, and templates.
2. Pin Chai-1 version/commit, weight checksum, input schema, MSA/template mode,
   number of samples, seeds, hardware, precision, and all restraints.
3. Smoke-test `chai-lab fold --help` and an upstream example. Run the validated
   FASTA/context into `artifacts/<run-id>/chai1/`; preserve inputs, MSAs,
   templates, restraint files, structures, scores, logs, and failures.
4. Separate model confidence, interface confidence, geometry checks, and any
   downstream affinity estimate. Compare samples and inspect clashes, ligand
   state, covalent geometry, low-confidence regions, and restraint satisfaction.
5. Record with `$science-provenance`; use `$science-review` before conclusions.

## Boundaries

- Restraint satisfaction is not independent evidence when restraints were input.
- A plausible complex or ligand pose is not proof of binding or affinity.
- Report results from public ColabFold-style MSAs separately from local MSAs.

