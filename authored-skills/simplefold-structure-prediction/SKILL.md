---
name: simplefold-structure-prediction
description: "Run Apple's released SimpleFold flow-matching protein structure models with PyTorch or MLX. Use for single-protein folding, conformer ensembles, or Apple-silicon inference when model-size and model-license constraints are acceptable."
license: MIT
---

# SimpleFold Structure Prediction

Use `$cx-modeling-problem-execution` to take concrete FASTA input through a real
run and downstream uncertainty analysis.

## Decision contract

Role: executor, with structure and ensemble analysis of model outputs.

Record the folding question, organism/construct, intended use, claim IDs, permitted inference, and what structural observation would change the conclusion. Choose model size and backend only after checking hardware and the separate released-model license. State whether the deliverable is a single predicted structure or an ensemble analysis.

## Workflow

1. Ask once before cloning a pinned commit, installing its environment, downloading weights, or running compute. Review the separate released-model license; select MLX on supported Apple silicon or PyTorch otherwise.
2. Validate FASTA alphabet, length, construct, and chain expectations. Preserve/hash input and state the input-length policy. Record unsupported lengths rather than silently truncating.
3. Pin commit, model size/checksum, backend, diffusion steps, tau, samples per protein, seeds, device, and precision. Record environment and actual revisions.
4. Smoke-test the sample notebook/smallest model and validate structure output. Run the real FASTA into `artifacts/<run-id>/simplefold/`; retain FASTA, structures, pLDDT, sampled ensemble, config, environment, logs, timings, and failures.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Report conformer diversity and confidence, not only the best sample. Compare legacy ESMFold, ESMFold2, or another justified baseline for decision-critical folding or ensemble claims; document shared data or methods. Retain null or failed outputs.
7. Record with `$science-provenance`; run `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized sequence/hash, model and backend revisions, settings/seeds, hardware, output paths/hashes, confidence and ensemble measurements, failures/nulls, uncertainty, and applicability limits. Include alternatives and the smallest falsifiable next action. Distinguish process exit success from scientific validation.

## Boundaries

Flow-matching samples are model conformers, not a thermodynamic ensemble. Code and model weights have separate terms; this skill grants neither. Do not present confidence as calibrated probability, or infer experimental accuracy for an unseen target. Stop if model/input compatibility or license terms are unresolved; keep the claim inconclusive or unavailable and preserve the failure record.
