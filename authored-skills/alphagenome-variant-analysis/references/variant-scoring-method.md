# AlphaGenome variant scoring method

## Claim semantics

Classify every conclusion before interpreting its score:

- **Predicted track effect:** the model's alternate-allele prediction differs
  from its reference-allele prediction for one specified track, modality,
  window and aggregation. Report the signed difference and preserve both values.
- **Predicted tissue or cell-type effect:** the stated track metadata identifies
  the requested biological context and the prediction is present for it. A
  close tissue name is not a substitute; unmatched tracks are unavailable.
- **Measured molecular effect:** requires an experimental measurement such as
  RNA-seq, ATAC-seq, ChIP-seq or a validated reporter assay. Model tracks alone
  cannot support this class.
- **Functional or clinical effect:** requires orthogonal functional or clinical
  evidence and a design appropriate to that claim. Model score alone cannot
  establish function, pathogenicity, causality or treatment relevance.
- **No detected predicted effect:** only when the requested outputs were
  returned, validated and below a prespecified criterion. Missing output,
  service error or unsupported track is `unavailable`, never a null effect.

## Scoring and record selection

The reference-versus-alternate comparison is made for a declared modality and
scorer. Record scorer name/version, returned output type and units, biosample or
cell type, gene/transcript where applicable, raw score, quantile score, allele
direction and any scorer aggregation. `tidy_scores` uses `gene_name` and
`output_type`; inspect returned columns before filtering and do not silently
substitute `gene_symbol` or a guessed `modality` field.

For an exploratory broad scan, use the recommended *differential* scorers and
exclude active-allele scorers (`ACTIVE`) and CAGE/PROCAP scorers when following
the inherited scan recipe. The inherited example flags `abs(quantile_score) >
0.995` as a screening threshold, not a calibrated significance cutoff. Rank by
the declared raw-score magnitude only after retaining sign and scorer context.
Filter to phenotype-relevant biosamples only when the user supplied that
context, and record the exact matching rule. Keep results from distinct output
types separate unless a prespecified, justified aggregation says otherwise.
The inherited example requests a 1-Mb interval centered on the variant and
creates the API client at `dns:///gdmscience.googleapis.com:443`; record the
actual request window and endpoint rather than assuming those defaults.

The API's recommended scoring can compare REF and ALT predictions, apply a
spatial mask, aggregate signal over bases, optionally transform or scale it,
and subtract REF from ALT; optional aggregation can then combine selected tracks.
Record operation order because transform-before-sum and sum-before-transform
need not agree. A gene-level RNA-seq summary, local chromatin window and splice
site score answer different questions and are not interchangeable. State
coordinate convention, input interval and exact mask boundaries, especially for
indels and windows clipped at sequence ends.

## Source dependencies and independence

Pin the reported model release and SDK/client version, API endpoint, request
time, genome assembly, annotation/track metadata release when exposed, selected
track IDs, scorer configuration and raw-response hash. If the server does not
expose a version, record it as unknown instead of inferring it from the client.
Model outputs can share training data, targets, annotations and sequence
features; multiple tracks, tissues or scorers are not independent replications.
An evaluation locus used in training, tuning or model selection is not a held-out
validation locus. Preserve dataset/locus provenance when known; label unknown
overlap `unverified` and restrict conclusions accordingly.

## Uncertainty and controls

Carry uncertainty as separate fields for reference-allele validity, API/model
version, track-to-tissue match, scorer calibration, biological replication,
training/evaluation overlap and unsupported inference. A quantile ranks against
the scorer's reference distribution only. Do not interpret a large score as a
probability of an observed or pathogenic effect.

Where suitable data exist, use positive controls such as independently measured
eQTL or MPRA-validated variants in the same modality and comparable context.
Use matched random or common variants as negative/background controls, matching
allele class, local sequence context, distance to gene/TSS and relevant
frequency/context variables where data allow. Avoid treating a control variant
as independent if it shares a locus, LD block, assay batch or source cohort with
the target. Record matching fields and imbalance. If no suitable controls are
available, mark the result exploratory.

## Sensitivity and applicability

Vary a biologically justified set of tracks/cell types, window or gene mask,
aggregation/transform, score-ranking rule and model release when available.
Report every variant of the analysis. Call the result fragile if plausible
choices reverse sign, materially reorder priority, or change the claim class;
otherwise state the tested range without claiming global robustness.

This method is most directly applicable to sequence contexts and output
modalities represented by the selected model tracks. It may not represent the
user's cell state, developmental stage, stimulus, ancestry, rare sequence
context, complex haplotype or non-human assembly. API scope, rate, terms and
available model releases can change; check the current official documentation
at execution time and do not extrapolate beyond the returned track metadata.

## Common failure modes and checks

- **Assembly or allele mismatch:** check reference bases against the declared
  assembly and reject the score if they disagree.
- **Wrong field or scorer family:** inspect columns and scorer metadata; check
  that a differential scorer was used for a REF/ALT effect.
- **Track/tissue mismatch:** match exact track and biosample metadata; otherwise
  report unavailable rather than substituting a nearby context.
- **Threshold fishing or over-ranking:** freeze threshold and ranking rule
  before examining scores; retain the full table and label post hoc scans.
- **Window or indel alignment artifact:** inspect masks and coordinate mapping,
  compare plausible windows, and report boundary failures.
- **Training/evaluation overlap:** compare locus and cohort provenance when
  available; label unresolved overlap and do not call the result held out.
- **API/service failure:** record status and retry only according to current
  API guidance; never turn a missing response into a biological negative.

## Sources

- Avsec et al., “Advancing regulatory variant effect prediction with
  AlphaGenome,” *Nature* (2026); use the paper for model/evaluation context,
  not as evidence for a particular locus. The AlphaGenome variant-scoring
  documentation describes REF/ALT scoring, masks and aggregation; pin the SDK
  release and access date because online API details can change.
- GTEx Consortium, “The Genotype-Tissue Expression (GTEx) pilot analysis:
  multitissue gene regulation in humans,” *Science* (2015), for eQTL context.
- Melnikov et al., “A systematic dissection and optimization of inducible
  enhancers in human cells using a massively parallel reporter assay,” *Nature
  Biotechnology* (2012), for MPRA assay context.
- Tewhey et al., “Direct identification of hundreds of causal regulatory
  variants using CRISPR/Cas9 tiling screens,” *Nature Genetics* (2016), for
  experimental perturbation context.
