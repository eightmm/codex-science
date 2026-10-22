# scGPT Evidence Calibration

## Claim classes

Assign a claim ID before evaluating results and use one primary class per claim.

- **Representation:** embeddings preserve useful structure for a declared task.
  Require a prespecified downstream metric, independent-unit split, and a
  baseline. Embedding visualization alone is descriptive, not validation.
- **Clustering:** a partition is stable and useful for the declared population.
  Require an explicit resolution, replicate-level stability, marker or external
  annotation checks, and an independent baseline. Clusters are computational
  groupings, not discovered cell types by themselves.
- **Annotation/label transfer:** transferred labels agree with a reference for a
  defined target domain. Require a predeclared confidence/rejection rule and
  held-out donor or sample estimates. The prediction is not a measured label.
- **Integration:** nuisance variation is reduced while known biology remains.
  Require separate mixing and conservation measurements; success on one does not
  imply success on the other.
- **Perturbation/prediction:** a model predicts a held-out response. Require a
  split by donor/experiment, a fixed baseline, uncertainty, and experimental
  validation before biological or causal wording.

Use statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`.
For each claim, record required support, falsifier, evidence IDs, uncertainty,
applicability, and dependencies. Do not turn an unavailable label or uncertain
cell identity into a negative observation.

## Data and source dependencies

Record raw count source, assay, tissue, organism, donor/sample/experiment IDs,
feature annotation release, filtering, gene mapping, and preprocessing. Cell rows
from the same donor, sample, experiment, or library are dependent observations;
use that biological unit for splitting and uncertainty. A random cell split leaks
unit-specific signal and cannot support generalization to new donors.

Pin the scGPT repository revision, checkpoint revision/hash, tokenizer and gene
dictionary, checkpoint training cutoff if known, inference code, preprocessing,
and runtime. Record dataset or corpus names and releases when documented. Public
checkpoint reuse, dataset reuse, and fine-tuning on related cohorts are shared
dependencies. Unknown pretraining membership is an uncertainty, not evidence of
independence. Report potential overlap with evaluation cohorts and near-duplicate
samples; do not call train/test source independence unless established.

Fit gene selection, scaling, normalization, vocabulary extensions, calibration,
and thresholds using training data only. A fixed reference mapping may use the
whole declared reference in a transductive design, but identify that design and
do not score it as inductive held-out performance.

## Uncertainty and confidence

Report donor/sample-level variation or interval, independent-unit count, cell and
unit denominators, missing labels, exclusions, and seed variation. A cell-level
bootstrap understates uncertainty when cells share a donor. State how intervals
were computed and which sources of uncertainty they omit.

Label-transfer scores are ranking/confidence outputs, not calibrated probabilities
unless calibration was assessed on independent units in the target domain. Choose
the rejection threshold before test evaluation. Report coverage and error among
accepted labels as well as performance on all eligible observations.

## Controls and baselines

Include known marker genes or externally supported labels where appropriate;
check that expected markers remain interpretable across donors and batches.
Use negative-control labels or permuted labels to detect leakage where the task
permits. Compare simple PCA with logistic/nearest-neighbor prediction and a
batch-aware baseline. A model should not be credited for complexity unless it
improves the prespecified held-out-unit metric.

For integration, report a mixing measure such as kBET or LISI only as evidence
about mixing, and a conservation measure such as ARI only as agreement with its
specified labels. No single metric establishes good integration. Inspect known
biology and an unintegrated baseline; excessive mixing that removes marker,
condition, or cell-type structure is a failure even when batch mixing improves.

## Sensitivity and fragility

Repeat stochastic workflows across prespecified seeds. Vary latent dimension,
highly variable gene count, clustering resolution, confidence threshold, and
plausible preprocessing choices. When batch adjustment is used, vary the
covariates and compare the no-integration baseline. Record numerical results and
claim changes for every variant, not just the selected run.

Treat the claim as fragile if held-out donor/batch performance, accepted-label
coverage, cluster membership, marker interpretation, or biological conclusions
change materially under these choices. Define materiality before analysis where
possible; otherwise label the sensitivity assessment exploratory and retain the
observed changes.

## Applicability domain and failure detection

scGPT performance may shift across species, tissue, developmental state, assay,
sequencing depth, gene identifier release, and perturbation regime. Check overlap
of target features with the tokenizer dictionary and report dropped or unknown
genes. A poor or truncated mapping can make an embedding appear valid while
omitting relevant biology.

- **Gene mapping loss:** compare mapped features and counts to the source matrix;
  report unmatched genes and halt if the declared representation is not met.
- **Donor leakage:** inspect split IDs for shared donor/sample/experiment; rebuild
  the split before scoring if units cross partitions.
- **Over-integration:** compare mixing with marker/condition conservation and the
  unintegrated baseline; downgrade if biology is removed.
- **Overconfident transfer:** inspect calibration, coverage, and errors by donor;
  use abstention where scores do not support a reliable assignment.
- **Corpus overlap or shift:** document known pretraining/evaluation overlap and
  tissue/species distance; report unknowns and restrict the claim accordingly.
- **Seed/resolution instability:** compare assignments and conclusions across
  variants; retain unstable outcomes as inconclusive.

## Sources

scGPT model and corpus claims should be checked against the cited scGPT paper by
Cui et al. (2024) and the exact checkpoint card/revision used; the paper does not
establish generalization to a new tissue, species, or cohort. Use Stuart et al.
(2019) for the integration objective of balancing dataset mixing and biological
conservation, not as proof that a particular metric validates an integration.
Use Luecken et al. (2022), *Benchmarking atlas-level data integration in single-
cell genomics*, for benchmark design and metric caveats. Use the original kBET
paper (Büttner et al., 2019) and LISI method (Korsunsky et al., 2019) only for the
properties their measures quantify. Do not infer label truth or biological
validity from those metrics.
