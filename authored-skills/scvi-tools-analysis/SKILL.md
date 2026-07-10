---
name: scvi-tools-analysis
description: "Build and evaluate reproducible scvi-tools workflows for single-cell RNA, protein, chromatin, spatial, or multimodal data using scVI, scANVI, totalVI, MultiVI, PeakVI, DestVI, or related models."
license: MIT
---

# scvi-tools Analysis

## Gate

Ask once before installing a pinned scvi-tools stack, downloading hub models or
datasets, and using GPU/long compute. Never upload governed human data without
authorization. Follow `$cx-compute-environment`.

## Workflow

1. Define assay, biological units, count layers, features, batches/covariates,
   labels, controls, missing modalities, and task. Split by donor/sample/well,
   never randomly by cells from the same biological unit. Audit whether treatment,
   phenotype, cell type, donor, site, and acquisition batch are confounded; stop
   when the requested biological effect is not identifiable from the design.
2. Select the model for the assay and estimand; pin scvi-tools and dependencies,
   AnnData registry fields, likelihood, covariates, architecture, train/validation
   split, early stopping, seeds, hardware, and precision.
3. Smoke-test data registration and a few training steps. Train into
   `artifacts/<run-id>/scvi/`; retain immutable input/split IDs, setup schema,
   model/config/checkpoint, histories, posterior outputs, environment, logs, and
   failures.
4. Run posterior predictive/model criticism checks. Compare PCA/Harmony or other
   simple task-appropriate baselines; report donor-level uncertainty, batch and
   biology conservation, subgroup/OOD performance, and sensitivity to covariates.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- A visually mixed latent space is not proof of correct integration.
- Never encode treatment or the biological signal as a nuisance covariate merely
  to improve batch mixing; require held-out-donor batch
  predictability and biology-conservation criteria.
- Do not use test cells to choose highly variable genes, normalization,
  covariates, architecture, epochs, or calibration unless declared transductive.
