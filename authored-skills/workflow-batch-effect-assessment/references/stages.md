# Stages and local records

All checked-in data are synthetic fixtures. The command is
`python3 scripts/validate_batch_effect_assessment_pack.py examples/workflow-batch-effect-assessment/pack.json`.
It accepts one bundle JSON argument, prints JSON on stdout and writes nothing.
Missing, extra or unknown arguments and admission failures produce JSON with
status refused and a labelled finding on stderr, exit 2. Help is plain stdout,
exit 0. There is no output-file option. Python standard library, local CPU only;
no installation, network, GPU, remote execution or implicit download.

## Pack-local schemas

All five schemas use an object root, `schema`, real integer `schema_version` equal
to 1, and boolean `fixture`. Every checked-in input has fixture true. Unknown or
missing fields are refused. These records are ordinary provenance artifacts,
never new global payloads. Claims are copied separately into the existing
claim-register by the coordinator.

- `batch-effect-pack-v1`: `stages`, `inputs` with `rules` and `matrix` identities,
  `frozen_rules_sha256`, `freeze_before_matrix`, timezone-aware `frozen_at` and
  `matrix_read_at`, `study_outputs`, `claims`, `status`, `group_adjusted`.
  Every identity has canonical relative `path` and lowercase 64-hex `sha256`.
  `study_outputs` identities refer to evidence records. `group_adjusted` is false;
  the reference provides unadjusted one-way metrics, not adjusted attribution.
- `batch-effect-rules-v1`: `samples`, `covariates`, `confounding_rule`,
  `feature_filter`, `transformation`, `minimum_samples`, `thresholds`,
  `permutations`, `thresholds_changed_after_outcomes`, `exploratory`.
  Sample rows have `id`, `batch`, `group`, numeric `covariates` by declared name,
  boolean `qc`, nullable technical `replicate` ID, boolean `available`, nullable
  `reason`. Unavailable rows require a named reason, null batch/group/replicate,
  empty covariates and qc false; they are excluded from batch counts and cannot
  appear in matrix columns. Every available sample must appear exactly once.
  Replicate IDs cannot cross biological groups. Covariate values are within
  minus one trillion and one trillion. The fixed confounding rule is
  `group-single-batch-or-rank-deficient`. Filter fields are `method` equal to
  `complete-nonconstant`, `uses_group_labels` false, `frozen` true. This small
  reference refuses all group-label filters, including externally frozen ones.
  Transform is `identity` or nonnegative `log2p1`. Minimum samples is a real
  integer from 4 to MAX_SAMPLES. Thresholds are `median_batch_r2` in zero to one,
  `batch_silhouette` in minus one to one, `permutation_alpha` in zero to one,
  and nonnegative `qc_dispersion` at most MAX_NUMBER. Permutations have real
  integer `seed` from zero through 4294967295, real integer `count` from one
  through MAX_PERMUTATIONS, `strata` equal to `group`, and
  `minimum_success_fraction` greater than zero and at most one. Changed
  post-outcome thresholds require exploratory true; retain the original run.
- `batch-effect-matrix-v1`: unique string `samples` column IDs, unique string
  `features` row IDs, and `values`, a rectangular feature-by-sample list of
  finite numbers or null. Null stays missing in the source and missingness output;
  complete-case feature exclusion has the named reason `missing-values`.
  Constant transformed features have reason `zero-variance`. No samples are
  silently discarded, no missing values become zero and no labels select features.
- `batch-effect-evidence-v1`: bounded nonempty string `kind` and `result`.
  These labels are checked against cited bytes and output identities; labels alone
  cannot establish authenticity, independence or truth.
- `batch-effect-result-v1`: ordered `stages`, `evidence_level` arithmetic-only,
  `review` unavailable, `input_identities`, `rules_sha256`, `assessment`, `claims`
  and `limitations`. Assessment records exact `confounding` rank/columns and
  single-batch groups, `missing_counts`, `filtered_features`, `retained_features`,
  `unavailable_samples`, `sample_count`, `exploratory`, `status`, `metrics`, and
  `failed_controls`. Metrics are null for confounded designs. Otherwise they
  contain `per_feature` batch/group R-squared and F, `median_batch_r2`,
  `median_group_r2`, `batch_silhouette`, `group_silhouette`, `batch_permanova`
  with pseudo-F, p-value, seed, count, successful count and strata, and
  `qc_dispersion` with status, pair count, RMS distance and distance SD.

Claim rows have `id`, `kind`, `status`, `text`, `support`. Support identities also
include `origin` from study, external, independent or preregistered. Status uses
the existing claim-register vocabulary; kind is descriptive or associational.
The lexical and evidence gates below apply regardless of a benign kind label.

## Limits and immutable admission

Module constants are MAX_BYTES 64 MiB per artifact, MAX_TOTAL_BYTES 256 MiB,
MAX_TOTAL_NODES 4000000 bundle-wide preparse JSON values, MAX_ARTIFACTS 128 distinct
inodes, MAX_DEPTH 32, MAX_TEXT 4096 characters, MAX_ITEMS 20000 per JSON container,
MAX_SAMPLES 128, MAX_FEATURES 256, MAX_COVARIATES 8, MAX_VALUES 32768 cells,
MAX_PERMUTATIONS 999, MAX_METRIC_WORK 8000000 sample-feature-permutation operations,
MAX_CLAIMS 100, MAX_SUPPORT 100, and MAX_NUMBER absolute numeric magnitude 1e100.
Dimensions are checked before dependent sets, cross products, elimination,
permutation work or QC pair allocation. Inputs with zero variance, too few
samples, zero residual variance or no retained features are refused. A small
or zero p-value never substitutes for these controls.

Pin every ancestor from the filesystem root with directory-descriptor opens,
no symlinks, and retain all device/inode identities. Resolve every artifact
component relative to the pinned descriptor. Require lstat regular file,
nonblocking no-follow open, descriptor fstat identity/size match and bounded
size-plus-one read. Hash the parsed bytes. Distinct hardlink aliases share reads,
parsing, byte and JSON budgets; path identities remain separate. Re-read hashes
once per inode at completion and compare the entire visible ancestor chain before
and after rechecks. Refuse replacements, growth, FIFOs, devices, directories,
symlinked components, escaping or noncanonical paths and exceeded budgets.
Duplicate JSON keys at any depth, non-object roots, nonfinite/huge numbers,
bool-as-number and non-integer seeds/counts/versions are labelled refusals.
Preparse counting streams container matches without allocating a match list.

The validator writes no file, ref or record. Concurrent calls consume independent
immutable snapshots. A kill leaves input bytes unchanged and may leave partial
stdout; discard incomplete JSON. The coordinator owns atomic artifact publication,
checkpoint advancement and immutable handoffs outside this command.

## 01-rule-freeze

Accepted input: pack and rules paths plus hashes, with sample sheet embedded in
rules. Call the pack's validator to validate/hash rules before opening the matrix.
Freeze every rule and record timestamps with freeze strictly before first matrix
read. Output artifact: frozen `batch-effect-rules-v1`, registered through existing
`$science-provenance`. A declared freeze and its hash cannot prove history.
Failed filter, strata, timestamp or post-outcome controls stop admission and
retain the failed attempt. Only interpretation-changing choices require a human
decision; routine offline hashing needs no new gate.

## 02-matrix-qc

Accepted input: frozen rules path/hash and matrix path/hash. Call the same
read-only validator; output is the identity/missingness/exclusion portion of
`batch-effect-result-v1`. Check unique identities, rectangular finite values,
complete sample coverage, named unavailable reasons, fixed transform and fixed
feature filter. Preserve raw nulls and all exclusions. Fail instead of repairing
missing samples, invalid transforms or no retained features. No human gate is
needed for admitted synthetic CPU fixtures.

## 03-metrics

Accepted input: the same immutable rules and matrix identities. The module's
`reference_computation` implements the bounded arithmetic; output is the metrics
portion of `batch-effect-result-v1`. There is no external executable dependency.

Design columns are intercept, sorted batch indicators except the first, sorted
group indicators except the first, and frozen numeric covariates. Exact rational
elimination uses decimal representations, with no floating rank tolerance. A
group in one batch or rank less than the column count is confounded, even if
some other groups span batches. At least two batches and groups are required.

For each complete nonconstant transformed feature, SSB is the sum of group size
times squared group-mean deviation from the grand mean; SSW is the sum of squared
within-group deviations. R-squared is SSB over SSB plus SSW; F is SSB divided by
k minus one, over SSW divided by n minus k. Report these separately by batch
and by biological group. Medians are descriptive, with no multiplicity claim.
Zero residual variance is refused rather than returning infinity.

For the centroid silhouette-style score, a is distance to the sample's own
centroid including itself, and b is distance to the nearest other centroid.
Average b minus a divided by max of a and b, using zero when both vanish.
This is a centroid approximation, not the pairwise silhouette. Use Euclidean
geometry over retained transformed features with one common numerical scale;
never standardize each feature silently.

Batch pseudo-F aggregates SSB and SSW over these features with the same degrees
of freedom; this equals the Euclidean one-factor PERMANOVA-style pseudo-F.
Shuffle batch labels only within frozen biological group strata with Python's
seeded generator. The p-value is one plus exceedances plus unsuccessful data
draws, divided by one plus the fixed count. Equality counts as an exceedance.
Only the labelled permutation-degenerate error counts as an unsuccessful draw;
other errors propagate. Require the frozen successful fraction. P-value
resolution is one divided by count plus one. This is a restricted permutation
check, not a fitted group-adjusted model or independent attribution.

QC dispersion uses every cross-batch pair of frozen QC samples: report root mean
squared Euclidean distance and population SD of those distances in transformed
units. With no cross-batch QC pair both numbers are null and status unavailable;
this never becomes a passed control. No technical or QC replicate is counted as
independent biological replication. Failed controls and negative results survive.

## 04-summary

Accepted input: unchanged identities and computed metrics. Output artifact:
`batch-effect-result-v1`. Confounding always returns `unassessable` and null
metrics. Otherwise RMS QC distance above its frozen threshold yields unassessable
with `qc-dispersion` in failed controls. Detection requires all three inclusive
thresholds: median batch R-squared and batch centroid score at least their frozen
values, and permutation p-value at most alpha. Otherwise return `not-detected`.
The declared status must agree. Exact boundary equality is admitted.

## Claim boundaries

The conservative English lexical gate is case-insensitive, uses whole words and
allows word-character suffixes for these prefix families: caus*, mechanis*,
therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, recommend*,
prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*.
It additionally refuses truth, physical validity, biological signal, differential
expression, and correct* or remov* wording. Spaces or hyphens are accepted in
those phrases. Group-adjust* wording is refused separately. Confounded designs
also refuse no batch, absen* and not detect* wording. This filter is incomplete,
conservative and refuses negations too; human source and method review remains
necessary. Association cannot establish causality, computed agreement cannot
establish physical or clinical validity and review approval cannot establish truth.

Positive statuses supported, suggestive and replicated cannot cite records whose
kind OR result contains review, approval, computation, numerical agreement,
physical, clinical or truth indicators. Admitted positive technical records have
kind observed-technical-record and result batch-structure; labels do not prove
source authenticity. External, independent or preregistered support cannot share
a path OR hash with a study input, output or pack. Any citation with kind or result
unavailable forces unavailable status, including mixed evidence and negative
statuses. Empty evidence also forces unavailable status. Unavailable text refuses
supported, replicated, suggestive and significan* in addition to the general gate.
Replicated is always refused for this single-table reference. Boundary refusals
precede later evidence gates; unavailable-evidence precedes positive support gates.

## 05-handoff

Accepted input: immutable pack, rules, matrix, evidence and result paths/hashes.
Register ordinary artifacts using `$science-provenance`; separate claim-register
entries preserve assumptions, required support, falsifiers, denominators, controls,
conflicts, dependencies, uncertainty, applicability, exclusions, rejected choices
and the smallest discriminating next observation. Advance one coordinator-owned
checkpoint in stage order. `$science-review` owns record/source/method review and
rigor classification; pack review remains unavailable. Failed controls, nulls,
exploratory thresholds and unavailable evidence must be in the handoff.

Human gates occur only before installation, restricted transfer, a new host,
GPU/remote/heavy compute or an interpretation-changing choice. None is exercised
by these offline fixtures. Correct deterministic refusals once at the source;
do not automatically retry or overwrite a prior snapshot. Source authenticity,
historical freeze timing, independent replication, biological validity and effect
removal remain unestablished by software acceptance.
