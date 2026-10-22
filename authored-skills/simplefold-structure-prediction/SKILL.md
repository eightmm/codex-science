---
name: simplefold-structure-prediction
description: "Run Apple's released SimpleFold flow-matching protein structure models with PyTorch or MLX. Use for single-protein folding, conformer ensembles, or Apple-silicon inference when model-size and model-license constraints are acceptable."
license: MIT
---

# SimpleFold Structure Prediction

Use `$cx-modeling-problem-execution` to take concrete FASTA input through a real run and downstream uncertainty analysis.

## Decision contract

Role: executor, with structure and ensemble analysis of model outputs.

Record the folding question, organism/construct, intended use, claim IDs, permitted inference, and what structural observation would change the conclusion. Choose model size and backend only after checking hardware and the separate released-model license. State whether the deliverable is a single predicted structure or an ensemble analysis. Use the status vocabulary `supported`, `contradicted`, `inconclusive`, and `unavailable`. Confidence metrics describe model outputs; do not interpret them as calibrated probability of correctness.

## Reference usage

- Read [references/structure-evidence.md](references/structure-evidence.md) before reporting confidence, ensemble diversity, accuracy, or generalization claims; it defines claim classes, data-dependence checks, controls, and applicability limits.
- Read the pinned SimpleFold repository's installation, model-card, and license documentation before selecting a backend or weights. Record immutable repository revision and exact weight checksum in the run output; this skill does not replace their current instructions.

## Workflow

1. **Gates (ask before proceeding).** Ask once before cloning a pinned commit, installing its environment, downloading weights, or running compute. Review the separate released-model license and continue only with approval and acceptable terms; select MLX only on supported Apple silicon or PyTorch otherwise. Record approval, license identity, backend choice, or gated status.
2. Validate FASTA alphabet, sequence length, construct, organism, and chain expectations. If input is invalid or length unsupported, stop without truncation; preserve/hash the input and record validation results and the explicit input-length policy.
3. Pin repository commit, model size/checksum, backend, diffusion steps, tau, samples per protein, seeds, device, and precision. If a required setting or actual revision is unavailable, mark execution unavailable; record intended and actual revisions plus environment.
4. Smoke-test the sample notebook or smallest model and validate structure output before the full run. For a valid input and authorized resources, run into `artifacts/<run-id>/simplefold/`; retain FASTA, structures, pLDDT, sampled ensemble, config, environment, logs, timings, and failures. Record validation and execution outcome.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Continue only when output passes structure parsing and required integrity checks; record each retry and its reason.
6. Report conformer diversity and confidence, not only the best sample. Compare legacy ESMFold, ESMFold2, or another justified baseline for decision-critical folding or ensemble claims; document shared data or methods. Retain null or failed outputs, report sensitivity and limits, record with `$science-provenance`, and run `$science-review` before material conclusions.

## Outputs

Return `simplefold-structure-evidence-v1` with: execution/evidence table; claim identifier (`claim_id`) and claim status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized sequence and hash; model and backend revisions; settings and seeds; hardware; output paths and hashes; confidence and ensemble measurements; failures and nulls; uncertainty; applicability limits; alternatives and reasons; and smallest falsifiable next action. Distinguish process exit success from scientific validation.

## Boundaries

Flow-matching samples are model conformers, not a thermodynamic ensemble. Code and model weights have separate terms; this skill grants neither. Do not present confidence as calibrated probability, or infer experimental accuracy for an unseen target. Stop if model/input compatibility or license terms are unresolved; keep the claim inconclusive or unavailable and preserve the failure record.
