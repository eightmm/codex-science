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

## Reference usage

Read [references/esmc-evidence-contract.md](references/esmc-evidence-contract.md)
before scoring substitutions, interpreting embeddings or sparse-autoencoder
(SAE) features, evaluating a benchmark, or making a function-related claim.

## Workflow

1. **step-1 — Pass the execution gate:** ask once before installing pinned Biohub `esm`/Transformers, downloading ESMC/SAE weights, using GPU, Hugging Face authentication, or sending sequences to Biohub; keep tokens and private sequences secret and record authorization and release license/weight terms.
2. **step-2 — Freeze the question:** define task, estimand, prediction unit, permitted inference, split unit, sequence transfer, and any hosted inference; record sequence hashes and claim scope.
3. **step-3 — Pin the method:** record model scale/family, checkpoint revision, tokenizer, layer or SAE, pooling, length/chunking, masks, precision, device, and all preprocessing.
4. **step-4 — Select claim semantics:** distinguish representation, pseudo-log-likelihood, masked-marginal mutation effect, SAE activation, and supervised task output; apply the reference criteria and record score direction, units, and claim ID/status.
5. **step-5 — Check extraction integrity:** smoke-test a sequence alone and in a mixed batch; require padding/batch invariance within declared tolerance, then record outputs, dimensions, masks, and failures under `artifacts/<run-id>/esmc/`.
6. **step-6 — Evaluate without leakage:** cluster homologs and related assay records before splitting; fit transforms and heads on training data only; compare ESM-2, nearest-homolog, conservation/profile, composition, and simple linear baselines; report nearest-train identity strata.
7. **step-7 — Challenge the result:** test matched positive/negative variants and sequence sanity controls, vary scale/checkpoint, context/chunking, layer/pooling, and scoring rule, and inspect SAE feature stability; record uncertainty and fragile conclusions.
8. **step-8 — Verify and hand off:** verify schema and reference requirements, retain exclusions/failures and artifacts, record with `$science-provenance`, and use `$science-review` before material claims; report supported, contradicted, inconclusive, or unavailable status.

## Outputs

Use schema `esmc-evidence-reconciliation-v1`. Required fields: claim identifier
(`claim_id`); claim status (`status`: supported, contradicted, inconclusive, or
unavailable); claim class (`claim_class`); prediction unit and estimand
(`prediction_unit`, `estimand`); sequence and split provenance (`sequence_hashes`,
`split_ids`, `homology_policy`, `assay_grouping`); authorization and release terms
(`transfer_authorization`, `hosted_authorization`, `license_terms`); model and
method (`model_family`, `model_scale`, `checkpoint_revision`, `tokenizer`,
`scoring_method`, `layer_or_sae`, `preprocessing`); environment (`code_revision`,
`environment`, `seed`, `device`, `precision`); outputs/integrity (`scores_features`,
`dimensions`, `masks`, `batch_invariance`); controls and sensitivity (`controls`,
`sensitivity`, `sae_stability`); uncertainty and baseline results (`uncertainty`,
`baseline_results`); applicability/failures (`applicability_domain`, `limitations`,
`failures`); artifact locations/hashes (`artifact_paths`, `artifact_hashes`);
provenance and review references (`provenance_ref`, `review_ref`). Return a
candidate/evaluation table, exclusions, logs, and smallest falsifiable next
analysis. `$science-review` is mandatory before material claims. Output integrity
and batch invariance do not validate function.

## Boundaries

- Likelihood, an embedding, or an SAE interpretation is not measured function.
- A model score is not a calibrated probability of pathogenicity, fitness, expression, or clinical effect.
- Record the pretraining/database cutoff; audit homolog, benchmark, and propagated-record leakage.
- License metadata for the skill does not replace the license and weight terms attached to the exact code, checkpoint, or SAE release.
- Assign each material claim an ID and status: supported, contradicted, inconclusive, or unavailable.

