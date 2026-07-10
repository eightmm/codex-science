---
name: alphafold2-structure-prediction
description: "Run reproducible AlphaFold2 monomer or multimer inference with pinned code, parameters, sequence databases, template cutoff, and seeds. Use when a local AlphaFold2 installation or approved container/database setup is available; use AlphaFold DB lookup instead for an existing canonical model."
license: MIT
---

# AlphaFold2 Structure Prediction

## Gate

Ask once before installing or pulling a pinned container, downloading model
parameters or sequence databases, querying remote MSA services, and using GPU
compute. State that a full official setup can require hundreds of GB of downloads
and several TB of disk. Prefer an existing validated installation. Never upload
private sequences without explicit approval. Follow `$cx-compute-environment`.

## Workflow

1. Resolve exact sequences, constructs, oligomeric state, chain stoichiometry,
   modifications, and template cutoff. Use `$cx-alphafold-structure-analysis`
   instead when AlphaFold DB already contains the desired canonical monomer.
2. Pin the AlphaFold repository/container digest, model parameters, database
   snapshots, model preset, template date, MSA mode, recycle count, relaxation,
   seeds, GPU, and numerical precision.
3. Smoke-test the pinned environment on a tiny known input. Run monomer or
   multimer inference into `artifacts/<run-id>/alphafold2/`; retain FASTA, MSAs,
   template hits, ranked structures, PAE, confidence JSON, timings, and logs.
4. Report per-residue pLDDT, PAE, pTM/ipTM where available, chain/interface
   uncertainty, disordered regions, template dependence, and model diversity.
5. Record the complete run with `$science-provenance` and review claims with
   `$science-review`.

## Boundaries

- Prediction confidence is not experimental validation or proof of interaction.
- Audit template/database overlap for benchmarks and keep apo/holo assumptions
  explicit. Do not compare runs with different database snapshots as identical.

