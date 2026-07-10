---
name: alphafold3-structure-prediction
description: "Run the official AlphaFold3 inference pipeline for approved theoretical modeling of proteins, nucleic acids, ligands, modifications, and covalent complexes. Use only when the user has legitimately obtained model parameters and accepts the source, weight, output, and non-commercial terms."
license: MIT
---

# AlphaFold3 Structure Prediction

For a concrete approved input, follow `$cx-modeling-problem-execution` through
execution and review.

## License and gate

AlphaFold3 code, model parameters, and outputs have separate restrictive terms.
Verify the intended use and that parameters came directly from Google. Ask once
before inspecting credentialed parameter paths, pulling a pinned container,
downloading databases, or using GPU compute. Never copy, redistribute, or log
weights/credentials; never use for clinical purposes.

## Workflow

1. Validate AlphaFold3 JSON dialect/version, entity IDs, sequences, ligand
   CCD/SMILES, modifications, bonds, custom CCD, MSAs/templates, and model seeds.
2. Pin code release/container digest, database snapshots, parameter provenance,
   template cutoff, pipeline/inference flags, seeds, hardware, and precision.
3. Smoke-test the official example. Run the real JSON into
   `artifacts/<run-id>/alphafold3/`; record input hashes and metadata but exclude
   restricted weights. Preserve outputs, confidence, logs, timings, and failures.
4. Inspect ranking/confidence, interfaces, ligand state, covalent geometry,
   clashes, template/MSA dependence, and sample diversity. Compare an open model
   when the claim requires independent evidence.
5. Record compliant provenance with `$science-provenance`; run `$science-review`.

## Boundaries

- The repository skill license does not grant rights to AlphaFold3 assets.
- Predictions are theoretical models, not binding, efficacy, safety, or clinical evidence.

