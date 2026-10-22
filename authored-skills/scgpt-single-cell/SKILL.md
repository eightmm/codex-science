---
name: scgpt-single-cell
description: "Run pinned scGPT checkpoints for single-cell embeddings, cell-type annotation, reference mapping, perturbation modeling, or fine-tuning. Use when a pretrained single-cell transformer is requested and donor/batch/feature provenance can be preserved."
license: MIT
---

# scGPT Single-Cell Analysis

## Decision contract

Record dataset/sample/donor identifiers, assay, count layer, feature dictionary
and release, labels, perturbation, task, deployment population, and independent
unit. Prespecify split, preprocessing, baseline, metrics, uncertainty and subgroup
checks. State whether analysis is inductive or transductive and what would falsify
the requested interpretation. Treat embeddings, clusters, transferred labels,
integration scores, and perturbation predictions as model-derived outputs, not
measured biology.

## Reference usage

Read [references/scgpt-evidence-calibration.md](references/scgpt-evidence-calibration.md)
before preprocessing, checkpoint selection, label transfer, integration, or
interpreting an embedding. It defines claim classes, source overlap, uncertainty,
controls, sensitivity checks, and the tissue/species applicability boundary.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned scGPT
   revision, downloading checkpoints or reference assets, and using GPU compute.
   Check and follow the checkpoint's license and weight terms; record the pinned
   terms alongside the checkpoint revision.
   Never upload private human data without explicit authorization and governance
   review. Follow `$cx-compute-environment`. Record approvals and unresolved gates.
2. Define the independent biological unit, task, donors, tissues, batches,
   perturbations, count layer, gene identifiers/release, labels, and deployment
   population. Split by donor/sample/experiment before cell-level processing;
   record split IDs and whether any step is transductive.
3. Pin code/checkpoint, token dictionary, gene mapping, normalization/binning,
   max sequence length, feature selection, pooling, fine-tuning configuration,
   seeds, and hardware. Fit learned preprocessing on training data only and
   record every version and setting.
4. Smoke-test a small public example; continue only if the installed checkpoint
   loads and input/output shapes and feature mapping validate. Run into
   `artifacts/<run-id>/scgpt/`; retain AnnData schema, split IDs,
   preprocessing, embeddings/predictions, checkpoint/config, learning curves,
   environment, logs, and excluded cells.
5. Compare PCA/logistic, nearest-reference, and batch-aware baselines. For label
   transfer, set a confidence/rejection rule before evaluation; record donor-level
   metrics, calibration evidence, batch/tissue slices, and rejected labels.
6. Check nuisance predictability and biology conservation, including known marker
   genes and a mixing/conservation metric only for the property it measures.
   Evaluate on held-out donors or batches; record the control and each metric's
   limits, failures, and uncertainty by independent unit.
7. Vary seeds, latent dimension, HVG count, and clustering resolution when used.
   Downgrade a claim when assignments, held-out performance, or biological
   conclusions change materially; retain all variants and the decision rule.
8. Verify source/checkpoint overlap and tissue/species applicability using the
   reference. Record with `$science-provenance`; review with `$science-review`
   before material claims. Report failures, nulls, unavailable evidence, and the
   smallest falsifiable next action.

## Outputs

Return one `scgpt-evidence-v1` record containing input and donor/sample hashes
(`input_hashes`, `unit_hashes`), schema and feature mapping (`input_schema`,
`feature_mapping`), and assumptions (`assumptions`);
claim identifier (`claim_id`), claim class and status (`claim_type`, `status`);
source, checkpoint, code, and reference-use dependencies (`dependencies`);
split IDs, preprocessing, model settings, environment, and seeds (`analysis`);
control and baseline
results (`controls`); metrics with uncertainty and subgroup denominators
(`results`); sensitivity variants (`sensitivity`); applicability domain and
limitations (`applicability`, `limitations`); exclusions, failures, and nulls
(`failures`); rejected alternatives and rationale (`alternatives`); artifact
paths and hashes (`artifacts`); and the smallest falsifiable next action
(`next_action`). Status is `supported`, `contradicted`, `inconclusive`, or
`unavailable`. Record with `$science-provenance`; `$science-review` is mandatory
before material claims. Retain failed quality checks and excluded observations
without silent repair.

## Boundaries

- Cells from one sample are not independent replicates.
- Integration can erase biology; cell-type labels and perturbation predictions
  remain model outputs, not experimental or clinical truth.
- Embedding geometry and visually mixed latent spaces do not establish biological
  similarity, cell identity, causal response, or calibrated confidence.
- scGPT pretraining corpus overlap and tissue/species shift can invalidate an
  apparent held-out evaluation; report known overlap and unknown provenance.
- Never upload private human data without explicit authorization and governance
  review. Follow `$cx-compute-environment` for package, checkpoint, and GPU gates.
