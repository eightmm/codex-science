---
name: esmfold-structure-prediction
description: "Run the legacy public ESMFold v1 single-sequence structure model reproducibly for proteins or simple multimers. Use for the 2022 ESM-2-based model; use the separate ESMFold2 skill for Biohub's 2026 diffusion/all-atom model."
license: MIT
---

# ESMFold v1 Structure Prediction

This skill covers the legacy public `esmfold_v1` model. Use
`$cx-esmfold2-structure-prediction` for the 2026 Biohub diffusion/all-atom model.
For a concrete input, follow `$cx-modeling-problem-execution` through execution.

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

State the structure question, intended use, claim IDs, target construct/organism, chain arrangement, and permitted inference. Record the expected structural detail and what result would alter the conclusion. Keep the model scope explicit: this is the legacy public `esmfold_v1`, not ESMFold2.

## Workflow

1. Ask once before installing a pinned `fair-esm`/repository revision, downloading weights, or using GPU compute. Prefer local inference; remote ESM Atlas folding requires separate approval because it transmits the sequence. Follow `$cx-compute-environment`.
2. Validate sequence alphabet, chain separators, construct, and length. Preserve and hash the submitted sequence. Do not silently truncate; plan chunking only when scientifically defensible, document boundaries, and do not interpret a chunked output as a full-length model.
3. Pin repository/package revision, `esmfold_v1` checkpoint, weight checksum, recycles, chunk size, batching, seed, device, and precision. Record environment details and actual revisions.
4. Smoke-test one short sequence and validate the expected structure and confidence fields. Run the real input into `artifacts/<run-id>/esmfold/`. Retain FASTA, PDB outputs, logs, timings, parameters, and failed sequences. Keep nonzero exits and invalid output as failures, not missing runs.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Report pLDDT, chain/interface uncertainty, clashes, missing confidence information, and consistency across settings. Compare against AlphaFold DB or an MSA-based method when the claim depends on structural detail, while noting shared evidence dependencies.
7. Record with `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized sequence and hash, model/checkpoint and environment revisions, settings, outputs and hashes, observed confidence/geometry, missingness and failures, uncertainty, and applicability limits. Include a concise interpretation and smallest falsifiable next action. State separately whether the process completed and whether the scientific acceptance criteria were met.

## Boundaries

Single-sequence speed does not imply equal accuracy to MSA/template methods. pLDDT is confidence, not experimental accuracy for a specific unseen target. Do not claim interface validity or generalization from one prediction. Stop if input sequence or chain mapping is ambiguous, or the desired construct cannot be represented; retain the failure and report an unavailable/inconclusive claim.
