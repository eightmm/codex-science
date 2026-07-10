---
name: simplefold-structure-prediction
description: "Run Apple's released SimpleFold flow-matching protein structure models with PyTorch or MLX. Use for single-protein folding, conformer ensembles, or Apple-silicon inference when model-size and model-license constraints are acceptable."
license: MIT
---

# SimpleFold Structure Prediction

Use `$cx-modeling-problem-execution` to take concrete FASTA input through a real
run and downstream uncertainty analysis.

## Gate and workflow

1. Ask once before cloning a pinned commit, installing its environment,
   downloading weights, or running compute. Review the separate released-model
   license; select MLX on supported Apple silicon or PyTorch otherwise.
2. Pin commit, model size/checksum, backend, diffusion steps, tau, samples per
   protein, seeds, device, precision, and input length policy.
3. Smoke-test the sample notebook/smallest model, then run the real FASTA into
   `artifacts/<run-id>/simplefold/`; retain FASTA, structures, pLDDT, sampled
   ensemble, config, environment, logs, timings, and failures.
4. Report conformer diversity and confidence, not only the best sample. Compare
   legacy ESMFold, ESMFold2, or another justified baseline for decision-critical
   folding or ensemble claims.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Flow-matching samples are model conformers, not a thermodynamic ensemble.
- Code and model weights have separate terms; this skill grants neither.

