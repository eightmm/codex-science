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
the requested interpretation.

## Gate

Ask once before installing a pinned scGPT revision, downloading checkpoints or
reference assets, and using GPU compute. Never upload private human data without
explicit authorization and governance review. Follow `$cx-compute-environment`.

## Workflow

1. Define the independent biological unit, task, donors, tissues, batches,
   perturbations, count layer, gene identifiers/release, labels, and deployment
   population. Split by donor/sample/experiment before cell-level processing.
2. Pin code/checkpoint/token dictionary, gene mapping, normalization/binning,
   max sequence length, feature selection, pooling, fine-tuning configuration,
   seeds, and hardware. Fit learned preprocessing on training data only.
3. Smoke-test a small public example. Run into `artifacts/<run-id>/scgpt/`;
   retain AnnData schema, split IDs, preprocessing, embeddings/predictions,
   checkpoint/config, learning curves, environment, logs, and excluded cells.
4. Compare PCA/logistic, nearest-reference, and batch-aware baselines. Report
   donor-level uncertainty, batch/tissue slices, calibration, OOD detection, and
   nuisance predictability from embeddings.
5. Record with `$science-provenance`; review with `$science-review`.

## Outputs

Save input and sample/donor hashes, schema and feature mapping, split IDs,
preprocessing/model/checkpoint/token dictionary, environment/seeds, metrics and
uncertainty by independent unit, exclusions/failures, and artifact paths/hashes.
Return claim IDs with supported, contradicted, inconclusive, or unavailable status,
limitations, and the smallest falsifiable validation. Record with
`$science-provenance`; `$science-review` is mandatory before material claims.
Retain failed quality checks and excluded observations without silent repair.

## Boundaries

- Cells from one sample are not independent replicates.
- Integration can erase biology; cell-type labels and perturbation predictions
  remain model outputs, not experimental or clinical truth.

