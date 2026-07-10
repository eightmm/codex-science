---
name: esm2-protein-embeddings
description: "Extract reproducible ESM-2 protein embeddings, residue representations, likelihoods, or zero-shot mutation scores. Use when a frozen protein language model is needed as a feature extractor or baseline."
license: MIT
---

# ESM-2 Protein Embeddings

## Gate

Ask once before installing a pinned ESM/Transformers revision, downloading model
weights, or using GPU compute. Keep sequences local unless remote inference is
explicitly approved. Follow `$cx-compute-environment`.

## Workflow

1. Define the prediction unit, exact sequence/construct, downstream task, and
   inference-time information. Deduplicate and cluster sequences before splitting.
2. Pin model/checkpoint revision, tokenizer, representation layer, max length,
   truncation/chunk overlap, pooling, special-token handling, batch size, device,
   precision, and code revision.
3. Smoke-test one sequence alone and in a mixed batch; require invariant output
   within numerical tolerance. Extract into `artifacts/<run-id>/esm2/` with
   sequence hashes, embeddings/scores, dimensions, masks, logs, and failures.
4. For supervised work, fit all transforms and heads on training data only.
   Compare nearest-homolog, composition, k-mer/profile, and simple linear
   baselines; report performance versus nearest-train identity.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Pin the pretraining/model release and acknowledge database-cutoff leakage.
- Embedding similarity or mutation likelihood is not functional validation.

