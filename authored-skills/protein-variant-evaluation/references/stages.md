# Stages and pack-local contract

## Identity and scope

The prediction unit is one substitution-defined sequence in one exact protein
construct and assay context. Freeze source accession/version, organism, isoform,
reference hash, assay protocol/release, allowed inference, split policy and
nearest-training/pretraining overlap evidence in the run artifacts. The helper
checks declared groups and exact sequences; it does not compute homology or
prove absence of pretraining overlap. Unknown overlap remains unresolved.
Keep all mutants, isoforms, duplicate sequences and homologs in one split;
freeze homology thresholds and cluster assignments before model fitting.
Fit heads, transforms, calibration and thresholds on training data only.

Input `protein-variant-input-v1` contains a nonempty `proteins` list. Each item:
- `id`, canonical uppercase 20-residue `reference`, integer `coordinate_offset`,
  `split` (train/validation/test), nonempty `homology_group`.
- `model` and `assay` each declare `definition`, nonempty `units` and `direction`
  (`higher` or `lower` means more of the prespecified desirable outcome).
- Nonempty `controls` with at least one essential control: unique `id`, boolean `essential`, `status`
  (passed/failed/unavailable) and artifact/source-linked `evidence`.
- Nonempty `variants`: unique `id`, `substitutions` list (empty is WT), `model`
  and `assay` score objects. A score has `status` (ok/failed/missing), `value`
  (finite JSON number iff ok, otherwise null), exact declared `units`; failures
  and missingness also require `reason`.

A substitution is `A11V`; zero-based reference index is
`11 - coordinate_offset - 1`. Thus offset 10 maps numbered residue 11 to the
first reference residue. This is an explicit numbering convention, not an
inferred PDB insertion-code map. Supply a verified mapping for discontinuous
numbering before entering this format; never guess an offset. Unsupported
residues, indels, overlapping edits, no-op edits, incorrect WT, duplicate variant
sequences and identity/split collisions fail closed. Full variant sequences and
SHA256 hashes are produced; substitutions are applied to the original reference.

## Method and assessment handoffs

Freeze the method descriptor described in method-discovery.md and register its
hash with the stage output. A supplied-score lane requires producer, exact method,
formula, checkpoint or explicit synthetic status, source artifact hashes and
failure log. The helper validates numeric consistency, not producer authenticity.
For model execution use existing executor provenance, context/token mapping,
batch invariance and a bounded pilot. Pin length/chunk policies and do not
silently truncate. Structure checks retain chain/residue maps and share a model
dependence lane when appropriate; confidence is not functional validation.

Prespecify matched positive/negative assay controls, WT/synonymous controls where
available, sequence sanity controls, baseline and acceptance thresholds. Essential
failed or unavailable controls block candidate acceptance; do not retune on test
controls. Supplied control statuses are assertions requiring independent review.

## Analysis and failure semantics

`protein-variant-analysis-v1` is an ordinary pack artifact, not a runtime schema.
It preserves all variants, score statuses, explicit sequences, edit distances,
score definitions, controls, total and paired counts. `model_rank` uses average
ranks for ties, best oriented model score first. Spearman is Pearson correlation
of average ranks after orienting both model and assay directions. Positive means
agreement with the declared desirable outcome. No absolute-value correlation.
The baseline is negative substitution count (higher is closer to WT), explicitly
model-free and scientifically weak; it is not a conservation or evolutionary
model. Model and baseline correlations use the same complete model/assay pairs.
Report pair attrition and assess missingness sensitivity before interpreting it.

Constants or fewer than two pairs yield null plus a reason. Raw scores from
different proteins/assays/units are never pooled; `pooled_metric` is null. Do not
infer significance, confidence intervals or predictive generalization from this
small deterministic analysis. A real study needs independent protein/assay-group
uncertainty and a frozen suitable benchmark. Null/negative correlations and zero
reviewable candidates remain valid outcomes.

## Review and provenance

Use one existing checkpoint with ordered IDs from plan.json. Every stage records
immutable input/output paths and hashes in the existing artifact manifest, with
software/environment, resource envelope, logs, exclusions and failures. No global
payload keys, checkpoint states or automatic routing changes are introduced.
The helper is read-only and emits stdout; the coordinator saves and registers it.
Record actual execution separately from method documentation and offline tests.

`candidate_status=unreviewed` only means declared essential controls passed;
`blocked-controls` blocks scientific acceptance. Neither status is a review
receipt or candidate recommendation. Obtain independent record/source/method
review as applicable, reconcile findings and hand off reviewed computational
candidates with limitations and an experimentally falsifiable next test. Never
present PLM scores as pathogenicity, clinical probability, measured function,
expression, fitness or effect. Real execution needs explicit installation,
weight, restricted-transfer and compute authorization under existing gates.
