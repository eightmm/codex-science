---
name: esmc-protein-modeling
description: "Run released Biohub ESMC protein language models for representations, masked likelihoods, sequence scoring, mutation analysis, or sparse-autoencoder features. Use as the current ESMC alternative to ESM-2 when model scale, revision, and inference boundaries are explicit."
license: MIT
---

# ESMC Protein Modeling

For a concrete dataset, use `$cx-modeling-problem-execution` to continue through
execution and downstream evaluation.

## Gate and workflow

1. Ask once before installing a pinned Biohub `esm`/Transformers revision,
   downloading ESMC/SAE weights, using GPU compute, Hugging Face authentication,
   or sending sequences to Biohub. Never expose tokens or private sequences.
2. Define the downstream task and split before extraction. Pin model/revision,
   tokenizer, layer/SAE, pooling, length/chunking, masks, precision, and device.
3. Smoke-test one sequence alone and in a mixed batch. Require padding/batch
   invariance within tolerance, then write results to
   `artifacts/<run-id>/esmc/` with hashes, embeddings/logits/features, masks,
   configs, environment, logs, and failures.
4. Fit transforms and prediction heads on training data only. Compare ESM-2,
   nearest-homolog, composition/profile, and simple linear baselines; report by
   nearest-train identity and applicability domain.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Likelihood, an embedding, or an SAE interpretation is not measured function.
- Record the pretraining/database cutoff and audit homolog or retrieval leakage.

