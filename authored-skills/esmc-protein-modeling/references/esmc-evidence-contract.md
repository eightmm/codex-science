# ESMC model outputs and evidence contract

## Claim classes

| Class | Assign when | Boundary |
|---|---|---|
| Representation | A named ESMC layer/pooling or SAE activation is extracted reproducibly. | It is a coordinate in a learned representation, not a measured mechanism. |
| Sequence plausibility | Masked residue conditionals are aggregated as pseudo-log-likelihood. | A masked language model score is not a normalized probability of biological function. |
| Substitution score | A masked-marginal reference/alternate log-odds or declared likelihood difference is computed. | It ranks model preference; it is not experimental effect or pathogenicity. |
| SAE feature association | A specific SAE feature is activated and associated with a declared sequence or label set. | Interpretability or label association does not establish causal function of the feature. |
| Downstream prediction | A fitted predictor is tested on grouped independent data against baselines. | Performance is limited to the evaluated assay, population, and split. |

State whether the score is per-residue conditional log probability, a sum/mean
pseudo-log-likelihood, masked-marginal substitution score, embedding similarity,
SAE activation, or a supervised prediction. Record sign and reference/alternate
order, residue/token alignment, normalization, and versioned SAE dictionary.
These conventions are not interchangeable. Similarity is not evolutionary
relatedness unless separately evaluated, and score magnitude is not effect size.

## Source dependencies and release terms

For each run, freeze ESMC family and scale, checkpoint revision/checksum,
tokenizer, model/library revision, layer/SAE release, and any hosted endpoint
version. Record the pretraining cutoff and source documentation when available;
otherwise mark it unknown. Preserve the exact license and terms for code,
checkpoint, and SAE files individually. Skill-level license metadata alone does
not establish checkpoint or endpoint rights. Record whether sequences stayed
local; never expose authentication tokens in logs or manifests.

Group train/validation/test data by protein/homology cluster, assay campaign,
construct, and propagated record lineage. Keep close homologs and related
mutant/measurement series within one split. Report nearest-training identity
and assay/source overlap. Random row splits or duplicated public measurements
cannot establish independent transfer. If a benchmark overlaps pretraining or
Biohub retrieval sources, disclose the audit limits and qualify the result.

## Uncertainty and calibration

Report input and assay uncertainty, sampling uncertainty over independent
protein/assay groups, and method uncertainty over model scale, checkpoint,
context treatment, layer/SAE, and score definition separately. Bootstrap at the
group level. Include denominator, class balance, confidence interval, missing
or failed inputs, and subgroup coverage. A raw ESMC/SAE output is not a
probability of pathogenicity, fitness, expression, or clinical effect. For a
downstream probability, fit calibration on training-only data and assess it on
an independent split from the intended target population; state calibration
method and reliability results.

## Controls and sensitivity

For variant ranking, include assay-backed known deleterious and benign controls
that are independent of threshold selection. Match controls by protein and
assay where feasible; report label source and conflicting labels. Use shuffled
or composition-matched sequences for score sanity and a simple conservation or
profile baseline. Include nearest-homolog and ESM-2 comparison for predictive
tasks, but do not treat either as independent validation when data are shared.

Vary ESMC size and checkpoint, effective context length/chunking, layer and
pooling, masked-marginal versus pseudo-log-likelihood scoring, and SAE version
or feature dictionary. For SAE work, check feature activation across repeated
extraction and sequence perturbations and report feature sparsity/selection
criteria. A result is fragile if signs, rankings, control separation, subgroup
conclusion, or decision-relevant performance changes across plausible settings.
Show sensitivity and downgrade claims; do not select a winning setting using
the held-out set.

## Applicability and failure detection

- Low-homology and out-of-distribution proteins: inspect nearest-train identity,
  alignment coverage, family and organism; stratify and abstain outside support.
- Species or assay bias: report representation by lineage, protein family,
  assay and condition; evaluate subgroups before cross-species transfer claims.
- Context or tokenization mismatch: check residue-to-token maps, unsupported
  symbols, truncation and chunk boundaries; report omitted sequence and exclude
  only under a declared rule.
- Hosted or authenticated execution: verify explicit authorization and endpoint
  revision; record transfer status without storing credentials or private inputs.
- SAE overinterpretation: detect feature instability across dictionary releases,
  perturbations, or examples; report association as descriptive and avoid causal
  mechanism claims absent interventions.
- Leakage or propagated records: audit homology, assay campaign, and source
  lineage; regroup or mark performance as non-independent.
- Batch/padding defects: compare singleton and mixed batches under a declared
  tolerance and validate masks before accepting extraction integrity.
- Calibration failure: inspect reliability on independent target data; never
  translate raw scores into clinical probabilities.

## Sources

- EvolutionaryScale ESM C release materials (model card, code, and license for
  the exact checkpoint): primary description of the model; record the release
  and any accompanying publication only after checking its title and venue
  against the primary record.
- Meier et al., “Language models enable zero-shot prediction of the effects of
  mutations on protein function,” *NeurIPS* (2021): masked-marginal scoring as
  a model-based ranking method, not a calibrated outcome probability.
- Cunningham et al., “Sparse Autoencoders Find Highly Interpretable Features in
  Language Models” (2023): SAE feature decomposition and interpretability
  framing; feature interpretation still requires model- and task-specific tests.
