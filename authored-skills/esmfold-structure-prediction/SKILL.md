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

## Reference usage

Read [esmfold-evidence.md](references/esmfold-evidence.md) before interpreting confidence, comparing a prediction with another model or structure, assigning claim status, or deciding whether the construct is in scope. It defines metric limits, evidence dependence, controls, sensitivity checks, and failure criteria.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned `fair-esm`/repository revision, downloading weights, or using GPU compute. Remote ESM Atlas folding transmits the sequence and requires separate approval; prefer local inference. State the resource or data transfer and record the approval decision. Follow `$cx-compute-environment`.
2. Validate sequence alphabet, chain separators, construct, organism, chain arrangement, and length; if mapping is ambiguous or the construct cannot be represented, stop and retain an unavailable/inconclusive result. Preserve and hash the submitted sequence; never silently truncate. Plan chunking only when scientifically defensible and record boundaries, never interpreting a chunk as a full-length model.
3. Pin repository/package revision, `esmfold_v1` checkpoint and weight checksum, recycles, chunk size, batching, seed, device, and precision. Record actual revisions and environment.
4. Smoke-test one short sequence and verify the expected structure and confidence fields before the real input; if the smoke test fails validation, stop and record the failure. Run the real input to `artifacts/<run-id>/esmfold/`; retain FASTA, PDB outputs, logs, timings, parameters, and failed sequences.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and retain cancellation and failure logs. Record status as `supported`, `contradicted`, `inconclusive`, or `unavailable` only under the reference criteria.
6. Analyze pLDDT, chain/interface uncertainty when available, clashes, and missing confidence information. pLDDT supports a model-internal local confidence statement only; it is not experimental accuracy. Do not invent PAE or interface fields absent from the output. Record observed fields and missingness.
7. When a claim depends on structural detail, compare with an appropriate AlphaFold DB or MSA-based method and assess shared evidence dependencies; use a known structure/benchmark and decoy or negative controls where applicable. Vary seeds or stochastic settings when available, and relevant recycles, chunking, precision, or batching; record which conclusions change.
8. **Verify** sequence-to-output mapping, chain identities, residue coverage, geometry, model revision, and saved artifact hashes; failures downgrade claims rather than disappear. Record the completed process separately from whether scientific acceptance criteria were met.
9. Record with `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return `esmfold-prediction-evidence-v1` with these required fields: claim identifier (`claim_id`); status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized sequence and hash (`sequence`, `sequence_hash`); target construct and chain mapping (`construct`, `chain_mapping`); model/checkpoint and environment revisions (`model_revision`, `checkpoint`, `environment`); settings and seed (`settings`, `seed`); outputs and hashes (`artifacts`); observed confidence and geometry fields (`metrics`); missingness and failures (`missingness`, `failures`); uncertainty (`uncertainty`); applicability limits (`applicability_limits`); process completion (`process_completed`); scientific acceptance status (`acceptance_status`); concise interpretation (`interpretation`); and smallest falsifiable next action (`next_action`).

## Boundaries

Single-sequence speed does not imply equal accuracy to MSA/template methods. pLDDT is confidence, not experimental accuracy for a specific unseen target. Do not claim interface validity or generalization from one prediction. Stop if input sequence or chain mapping is ambiguous, or the desired construct cannot be represented; retain the failure and report an unavailable/inconclusive claim.
