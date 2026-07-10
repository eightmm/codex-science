---
name: openfold3-structure-prediction
description: "Run pinned OpenFold3 preview inference for proteins, nucleic acids, noncanonical residues, and small-molecule complexes. Use when an open AlphaFold3-style workflow is wanted and preview-status limitations are acceptable."
license: MIT
---

# OpenFold3 Structure Prediction

## Gate

Ask once before installing a pinned OpenFold3 preview release, running setup,
downloading parameters/databases, contacting an MSA server, or using GPU/remote
compute. Never send private sequences to public services without approval.
Follow `$cx-compute-environment`.

## Workflow

1. Define query JSON entities, sequences, ligand states, modifications,
   stoichiometry, templates, MSAs, and covalent relationships.
2. Pin the preview release/commit, parameter checksum, setup version, database
   snapshots, kernel versions, MSA/template mode, seeds, samples, and hardware.
3. Smoke-test the official example. Run `run_openfold predict` into
   `artifacts/<run-id>/openfold3/`; retain query JSON, feature inputs, structures,
   confidence outputs, environment, exact command, logs, and failures.
4. Check chemistry, atom mapping, clashes, chain/interface confidence, PAE-like
   uncertainty, sample diversity, and template dependence.
5. Record with `$science-provenance`; review claims with `$science-review`.

## Boundaries

- Label the software and results as OpenFold3 preview; do not claim final-model
  parity or full AlphaFold3 modality parity.
- Predicted ligand poses and interfaces do not establish binding or affinity.

