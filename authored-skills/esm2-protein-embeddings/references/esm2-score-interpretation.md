# ESM-2 score and evidence interpretation

## Claim classes

Assign the narrowest class supported by the analysis and label every material
claim with its class and status.

| Class | Assign when | Does not establish |
|---|---|---|
| Extraction integrity | A pinned checkpoint returns expected tensors, masks, and batch-invariant values within prespecified tolerance. | Biological meaning or predictive validity. |
| Representation similarity | A declared layer/pooling produces a reproducible distance or similarity between sequences. | Functional equivalence, interaction, or common ancestry. |
| Sequence plausibility | Per-residue masked log probabilities are aggregated as pseudo-log-likelihood under the frozen model. | A probability that the protein is functional or natural. |
| Mutation score | A specified masked-marginal reference/alternate log-odds or pseudo-log-likelihood difference ranks substitutions. | Measured effect, pathogenicity, fitness, or calibrated probability. |
| Predictive association | A downstream model is evaluated on a declared, independent split with fixed labels, baseline, metric, and uncertainty. | Causality or transfer beyond the tested domain. |

ESM-2 is a masked language model. For pseudo-log-likelihood, mask each residue
in turn and sum or average its conditional log probability; this is a scoring
convention, not a normalized joint sequence likelihood. A masked-marginal
mutation score compares alternative amino-acid conditional log probabilities
at a masked site, optionally relative to the reference residue. State the exact
formula, sign, residue aggregation, and any length normalization. Embedding
similarity requires a named layer, residue handling, pooling, normalization,
and distance metric. Keep score scale distinct from experimental effect size.

## Sources, dependence, and release identity

Record checkpoint name/revision, weight checksum when available, tokenizer,
model code revision, pretraining release or database cutoff when documented,
retrieval source, and license/weight terms. Do not infer terms from the skill's
frontmatter. If cutoff or provenance is unknown, record it as unknown and treat
overlap risk as unresolved.

Construct splits at the independent biological unit. Cluster homologous
sequences before splitting; keep exact duplicates, isoforms/construct variants,
mutant series from one assay, and repeated measurements from the same protein
grouped together. If the benchmark may overlap pretraining or a retrieval source,
report overlap checks and nearest-training identity; do not call a random split
held out. Propagated records and database copies are dependent evidence.

## Uncertainty and calibration

Keep three uncertainty sources separate: input/label uncertainty, sampling
uncertainty over independent proteins or assay groups, and model/method
sensitivity across checkpoints, layers, context policies, or scoring rules.
Bootstrap at the independent protein/assay-group level, not at residue level.
Report denominators, metric interval, excluded or unscorable sequences, and
uncertainty source. Raw likelihood, embedding distance, and mutation score are
not probabilities of pathogenicity or function. Any calibrated downstream
probability needs a training-only calibration procedure and an independent
calibration/evaluation split; report calibration method and target population.

## Controls and sensitivity

For mutation ranking, use independently curated known deleterious and benign
variants with assay provenance, matched for protein, position, and substitution
where feasible. Do not tune thresholds on the test controls. Include shuffled
or composition-matched random sequences as a score sanity check and a simple
conservation/profile baseline. A control failure triggers investigation; it is
not repaired by selecting a favorable layer after inspection.

Vary model size/checkpoint, context length and truncation/chunking, embedding
layer/pooling, and score strategy (single-site masked marginal versus an
explicit pseudo-log-likelihood difference). Prespecify the primary result. Call
a conclusion fragile when rank order, sign, threshold classification, or
decision-relevant metric changes materially under a plausible setting; show the
range and downgrade the claim rather than averaging incompatible scores.

## Applicability and failure detection

- Low-homology or out-of-distribution sequences: detect by nearest-train
  identity, alignment coverage, or declared domain checks; stratify and abstain
  where benchmark support is absent.
- Species/assay bias: report organism, protein family, assay, and split-group
  coverage; compare subgroup performance and do not extrapolate across absent
  lineages without validation.
- Context loss: detect sequences exceeding model context or altered chunk
  boundaries; record omitted residues and test alternative chunk policies.
- Tokenization/normalization errors: validate accepted amino-acid alphabet,
  special-token placement, residue-to-token map, and sequence hashes; retain
  ambiguous or unsupported residues as exclusions, not silent substitutions.
- Leakage or duplicated records: audit sequence identity, assay provenance,
  and source cutoff; regroup or label the evaluation non-independent.
- Miscalibration: compare reliability and calibration error on independent data;
  never read a raw score as clinical probability.
- Padding/batch defect: compare single-item and mixed-batch output under stated
  tolerance; block extraction claims if masks or values disagree.

## Sources

- Lin et al., “Evolutionary-scale prediction of atomic-level protein structure
  with a language model,” *Science* (2023): ESM-2 model and masked protein
  language modeling context.
- Meier et al., “Language models enable zero-shot prediction of the effects of
  mutations on protein function,” *NeurIPS* (2021): masked marginal mutation
  scoring and benchmark framing; it does not make scores calibrated clinical
  probabilities.
- ESM Metagenomic Atlas / ESM model release documentation (Meta AI, 2022):
  use the exact checkpoint release documentation for weights, tokenizer, and
  license terms.
