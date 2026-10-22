# Conservation and regulatory-track interpretation

## Claim semantics

Assign one class to each statement:

- **phyloP substitution-rate score:** a score for departure from an explicit
  neutral evolutionary model along a specified alignment/phylogeny. Positive
  values generally support slower-than-neutral evolution (constraint); negative
  values indicate faster-than-neutral evolution (acceleration). Confirm the
  selected track's score convention and species/clade before applying this
  reading.
- **phastCons conserved-element score:** a model-derived probability/score for
  membership in a conserved element under a phylogenetic hidden Markov model.
  It is not a signed test of acceleration and is not interchangeable with
  phyloP.
- **TFBS annotation overlap:** an interval overlaps a named binding-site or
  motif annotation track. State source, assay/prediction status and track
  release. Overlap does not prove protein binding in the target tissue,
  condition or individual.
- **Measured molecular effect:** requires an assay for expression, chromatin,
  binding or function. Conservation or an annotation track alone cannot support
  this class.
- **No detected score/overlap:** only when the requested track was retrieved
  completely for the normalized interval and its records were parsed. Missing
  score, null, absent track, truncation or API error are `unavailable`, not a
  negative finding.

Do not equate constraint with function. Conserved sequence can have unknown or
context-dependent function; unconserved sequence may still be functional in a
lineage-specific or rapidly evolving context.

## Track and evolutionary dependencies

Record exact UCSC assembly, track ID, table/source, track metadata/release,
source alignment set, species count, species tree/clade and neutral model when
exposed. phyloP scores depend on the neutral substitution model and alignment;
phastCons additionally uses a conserved-element model and local transition
assumptions. Scores from different alignments, taxa, models or releases are not
directly comparable without a stated harmonization method.

The same multi-species alignment, reference assembly and upstream annotation may
underlie many adjacent scores. Adjacent bases/windows, phyloP and phastCons from
one alignment, and multiple UCSC mirrors are not independent evidence. Preserve
source dataset and release identifiers. Do not infer an unreported species
count or neutral model from a familiar track name; set it to unknown.

UCSC API track output may represent display-oriented wiggle data; UCSC documents
lossy compression for some browser score displays compared with original score
files. For precision-sensitive analysis, compare the chosen API result with the
original download source and record which was analyzed.

## Uncertainty and controls

Carry separate uncertainty for assembly/build, coordinate conversion, alignment
coverage and gaps, species composition, neutral model, track release, score
quantization, repeat/mappability, and TFBS assay/context. A single score is not a
confidence interval. Missing values and unaligned bases remain missing; do not
impute zero. Report bases queried, bases with score, bases aligned and each
exclusion denominator when those can be computed.

Use a known conserved coding exon as a positive conservation sanity control and
a neutral or weakly constrained region as a negative/background control, on the
same assembly and alignment track. For variant analyses, add matched random or
common variants with comparable local context and interval length. These check
retrieval and broad score behavior; they do not validate a regulatory function
claim. Record control loci, track/alignment, matching rules and whether controls
were chosen before target score inspection.

For TFBS annotations, use a known assay-positive locus in the same assay/source
as a retrieval sanity control and a matched background interval as comparison.
Motif predictions (for example JASPAR-derived annotations) and experimental
binding tracks (for example ENCODE or ReMap records) must remain labeled as
different evidence types.

## Sensitivity and applicability

Vary the conservation track, alignment set, species/clade, interval/window size,
score summary and API versus original score source when available. Vary TFBS
track source, assay and cell context separately. Report every tested setting.
Call a conclusion fragile if score direction, classification, overlap status or
ranking changes materially under a reasonable alternative. Do not select a
species set or window after seeing which supports the target claim.

Applicability is limited to the reference build, aligned taxa and regions with
reliable alignment and score coverage. Repeats, segmental duplications, assembly
gaps, lineage-specific insertions, paralogs, low-complexity sequence and poor
alignability can make scores absent or misleading. Conservation does not resolve
cell-specific regulation, developmental timing, environmental response or
causal effect. TFBS tracks are bounded by assay, sample, antibody/motif model,
cell type and release; no track does not mean no binding.

## Common failures and detection

- **phyloP/phastCons confused:** inspect track description and scoring method;
  report the metric under its own name and keep sign/probability semantics apart.
- **Wrong assembly or coordinate basis:** convert coordinates explicitly and
  check known sequence/track landmarks; stop when mapping is ambiguous.
- **Alignment gap treated as zero:** inspect missingness and alignment coverage;
  preserve unaligned bases as unknown.
- **Repeat-region artifact:** inspect RepeatMasker/low-complexity context and
  compare score coverage; qualify or exclude by a predeclared rule.
- **Species/model omitted:** inspect track metadata and record unknowns; do not
  claim cross-track comparability without them.
- **Track listing mistaken for data:** require returned records and response
  validation; classify absent or restricted track as unavailable.
- **TFBS overlap overread:** distinguish motif prediction from assay annotation
  and verify whether sample context matches the claim.
- **Lossy display values:** compare original score files for precision-sensitive
  use; disclose if only the display/API track was analyzed.

## Sources

- Siepel et al., “Evolutionarily conserved elements in vertebrate, insect, worm,
  and yeast genomes,” *Genome Research* (2005), for phastCons and conserved
  element detection.
- Pollard et al., “Detection of nonneutral substitution rates on mammalian
  phylogenies,” *Genome Research* (2010), for phyloP constraint/acceleration
  scores under a neutral model.
- UCSC Genome Browser REST API documentation and track metadata, version/access
  date recorded per query; use for endpoint and current track-specific semantics.
