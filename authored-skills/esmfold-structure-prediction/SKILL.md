---
name: esmfold-structure-prediction
description: "Run the legacy public ESMFold v1 single-sequence structure model reproducibly for proteins or simple multimers. Use for the 2022 ESM-2-based model; use the separate ESMFold2 skill for Biohub's 2026 diffusion/all-atom model."
license: MIT
---

# ESMFold v1 Structure Prediction

This skill covers the legacy public `esmfold_v1` model. Use
`$cx-esmfold2-structure-prediction` for the 2026 Biohub diffusion/all-atom model.
For a concrete input, follow `$cx-modeling-problem-execution` through execution.

## Gate

Ask once before installing a pinned `fair-esm`/repository revision, downloading
weights, or using GPU compute. Prefer local inference; remote ESM Atlas folding
requires separate approval because it transmits the sequence. Follow
`$cx-compute-environment`.

## Workflow

1. Validate sequence alphabet, chain separators, construct, and length. Do not
   silently truncate; plan chunking only when scientifically defensible.
2. Pin repository/package, `esmfold_v1` checkpoint, weight checksum, recycles,
   chunk size, batching, seed, device, and precision.
3. Smoke-test one short sequence, then run into
   `artifacts/<run-id>/esmfold/`. Retain FASTA, PDB outputs, logs, timings,
   parameters, and failed sequences.
4. Report pLDDT, chain/interface uncertainty, clashes, missing confidence
   information, and consistency across settings. Compare against AlphaFold DB or
   an MSA-based method when the claim depends on structural detail.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Single-sequence speed does not imply equal accuracy to MSA/template methods.
- pLDDT is confidence, not experimental accuracy for a specific unseen target.
