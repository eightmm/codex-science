# AlphaGenome evaluation, controls and inference limits

## Claim classes and evaluation unit

The prediction unit is one normalized variant against one declared reference
allele, scored for one model release, track or explicitly defined track group,
mask and aggregation. A **predicted regulatory effect** is a model-generated
REF/ALT difference in an output such as RNA-seq, CAGE/PRO-cap, chromatin
accessibility, histone mark, TF binding, splicing or contact map. It is not a
measured change in expression, chromatin state, binding, splicing or contact.
A **measured effect** requires an assay; a **functional consequence** requires
evidence that the molecular change alters a relevant biological process. A
clinical or pathogenic claim needs clinical evidence and is outside this
prediction procedure.

Define evaluation endpoints and loci before observing target scores. State
whether evaluation is a descriptive single-locus prediction, a benchmark against
assay outcomes, or a ranking task. Keep cell types, modalities and score scales
separate. If reporting performance over loci, give the included and excluded
denominators, split unit, metric, uncertainty interval and all exclusions.

## Cohort, locus and release dependencies

Track predictions may derive from public assays; variant labels and controls may
come from GTEx, MPRA or other cohorts also used for model training, tuning or
benchmark selection. Check model-paper data manifests and source dataset IDs
against evaluation records. Split by chromosome region, locus or cohort as
appropriate to prevent nearby variants, LD-correlated loci, repeated assays or
propagated labels from crossing train and evaluation partitions. Do not count
different tracks, tissues, related variants or duplicate source records as
independent observations.

Record genome build (`hg38`, `hg19` or another supported assembly), coordinate
system, annotation release, track metadata, SDK/model release and evaluation
dataset version. Do not lift coordinates silently. For historical comparisons,
preserve the original build and mapping procedure and flag ambiguous or
multi-mapped loci. A changed API release can change outputs even when the client
code is unchanged.

## Uncertainty, controls and sensitivity

Report uncertainty from model release, track-cell match, assay noise and sample
size, allele/assembly normalization, score calibration and train/evaluation
overlap separately. If no calibrated interval or replicate model is supplied,
say so; scorer quantiles are not confidence intervals.

For positive controls, use variants with independent eQTL or MPRA evidence
matched to the prediction modality and biological context. For negative or
background controls, use matched random or common variants that satisfy the
same assembly, allele, local-context and scoring protocol. Record ascertainment,
matching variables, cohort and overlap. For a sanity check, compare a known
regulatory locus with a local background region and inspect whether the predicted
track is present and biologically compatible; this is not independent proof.

Vary track/cell type, local versus gene-centered window, mask width, aggregation
(for example, signed mean versus absolute maximum), ranking threshold and model
version where available. A change in effect sign, target ranking or conclusion
under a defensible alternative makes the result fragile. Report the range and
do not choose the preferred configuration after seeing which supports the claim.

## Applicability domain and failure detection

Predictions are bounded by learned sequence-to-assay relationships, trained
species, assay/track coverage and represented cellular contexts. Distal enhancer
effects outside the input window, rare haplotypes, structural variants, complex
alleles, novel cell types and environment-specific regulation may be poorly
represented. Missing tracks or cells are coverage limits, not evidence of no
effect. Use orthogonal experiments for a measured claim.

- **Overlapping evaluation loci or cohorts:** inspect source accessions, locus
  distances, LD and label provenance; split by the independent unit.
- **Mismatched build or transcript release:** validate allele and annotation
  coordinates against pinned references; stop if identity cannot be resolved.
- **Selected controls or thresholds after scoring:** compare the frozen plan to
  the analysis record; relabel as exploratory and require a held-out check.
- **Correlated tracks counted as replications:** group by dataset, cell context
  and cohort; report one independent unit per defined evidence source.
- **Extrapolation from prediction to function:** inspect claim wording and
  require assay/perturbation evidence for measured or functional classes.

## Sources

- Avsec et al., “Advancing regulatory variant effect prediction with
  AlphaGenome,” *Nature* (2026), for the published evaluation design and model
  limits. AlphaGenome API/scoring documentation is versioned at execution time.
- GTEx Consortium (2015), for multi-tissue eQTL context; Melnikov et al. (2012),
  for MPRA context; Tewhey et al. (2016), for CRISPR tiling perturbation. A
  benchmark citation supports its described benchmark only; it does not validate
  a new target locus.
