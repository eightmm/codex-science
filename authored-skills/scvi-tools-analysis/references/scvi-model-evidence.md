# scvi-tools Model Evidence

## Claim semantics

Assign each claim a stable ID and primary class before comparing results.

- **Representation:** latent variables preserve task-relevant information for a
  stated population. Require held-out independent units, task metrics, and simple
  baselines; a latent plot is descriptive only.
- **Integration:** batch-associated variation is reduced while specified biology
  is conserved. Mixing and biology-conservation criteria are separate.
- **Annotation:** model-transferred labels meet a prespecified error and coverage
  rule on held-out donors. They are predictions, not measured cell identities.
- **Differential or perturbation analysis:** a model-based contrast estimates the
  stated estimand under declared design and likelihood assumptions. Confounded
  design or post-selection does not support causal language.
- **Prediction:** performance transports to a defined held-out population. Report
  independent-unit evaluation and uncertainty; validation remains domain-bound.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable`. Record required
support, falsifier, evidence, dependencies, uncertainty, and applicability for each
claim. Training completion, reconstruction fit, and visual mixing are not
scientific acceptance.

## Count assumptions and source dependencies

Record the measured assay and whether values are raw integer counts, normalized
values, or transformed values. State the chosen likelihood and its assumptions.
Negative-binomial models represent overdispersed count variation; zero-inflated
negative-binomial (ZINB) models add a zero-generating component. Use the
likelihood supported by the selected assay and implementation and justify any
ZINB choice; do not assume excess zeros automatically require a zero-inflated
model. Do not register normalized values as counts without an explicit, supported
procedure. Check gene/cell dimensions, finite values, nonnegative counts, and
registry fields before fitting.

Record the scvi-tools and dependency versions, model class, setup registry,
checkpoint, seed, data release, feature annotation, batch covariates, and code
revision. Donors, samples, wells, sites, and acquisition runs can be shared
dependencies across cells and portal exports. Split and resample at the
independent biological unit, not the cell. If an atlas, pretrained model, or
reference annotation shares source cohorts with evaluation data, disclose it and
do not call the evaluations independent.

Fit HVGs, normalization, covariate choices, calibration, and thresholds within
training data unless transduction is explicitly part of the target use. A
transductive pipeline can be useful but must not be presented as inductive
held-out generalization.

## Batch covariates and over-integration

Identify which variables are technical nuisances and which encode treatment,
phenotype, cell type, time, or other biology of interest. Do not include a
biological variable as nuisance merely to improve batch mixing. If nuisance and
biology are confounded, report the estimand as unidentifiable from the observed
design rather than claiming the model separates them.

For integration, evaluate held-out-donor or held-out-batch behavior and compare
mixing metrics against conservation of known marker genes, conditions, and cell
types. kBET and LISI assess aspects of local batch mixing; ARI measures agreement
with supplied labels under a declared clustering/label comparison. They do not
prove biological correctness or causal validity. Compare with unintegrated PCA,
Harmony where appropriate, and a task-appropriate simple baseline.

## Uncertainty and diagnostics

Report intervals or variation over independent units, donor/sample counts,
cell denominators, excluded observations, missing modalities, and seeds. A
cell-wise bootstrap is not a substitute for unit-level uncertainty. State whether
uncertainty covers sampling, optimization, model specification, or only a subset.

Use posterior predictive checks and diagnostics matched to the selected model,
including count distribution and zero behavior where relevant. Label-transfer
scores are not calibrated probabilities unless calibration is evaluated in a
separate, appropriate target-domain set. Report subgroup and OOD performance and
abstention coverage.

## Controls and sensitivity

Use known marker genes and declared biological controls to test whether expected
signals remain. Include negative-control features or labels where appropriate.
Compare simple PCA/Harmony or other task-appropriate baselines; do not treat one
integration score as a composite acceptance criterion. Record each metric's
meaning and denominator.

Vary seeds, latent dimension, HVG count, clustering resolution if used, plausible
likelihood choices, and candidate batch covariates. Compare with no integration.
Prespecify a material-change threshold where possible. If key contrasts, cell
assignments, conservation checks, or held-out metrics change materially, mark the
claim fragile or inconclusive and preserve all variants.

## Applicability and common failure modes

Results are conditional on assay chemistry, species, tissue, donor mix, sample
processing, modality availability, and model version. A model trained on one
distribution may fail under site, tissue, species, disease-state, or sequencing
depth shift. State the target domain and avoid transport claims without relevant
held-out data.

- **Invalid count input:** inspect integer/count semantics, range, finite values,
  and registry before training; stop if the likelihood input contract fails.
- **Biology in nuisance covariate:** inspect design confounding and covariate
  meaning; stop if the requested effect cannot be identified.
- **Over-integration:** compare mixing to marker/condition conservation and
  unintegrated baseline; downgrade when expected biological structure disappears.
- **Cell leakage:** verify no donor/sample/well appears across splits; resplit
  before claiming generalization.
- **HVG/test leakage:** trace feature-selection fit IDs; refit on training only
  unless explicitly transductive.
- **Unstable latent or clustering:** compare seeds, dimensions and resolutions;
  report unstable assignments as inconclusive.
- **Calibration or shift failure:** inspect reliability/coverage by donor and
  subgroup; abstain or narrow applicability when confidence degrades.

## Sources

Use the scvi-tools documentation and model-specific paper for the selected model
class and likelihood; pin the documentation/release because defaults change.
Lopez et al. (2018), *Deep generative modeling for single-cell transcriptomics*,
introduces scVI; it does not validate every later model or dataset. Townes et al.
(2019), *Feature selection and dimension reduction for single-cell RNA-Seq based
on a multinomial model*, motivates count-aware representation and cautions against
blind continuous normalization assumptions. Luecken et al. (2022),
*Benchmarking atlas-level data integration in single-cell genomics*, informs
benchmark design. kBET (Büttner et al., 2019), LISI (Korsunsky et al., 2019),
and ARI should be cited only for their defined measurement properties, not as
standalone proof of biological validity.
