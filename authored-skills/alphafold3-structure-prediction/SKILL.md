---
name: alphafold3-structure-prediction
description: "Run the official AlphaFold3 inference pipeline for approved theoretical modeling of proteins, nucleic acids, ligands, modifications, and covalent complexes. Use only when the user has legitimately obtained model parameters and accepts the source, weight, output, and non-commercial terms."
license: MIT
---

# AlphaFold3 Structure Prediction

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

For a concrete approved input, follow `$cx-modeling-problem-execution` through execution and review. State the structural question, intended use, entity and chemical state, claim IDs, permitted inference, and the observation that would change the conclusion. Record whether the result is exploratory; do not frame a predicted complex as binding evidence.

## Workflow

1. Verify the intended use and that parameters came directly from Google. AlphaFold3 code, model parameters, and outputs have separate restrictive terms. Before inspecting credentialed parameter paths, pulling a pinned container, downloading databases, or using GPU compute, ask once. Never copy, redistribute, or log weights or credentials; never use for clinical purposes.
2. Validate the AlphaFold3 JSON dialect/version, entity IDs, sequences, ligand CCD/SMILES, modifications, bonds, custom CCD, MSAs/templates, and model seeds. Preserve the exact input and hash; stop rather than silently dropping unsupported entities or chemistry.
3. Pin code release/container digest, database snapshots, parameter provenance, template cutoff, pipeline/inference flags, seeds, hardware, and precision. Exclude restricted weights and credentials from provenance artifacts.
4. Smoke-test the official example and validate the installed release's expected output structure. Run the real JSON into `artifacts/<run-id>/alphafold3/`; record input hashes and metadata. Preserve outputs, confidence, logs, timings, and failures, including nonzero exits and invalid output.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Inspect ranking/confidence, interfaces, ligand state, covalent geometry, clashes, template/MSA dependence, and sample diversity. Compare an open model when the claim requires independent evidence, while documenting shared data or methods.
7. Record compliant provenance with `$science-provenance`; run `$science-review` before material conclusions.

## Outputs

Return a summary and machine-readable execution/evidence table: claim ID and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized entities, input hash, code/database/model provenance that may be disclosed, settings, output paths and hashes, observed metrics, failures/nulls, uncertainty, applicability, and limitations. State explicitly when a restricted asset cannot be recorded. Include a smallest falsifiable next action and distinguish process completion from scientific validation.

## Boundaries

The repository skill license does not grant rights to AlphaFold3 assets. Predictions are theoretical models, not binding, efficacy, safety, or clinical evidence. Confidence does not establish chemical correctness. Stop if terms, parameter provenance, approval, or input representation is unresolved; do not imply validation from successful execution alone.
