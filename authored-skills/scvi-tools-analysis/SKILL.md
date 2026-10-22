---
name: scvi-tools-analysis
description: "Build and evaluate reproducible scvi-tools workflows for single-cell RNA, protein, chromatin, spatial, or multimodal data using scVI, scANVI, totalVI, MultiVI, PeakVI, DestVI, or related models."
license: MIT
---

# scvi-tools Analysis

## Decision contract

Record dataset/sample/donor identifiers, assay and count layer, feature registry,
biological and technical units, estimand, deployment population, and whether the
design identifies the requested effect. Prespecify model, split, likelihood,
baseline, diagnostics, metrics and uncertainty. Mark transductive choices and
define criteria that would contradict or leave the claim inconclusive. Distinguish
model-derived embeddings, clusters, annotations and integration results from
measured biology.

## Reference usage

Read [references/scvi-model-evidence.md](references/scvi-model-evidence.md)
before choosing a likelihood, covariate, latent representation, annotation, or
integration metric. It specifies count assumptions, over-integration checks,
claim semantics, sensitivity, and limits on benchmark interpretation.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned
   scvi-tools stack, downloading hub models or datasets, and using GPU/long
   compute. Never upload governed human data without authorization. Follow
   `$cx-compute-environment`. Check and follow dataset/model terms. Record
   approvals and unresolved gates.
2. Define assay, biological units, count layers, features, batches/covariates,
   labels, controls, missing modalities, and task. Split by donor/sample/well,
   never randomly by cells from the same biological unit. Audit whether treatment,
   phenotype, cell type, donor, site, and acquisition batch are confounded; stop
   when the requested biological effect is not identifiable from the design.
3. Select the model and likelihood for the assay and estimand. For count data,
   justify the negative-binomial or zero-inflated negative-binomial (ZINB)
   assumption against the assay and model implementation; pin scvi-tools and
   dependencies, AnnData registry fields, covariates, architecture,
   train/validation split, early stopping, seeds, hardware, and precision.
4. Smoke-test data registration and a few training steps; continue only if the
   registered fields, count domain, and output shapes validate. Train into
   `artifacts/<run-id>/scvi/`; retain immutable input/split IDs, setup schema,
   model/config/checkpoint, histories, posterior outputs, environment, logs, and
   failures.
5. Run posterior predictive/model criticism checks. Compare PCA/Harmony or other
   simple task-appropriate baselines; report donor-level uncertainty, batch and
   biology conservation, subgroup/OOD performance, and sensitivity to covariates.
6. For integration, use held-out-donor or held-out-batch evaluation with known
   marker genes. Treat kBET/LISI as mixing measures and ARI as label agreement
   against supplied labels, each only for the property measured. Check whether
   improved mixing removes known biology; record denominators and failures.
7. Vary seeds, latent dimension, HVG count, resolution when clustering, likelihood,
   and plausible batch covariates. Downgrade if conclusions or held-out metrics
   change materially or biology is erased; retain variants and decisions.
8. Verify applicability and source dependencies using the reference. Record with
   `$science-provenance`; review with `$science-review` before material claims.
   Preserve failed checks, unavailable evidence, and the smallest falsifiable
   follow-up.

## Outputs

Return one `scvi-evidence-v1` record containing input and independent-unit IDs
and hashes (`input_hashes`, `unit_ids`, `unit_hashes`), schema/registry and
transformations (`input_schema`, `registry`, `transformations`), and assumptions
(`assumptions`);
claim identifier (`claim_id`), claim class and status (`claim_type`, `status`);
source, cohort, model, and reference-use dependencies (`dependencies`); split,
likelihood, covariates, model settings, environment, and seeds (`analysis`);
split IDs (`split_ids`); control findings (`controls`); baseline findings
(`baseline`); diagnostics and per-unit metrics with uncertainty
and denominators (`results`); sensitivity variants (`sensitivity`); applicability
domain and limitations (`applicability`, `limitations`); exclusions, failures,
and nulls (`failures`); rejected alternatives and rationale (`alternatives`);
artifact paths and hashes (`artifacts`); and smallest falsifiable follow-up
(`next_action`). Status is `supported`, `contradicted`, `inconclusive`, or
`unavailable`. Record with `$science-provenance`; `$science-review` is mandatory
before material claims. Preserve failed checks and distinguish training completion
from scientific acceptance.

## Boundaries

- A visually mixed latent space is not proof of correct integration.
- Never encode treatment or the biological signal as a nuisance covariate merely
  to improve batch mixing; require held-out-donor batch predictability and
  biology-conservation criteria.
- Do not use test cells to choose highly variable genes, normalization,
  covariates, architecture, epochs, or calibration unless declared transductive.
- A likelihood is a modeling assumption, not proof that observed counts follow
  that distribution; latent variables and transferred annotations are not
  measured biological entities or experimental validation.
- Never upload governed human data without authorization. Follow
  `$cx-compute-environment` for package, hub, and GPU/long-compute gates.
