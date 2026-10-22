# Borzoi evaluation and control design

## Claims and observed outcomes

Separate: (1) a model-predicted difference between alternate and reference
sequence; (2) a measured change in RNA-seq or another assay; and (3) functional
or causal effect on a phenotype. Report which evidence lane supports each
claim. The output modality and tissue/track labels belong to the prediction
claim only. An eQTL association or MPRA readout is measured evidence and has its
own uncertainty and context; it does not automatically prove organism-level
function.

Predeclare the benchmark unit (variant, locus, transcript or assay), inclusion
criteria, held-out split, primary metric and threshold. When scoring many loci,
report denominator and exclusions, class balance, uncertainty interval and
aggregation. A result is not held out if its locus, overlapping sequence
window, LD proxy, assay label or propagated annotation entered training or
model/threshold selection.

## Training-data overlap and source independence

Use the pinned Borzoi paper, code and data manifests to identify training and
evaluation source studies, cell types, annotations and dates. Compare these to
the target eQTL, MPRA or other evaluation cohort at both cohort and locus level.
Keep data accession/version, genome assembly, annotation version, cell type and
experiment identifiers. If manifests do not permit the comparison, record the
gap and downgrade evidence status.

Split by non-overlapping genomic regions or chromosomes when feasible and by
cohort/assay where that addresses the suspected dependency. Remove or group
overlapping windows and LD-correlated variants according to a prespecified rule.
Do not count alternate tracks from the same sample/assay, repeated records,
related variants or multiple ensemble checkpoints as independent replicates.

## Controls

Use known eQTLs for an expression-track positive control and independently
MPRA-validated variants for a reporter-effect positive control. Match the
predicted track's tissue and assay context as closely as the available metadata
allows. Use matched random or common variants as background negatives, matched
on allele class, local sequence composition/context, distance to a gene and
frequency/context variables when known.

For sequence and conservation sanity checks, compare a known conserved coding
exon and a neutral region with matched window processing. Confirm the expected
sequence/track behavior only at the level of the named track. A coding exon
control does not calibrate enhancer effects and conservation is not functional
evidence. Record control source, ascertainment, matching balance, split and
whether the control cohort may overlap training.

## Uncertainty and sensitivity

Report separate uncertainty fields for dataset overlap, model/checkpoint,
ensemble variation, cell/track identity, annotation/build, window boundary,
aggregation and assay measurement. A deterministic model score is not an
uncertainty interval. Where a benchmark has repeated measurements, report their
unit and variability; do not transfer that variability to an unmeasured target.

Test declared alternatives for track selection, tissue/cell type, input-window
placement/width, transcript or region mask, signed versus magnitude aggregation,
and model version. Define material change in advance, such as sign reversal,
ranking shift beyond a prespecified threshold or claim-class change. If any
defensible setting meets that criterion, label the result fragile and preserve
all tested settings.

## Applicability and common failure checks

Predictions are most interpretable for model-supported assays and cell contexts
that resemble training data and for regions correctly represented in the pinned
reference assembly. Unseen cell types/conditions, distant enhancers outside the
input window, structural variants, repeats and poorly represented haplotypes
are extrapolations. No prediction covers all regulatory mechanisms.

- **Locus leakage:** inspect windows and LD across splits; group by locus and
  report exclusions.
- **Evaluation label leakage:** compare assay/annotation source IDs and release
  dates with model data manifests; call overlap unresolved if not inspectable.
- **Assembly mismatch:** reference-check every allele, confirm coordinate
  convention and transcript release, and stop on mismatch.
- **Track mismatch or absent target:** reconcile target IDs and tissue metadata;
  classify absent predictions as unavailable.
- **Post hoc window/track selection:** compare the frozen analysis contract to
  executed settings; report exploratory selections and require independent data.
- **Overclaim from prediction:** verify that reported measured or functional
  wording has corresponding assay or perturbation evidence.

## Sources

- Linder et al. (2025), *Nature Genetics*, Borzoi model and its evaluation; use
  the pinned repository and data manifests for the run-specific provenance.
- GTEx Consortium (2015), for multi-tissue eQTL study context.
- Melnikov et al. (2012), for massively parallel reporter assay context.
- Tewhey et al. (2016), for CRISPR tiling perturbation context.
