# Borzoi prediction protocol

## Claim semantics

The prediction unit is one normalized variant or alternate sequence compared
with its matched reference sequence, scored for a pinned checkpoint/ensemble,
target track, tissue, coordinate window and aggregation.

- **Predicted RNA-seq effect:** a reference/alternate difference in model
  coverage for an identified target track or transcript. Report the signed
  difference, exact aggregation and scale. This is not measured gene expression.
- **Predicted regulatory-track effect:** a difference in a named output target
  with its assay modality and tissue/cell metadata. It does not establish
  measured accessibility, binding or histone modification.
- **Measured expression or chromatin effect:** requires external experimental
  data with sample, assay and measurement provenance; prediction alone cannot
  support the class.
- **Functional or causal effect:** requires appropriate perturbation or other
  causal evidence. A sequence model score is a hypothesis generator, not proof.
- **No predicted difference:** report only when the requested track and both
  allele predictions pass validation and a criterion fixed before scoring.
  Missing target, failed window or unsupported context is `unavailable`.

## Input, tracks and aggregation

Pin hg38 or hg19 explicitly (or another supported genome build); record
zero-based/one-based conventions, chromosome naming, strand, REF/ALT alleles,
reference-validation source, boundary policy and transcript annotation release.
The assembly, gene annotation and target metadata must describe compatible
coordinates. Do not change the build to make a variant fit without documenting
and validating the mapping.

Record code commit, model/checkpoint checksums, ensemble members, target metadata
release, preprocessing, sequence length, output bin size, shift/reverse-complement
ensembling, precision, device, deterministic settings and seeds. Store target
IDs as supplied by the model metadata and preserve mapping to their assay/cell
labels. Do not infer labels from output order.

For each target, retain raw reference and alternate tracks and their aligned
coordinate maps. Define whether the variant-centered local window, transcript
body, exon mask, promoter or distal interval is being summarized. State whether
aggregation is signed sum/mean, maximum absolute change, log ratio or another
explicit reduction. Keep separate modality-specific outputs separate; averaging
RNA-seq, chromatin and TF tracks has no default scientific meaning. Include
window-edge behavior and strand handling in the recorded method.

## Source dependencies and independence

The model's sequence-to-track training data, public assay tracks, transcript
annotations and benchmark labels may share experiments or source cohorts.
Before a performance claim, inspect the Borzoi publication and repository
manifests for training/validation/test provenance and compare locus, assay,
cell-type and release IDs with evaluation data. If overlap cannot be checked,
state `training_overlap=unverified`; do not call evaluation held out. Nearby
windows, LD-linked variants, repeated tracks from one assay and ensemble members
are dependent evidence, not independent test examples.

Keep evaluation by independent locus or cohort; deduplicate propagated records
and avoid splitting overlapping sequence windows across train and evaluation.
Pin input assembly, annotation release, model revision and target release so a
later rerun can reconstruct track identity. Retain unknown or ambiguous mapping
as uncertainty.

## Uncertainty and controls

Separate uncertainty due to model ensemble, training overlap, track-cell match,
input allele/build, sequence-window boundary, aggregation choice and biological
assay variability. If no predictive interval is available, do not create one
from deterministic track outputs. Report ensemble variation as a model
sensitivity measure, not a confidence interval for biology.

Use known eQTL or MPRA-validated variants as modality-appropriate positive
controls when independent outcome data are available. Compare to matched random
or common variants as background controls; match allele class, local sequence
context, gene distance and measurement context where possible. Use a conserved
coding exon and a neutral region as sanity controls for conservation-associated
sequence behavior, but do not treat either as proof of regulatory prediction
calibration. Record source cohort, matching rules, missingness and any sharing
with model training data. Controls drawn from the same training/benchmark source
do not establish independent validation.

## Sensitivity and applicability domain

Vary plausible target tracks/tissues, window width and placement, transcript or
distal-element mask, aggregation and ensemble/model version. Record the full
comparison. If a plausible choice changes effect direction, ranking or claim
class, report the conclusion as fragile. Do not select a track or window after
seeing which produces the desired direction without marking that analysis
exploratory.

Borzoi predicts RNA-seq coverage and supported regulatory targets from long
sequence contexts represented by its training data. Transfer to unseen cell
types, conditions, species, poorly annotated transcripts or distal elements not
represented within the input context is extrapolation. An enhancer-to-gene
assignment is not established by sequence proximity alone. Flag structural or
complex variants, repetitive sequence, reference gaps, boundary clipping,
ancestry-specific haplotypes and unsupported output targets as out of domain or
uncertain.

## Common failure modes and detection

- **Build or coordinate mismatch:** independently check reference alleles and
  map boundaries against pinned assembly; stop on disagreement.
- **Training/evaluation overlap:** compare source cohort and locus manifests;
  split by locus/cohort and report unresolved provenance.
- **Target-label confusion:** validate output dimensions against pinned target
  metadata; fail rather than trust target order.
- **Window-edge or strand artifact:** inspect coordinate maps and rerun a
  prespecified window/strand sensitivity check.
- **Track/cell extrapolation:** compare target metadata to the requested context;
  call unseen contexts extrapolative and narrow the claim.
- **Remote sequence exposure or accidental resource use:** check gate decision,
  execution record and actual command/network path before scoring.
- **Dropped failed windows:** reconcile planned loci with outputs and exclusions;
  retain every failure and do not change the denominator silently.

## Sources

- Linder et al., “Predicting RNA-seq coverage from DNA sequence as a unifying
  model of gene regulation,” *Nature Genetics* (2025), for Borzoi model design,
  evaluation and variant scoring. Use the model repository's pinned commit for
  executable details and target definitions.
- GTEx Consortium, “The Genotype-Tissue Expression (GTEx) pilot analysis:
  multitissue gene regulation in humans,” *Science* (2015); Melnikov et al., “A
  systematic dissection and optimization of inducible enhancers in human cells
  using a massively parallel reporter assay,” *Nature Biotechnology* (2012); and
  Tewhey et al., “Direct identification of hundreds of causal regulatory
  variants using CRISPR/Cas9 tiling screens,” *Nature Genetics* (2016), for
  eQTL, MPRA and perturbation control context.
