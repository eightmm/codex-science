---
name: esmc-protein-modeling
description: "Run released Biohub ESMC protein language models for representations, masked likelihoods, sequence scoring, mutation analysis, or sparse-autoencoder features. Use as the current ESMC alternative to ESM-2 when model scale, revision, and inference boundaries are explicit."
license: MIT
---

# ESMC Protein Modeling

For a concrete dataset, use `$cx-modeling-problem-execution` to continue through
execution and downstream evaluation.

## Decision contract

Record sequence/construct identifiers and hashes, downstream task and estimand,
independent split unit, permitted inference, model family/checkpoint revision,
and whether sequence transfer or hosted inference is authorized. Prespecify
extraction settings, baselines, acceptance tolerances, and leakage checks. Keep
model scale or likelihood separate from biological validity.

## Workflow

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

## Outputs

Save normalized sequence IDs/hashes, split IDs, model and checkpoint revision,
tokenizer/layer/SAE and preprocessing, environment/device/precision, outputs and
dimensions, masks, logs, exclusions/failures, and artifact paths/hashes. Return
the candidate/evaluation table, uncertainty, baseline and applicability results,
limitations, and smallest falsifiable next analysis. Record with
`$science-provenance`; `$science-review` is mandatory before material claims.
Output integrity and batch invariance do not validate function. Assign each
material claim an ID and status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- Likelihood, an embedding, or an SAE interpretation is not measured function.
- Record the pretraining/database cutoff and audit homolog or retrieval leakage.

