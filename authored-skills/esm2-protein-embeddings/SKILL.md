---
name: esm2-protein-embeddings
description: "Extract reproducible ESM-2 protein embeddings, residue representations, likelihoods, or zero-shot mutation scores. Use when a frozen protein language model is needed as a feature extractor or baseline."
license: MIT
---

# ESM-2 Protein Embeddings

## Decision contract

Record sequence/construct identifiers and hashes, prediction unit, intended
downstream estimand, permitted inference, split unit, and information available
at inference. Prespecify model/checkpoint, extraction settings, baseline metrics,
acceptance tolerances, and leakage checks. Treat model likelihood and embedding
features as model outputs, not validated biological measurements.

## Gate

Ask once before installing a pinned ESM/Transformers revision, downloading model
weights, or using GPU compute. Keep sequences local unless remote inference is
explicitly approved. Follow `$cx-compute-environment` and record the applicable
code and checkpoint license/weight terms from their release metadata; do not
assume the skill's MIT metadata grants rights to every checkpoint or use.

## Reference usage

Read [references/esm2-score-interpretation.md](references/esm2-score-interpretation.md)
before computing or interpreting a likelihood, mutation score, embedding
similarity, supervised comparison, or claim of biological relevance.

## Workflow

1. **step-1 — Pass the execution gate:** ask once before installing pinned ESM/Transformers, downloading weights, or using GPU; keep sequences local absent remote approval, follow `$cx-compute-environment`, and record license/weight terms, code revision, and checkpoint provenance.
2. **step-2 — Freeze the question:** define prediction unit, exact sequence or construct, task, estimand, inference-time information, and intended claim; record hashes, split unit, and permitted inference.
3. **step-3 — Pin the method:** select checkpoint/revision, tokenizer, representation layer, maximum length, truncation or chunk overlap, pooling, special-token handling, batch size, device, and precision; record each setting and rationale.
4. **step-4 — Select claim semantics:** choose embedding, pseudo-log-likelihood, masked-marginal substitution score, or downstream prediction; use the reference criteria to assign claim class, then record score definition, direction, units, and claim ID/status.
5. **step-5 — Check extraction integrity:** smoke-test one sequence alone and in a mixed batch; require agreed numerical batch invariance and valid dimensions/masks, recording the comparison and any failure before extraction.
6. **step-6 — Evaluate without leakage:** cluster homologs before splitting, fit transforms/heads on training data only, and compare nearest-homolog, conservation/profile, composition, and simple linear baselines; record group-level metrics and nearest-train identity strata.
7. **step-7 — Challenge the result:** run matched positive/negative and sequence sanity controls, then vary model size/checkpoint, context handling, layer/pooling, and scoring method; record control outcomes, sensitivity ranges, and fragile conclusions.
8. **step-8 — Verify and hand off:** run the applicable schema/reference checks, preserve failures and artifacts, record with `$science-provenance`, and use `$science-review` before material downstream claims; report supported, contradicted, inconclusive, or unavailable status and the smallest falsifiable next analysis.

## Outputs

Use schema `esm2-evidence-reconciliation-v1`. Required fields: claim identifier
(`claim_id`); claim status (`status`: supported, contradicted, inconclusive, or
unavailable); claim class (`claim_class`); prediction unit and estimand
(`prediction_unit`, `estimand`); sequence and split provenance (`sequence_hashes`,
`split_ids`, `homology_policy`); model and method identity (`checkpoint`,
`checkpoint_revision`, `tokenizer`, `scoring_method`, `layer`, `preprocessing`);
run environment (`code_revision`, `environment`, `seed`, `device`, `precision`);
outputs and extraction checks (`scores_or_embeddings`, `dimensions`, `masks`,
`batch_invariance`); controls and sensitivity (`controls`, `sensitivity`);
uncertainty and baselines (`uncertainty`, `baseline_results`); applicability,
limitations and failures (`applicability_domain`, `limitations`, `failures`);
artifact locations and hashes (`artifact_paths`, `artifact_hashes`); provenance
and review references (`provenance_ref`, `review_ref`). Save a manifest plus a
per-sequence extraction/evaluation table, logs, exclusions, and artifacts under
`artifacts/<run-id>/esm2/`. `$science-review` is mandatory before material
downstream claims. Valid tensor shapes and batch invariance establish extraction
integrity only.

## Boundaries

- Pin the pretraining/model release and acknowledge database-cutoff leakage.
- Embedding similarity or mutation likelihood is not functional validation.
- A score is not a probability of pathogenicity, fitness, expression, or clinical effect.
- In-silico benchmarks support only the evaluated constructs, splits, labels, and task; retain the smallest falsifiable next analysis.
- Assign each material claim an ID and status: supported, contradicted, inconclusive, or unavailable.

