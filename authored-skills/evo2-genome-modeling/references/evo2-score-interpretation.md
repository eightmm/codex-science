# Evo 2 genomic score and evidence contract

## Claim classes

| Class | Assign when | Boundary |
|---|---|---|
| Sequence likelihood | A pinned autoregressive model's next-token log probabilities are summed/averaged for a declared DNA window. | It is model fit to sequence, not a probability of biological activity. |
| Variant score | Matched reference and alternate windows produce a declared log-likelihood difference or ratio under fixed context. | It is a model preference, not a measured variant effect or pathogenicity. |
| Embedding similarity | A named layer and pooling produce a reproducible representation distance. | Similarity alone does not imply regulatory, evolutionary, or functional equivalence. |
| Predictive association | A downstream predictor is evaluated on grouped independent genomes/assays against declared baselines. | It supports only the measured target and evaluated domain. |
| Generation hypothesis | A sequence is sampled under pinned model, context, decoding, and constraints. | Novelty or plausibility does not imply safety, activity, or experimental validity. |

For every score, state whether it is total or mean autoregressive log likelihood,
reference/alternate log-likelihood ratio or difference, embedding similarity,
or a fitted phenotype output. Specify tokenization, strand, coordinates,
window boundaries, context inclusion, normalization, sign, and the exact comparison.
Do not call a sequence-score difference a causal variant effect. Do not report
raw score as a probability of pathogenicity, fitness, expression, or function.

## Source, genome, and evaluation dependence

Freeze Evo 2 code/version, checkpoint revision and checksum, tokenizer, scoring
implementation, context policy, and hardware/precision. Record training-data
release/cutoff and checkpoint license/weight terms where the release documents
them; otherwise state unknown and retain unresolved overlap risk. Preserve the
assembly accession/version, coordinate convention, contig, strand, reference
allele, normalization, window extraction command, and hashes. Map each token back
to genomic coordinates where the method supports it.

Split at the independent genome, organism/lineage, locus, and assay unit needed
for the claim. Keep overlapping windows, reverse complements of one locus,
reference/alternate pairs, paralogous regions, and propagated records in the
same split. Audit exact and homologous training overlap; report nearest-train
similarity, assembly/source dates, and gaps in the audit. A random window split
from one genome is not a held-out organism or independent biological replicate.

## Uncertainty and calibration

Report uncertainty in labels/assays, sampling over independent genomes or loci,
and method sensitivity to model release, context, strand, and score definition
separately. Bootstrap at the independent group, never the token/window level
when windows overlap. Include denominators, class balance, failures, and
uncertainty intervals. Raw sequence scores are not calibrated clinical
probabilities. A downstream probability requires training-only calibration
and evaluation on an independent, target-representative set; state calibration
method and reliability results. For generated sequences, uncertainty includes
seed/decoding variability and should not be presented as biological confidence.

## Controls and sensitivity

For variant analyses, include known deleterious and benign variants with
independent assay labels and provenance; use matched reference/alternate windows
and report conflicts. Add shuffled or GC/composition-matched random DNA as a
scoring sanity check, and a simple conservation or nearest-homolog baseline.
When appropriate, compare both strand conventions and confirm reverse-complement
handling does not create duplicate held-out examples. Controls do not substitute
for an independent genome or assay.

Vary model size/checkpoint, context length and window placement, strand, and
scoring strategy (full-window versus local or alternate marginal scoring where
defined). For generation also vary decoding seed/settings within the approved
budget and assess constraint/filter stability. A conclusion is fragile if score
sign, rank, control separation, subgroup result, or decision-relevant metric
changes under plausible settings. Report the range and qualify or abstain; do
not choose settings using the held-out outcome.

## Applicability, generation, and failure detection

- Low-homology or out-of-distribution genome: detect by lineage and nearest
  training similarity; stratify, qualify, or abstain where no evaluation support
  exists.
- Species bias: report organism/lineage coverage and subgroup performance;
  training on some clades does not establish transfer to another.
- Context overflow or boundary artifacts: validate token count, effective
  context, truncation and window placement; repeat plausible placements and
  report omitted bases.
- Tokenization/coordinate mismatch: check accepted alphabet, ambiguous bases,
  reference allele, strand conversion, token-coordinate mapping and hashes;
  fail rather than silently repairing sequence or coordinates.
- Leakage/memorization: audit benchmark/training release overlap, exact matches,
  homologs and source dates; label unresolved overlap and avoid held-out claims.
- Control failure or calibration error: inspect shuffled/GC-matched scores,
  conservation baseline, and independent reliability; do not convert raw score
  to pathogenicity probability.
- Generation memorization or constraint failure: compare nearest database
  neighbors, exact/near-identical training matches, composition, required
  constraints, and filter failures; preserve all failed outputs.
- Unsafe biological use: generated DNA remains a computational hypothesis;
  do not automatically synthesize, deploy, or optimize it for harmful function.

## Sources

- Brixi et al., “Genome modeling and design across all domains of life with
  Evo 2,” bioRxiv preprint (2025): Evo 2 genomic sequence modeling and design
  context; cite a peer-reviewed version only after checking it against the
  primary record.
- Brixi et al., Evo 2 model and code release documentation (Arc Institute and
  collaborators, 2025): consult the exact checkpoint release for supported
  tokenization/context, hardware, and licensing terms.
- Meier et al., “Language models enable zero-shot prediction of the effects of
  mutations on protein function,” *NeurIPS* (2021): an example of model-based
  mutation ranking; its protein setting is not validation of Evo 2 DNA scores.
