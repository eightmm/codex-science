# Synthetic LC-MS feature QC stages

All example data, negative cases and expected outputs are synthetic fixtures.
This reference controls procedure; it is not scientific evidence. The accepted
application is an offline arithmetic check of already-acquired untargeted LC-MS
features before differential comparison, with no network, downloads, installation,
remote tasks, GPU or raw-spectrum processing. No third-party library is required.

## Pack-local schemas

All JSON input records have exactly the fields below. Unknown or missing fields
are refused; `schema` is the named string, and `fixture` is `synthetic fixture`.
Schema names are pack-local and add no global artifact kinds or receipt fields.
Integers below must be real JSON integers, never bool, float or string.

- **metab-pack-v1**: `schema, fixture, frozen_rules, rules, sheet, table, report,
  evidence, frozen_rules_sha256, frozen_sheet_sha256, frozen_before_table_read,
  stages`. Artifact descriptors are exactly `{path, sha256}`. `evidence` is a list
  of descriptors. Freeze hashes bind original rules and sheet bytes; the boolean
  must be true. `stages` is exactly `01-freeze, 02-table, 03-features, 04-samples,
  05-handoff` in that order.
- **metab-rules-v1**: `schema, fixture, blank_ratio_max, qc_rsd_max,
  study_missing_max, qc_missing_max, drift, normalization, dilution_r2_min,
  dilution_slope_min, minimum_qc, minimum_dilution, mz_min, mz_max, rt_min, rt_max,
  missing_policy, sample_outlier_distance, minimum_distance_features`.
  Missingness and R-squared thresholds are in [0,1]; other thresholds are finite
  nonnegative numbers at most 1e12. Positive dilution slope is always required.
  QC/dilution minima are integers >=3; distance feature minimum is an integer >=1.
  Ranges have positive width; m/z minimum is positive. `missing_policy` is
  `preserve`. `normalization` is `none` or `median`. `drift` is exactly
  `{method, window, anchors}`, with method `none` or `running-median-qc`, an odd
  integer window in [1,101], and anchors `pooled-qc` only.
- **metab-sheet-v1**: `schema, fixture, groups, samples`. Two distinct frozen
  groups are required. Each sample is exactly `{id, injection_order, sample_type,
  batch, group, dilution}`. IDs and positive integer injection orders are unique.
  Types are `study`, `pooled-qc`, `blank`, `dilution-series`. Only study samples
  have a group; others have null. Only dilution samples have a positive finite
  concentration in [1e-12,1e12]; others have null. Both study groups must occur.
  Every sample carries a batch ID. There must be at least one sample of each type;
  feature-level insufficient controls yield explicit failed metrics, not invented
  values. Study group/batch labels are frozen with this file.
- **metab-table-v1**: `schema, fixture, sample_ids, features`. The sample ID set
  equals the sheet, each ID once; vector order follows `sample_ids`. Each feature
  is exactly `{id, mz, retention_time, values, imputed, unavailable_batches}`.
  Unique IDs and in-range m/z/retention time are required. Intensity vectors are
  finite numbers in [0,1e12] or null. The boolean imputation mask has matching
  length and is all false: this reference never imputes. A true mask, including
  a replacement with zero, is refused. `unavailable_batches` lists batches in
  which this feature was not measured owing to a failed acquisition; all its
  values there must be null. Such a row is unavailable and cannot be retained.
  An observed zero elsewhere remains a measured zero, distinct from missingness.
- **metab-report-v1**: `schema, fixture, rules_sha256, exploratory,
  rsd_population, drift_anchors, features, samples, batch_confounded, headline,
  claims`. The rules hash binds the applied rules. `exploratory` is boolean and
  mandatory when applied rules differ from frozen rules. RSD population and
  anchors are `pooled-qc`. Features are exactly `{id, retained, reasons, status}`
  for every table feature. `retained` is boolean, `reasons` are sorted, unique
  named reasons computed by the reference, and `status` is pass/fail/unavailable.
  Samples are exactly `{id, flags}` for every sheet sample with the computed
  flags. `batch_confounded` is the computed boolean; headlines obey claim limits.
  Claims are exactly `{id, kind, status, text, evidence}` with unique IDs;
  evidence is a unique list of record IDs from evidence artifacts.
- **metab-evidence-v1**: `schema, fixture, records`; each record is exactly
  `{id, kind, result, origin, source}`. `source` is a path-plus-hash descriptor;
  the bytes are read and hash-checked even if they are not JSON. Origin is
  internal/external/independent/preregistered. Noninternal sources may not share
  a path or SHA-256 with any pack input, report, evidence document or pack entry.
  These labels and hashes cannot prove actual independence or preregistration.
- **metab-result-v1**: `schema, fixture, status, review, stages, exploratory,
  inputs, computation, claims, limitations`. Status is `offline-arithmetic-only`,
  review is `unavailable`. `inputs` contains all consumed paths and SHA-256s.
  Computation has `features, samples, normalization_factors,
  retained_feature_count, reason_counts, batch_confounded`. Each feature contains
  identity/ranges, status/retention/reasons, `blank_ratio, qc_rsd_before,
  qc_rsd_after, study_missingness, qc_missingness, dilution, corrected, normalized`.
  Dilution is `{r_squared, slope}` or null. Each sample has
  `id, median_intensity, qc_log_distance, distance_features, flags`.
- **metab-negative-fixtures-v1** is the checked-in test index only:
  `schema, fixture, cases`; each case has `id, path, finding, fixture`.
  It is consumed by acceptance tests, not an existing runtime contract.

## Input safety and budgets

Every artifact path is canonical and relative to the bundle: no absolute path,
parent traversal, backslash, colon, control character or symlink component.
The bundle is opened component by component from the filesystem root using
`O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK` and relative directory descriptors. Every
ancestor's device/inode identity is preserved and checked again after pinning
and before/after final hash verification. Each input uses lstat, nonblocking
no-follow descriptor open, fstat regular-file/identity/size checks, and a bounded
read of size+1 bytes. Hash the parsed bytes. Files are read and parsed once per
(st_dev, st_ino), with a final bounded re-read only for identity/hash verification.
Hardlink aliases share parsing and byte budgets. FIFOs, devices, directories,
symlinks, replaced/growing files and oversized files yield labelled refusals.

Named constants, enforced before work that scales with the corresponding input:
`MAX_BYTES=67108864`, `MAX_TOTAL_BYTES=268435456`, `MAX_TOTAL_NODES=4000000`,
`MAX_ARTIFACTS=128`, `MAX_ITEMS=20000`, `MAX_DEPTH=32`, `MAX_STRING=4096`,
`MAX_NUMBER=1e100`, `MAX_SAMPLES=256`, `MAX_FEATURES=1000`, `MAX_CELLS=200000`,
`MAX_WINDOW=101`, `MAX_RECORDS=128`. These are inclusive ceilings. Counts are
checked before set building and cross-product computation. Per-batch indices and
nearest-QC orders are cached; no per-feature `list.index` lookup is needed.
JSON is bounded before parsing using an upper bound `1 + commas + nonempty
containers`, counted with a non-consuming regex lookahead and `finditer` without
allocating a match list. It can conservatively overcount punctuation inside
strings. The allowance is shared across parsed artifacts, not reset per input.
Duplicate keys, nested duplicates, non-object roots, NaN/Infinity, enormous
numbers, deep nesting, long strings and wrong numeric types are refused.

## 01-freeze: rule and sample-sheet identity

Accepted inputs are `frozen_rules`, applied `rules` and `sheet`, each path plus
SHA-256 from `metab-pack-v1`. Load and validate these before `table` bytes.
Output: immutable `metab-rules-v1` and `metab-sheet-v1` identities and the
coordinator's existing checkpoint. Use `$science-provenance` and the existing
manifest plan shape in `plan.json` (`id, description, status`), one checkpoint
per run with ordered IDs. Freeze all controls listed above before outcomes.
A changed rule retains both versions and requires an exploratory label; it does
not rewrite original inputs. Hash equality and declared timing cannot prove the
actual historical freeze. Missing essentials or an incompatible method stop this
route. Interpretation-changing choices require a human decision before execution.

## 02-table: identity and acquisition controls

Accepted input: `table` path plus SHA-256, the frozen sheet/rules identities.
Call the pack's `compute_feature_qc` through the read-only validator. Output:
validated `metab-table-v1` identity and preserved input records in
`metab-result-v1`. Check sample coverage/uniqueness, injection order, m/z and
retention time, nonnegative finite values, vector dimensions, explicit missing
values and unavailable failed-batch measurements. Failed controls remain in the
table; malformed identities refuse the bundle. No interpretation or permission
gate is needed for authorized offline arithmetic.

## 03-features: fixed reference arithmetic

Accepted identities: the same immutable table, rules and sheet; no alternate
study values as QC anchors. Output: feature records within `metab-result-v1`.

- Blank ratio is mean observed blank intensity divided by mean observed pooled-QC
  intensity before correction, across the table; thresholds fail only when exceeded.
- RSD is sample SD / mean of observed pooled QC, minimum frozen count, before and
  after drift correction and before normalization. Calculation is scaled to avoid
  underflow. A zero mean or too few QC observations makes the metric unavailable
  and fails the feature. Identical positive QC values correctly have RSD zero;
  zero variance here indicates repeatability, not evidence of significance.
- Running median is multiplicative and within batch: for each feature/sample,
  choose the closest observed positive pooled QC anchors by injection-order
  distance, ties to the earlier injection, up to the frozen odd window. Divide
  the raw intensity by their median and multiply by the batch's median observed
  positive QC intensity. QC samples participate in their own reference correction;
  no held-out improvement or scientific validation is claimed. Insufficient
  positive anchors flag `drift-unavailable` and retain the raw values visibly.
- Study and pooled-QC missingness are null count / total samples in each type.
  Unavailable cells count as missing while retaining their distinct batch label.
- Fit dilution intensity after drift against frozen concentration using ordinary
  least squares with an intercept. Report R-squared and slope; reject insufficient
  n, zero concentration/response variance or non-finite results as unavailable.
  A negative or zero slope always fails, even if R-squared is one.
- Named reasons: `unavailable-batch`, `drift-unavailable`, `qc-degenerate`,
  `qc-rsd`, `blank-unavailable`, `blank-ratio`, `study-missingness`,
  `qc-missingness`, `dilution-degenerate`, `dilution-linearity`. Retain only rows
  with no reasons. Unavailable batches yield status unavailable. All other failed
  rows have status fail. Preserve every row, measurement and named reason.

Empty/degenerate numerical inputs never yield a significant-looking statistic.
There is no statistical testing, differential comparison or inference engine.
A failure is not fixed by refitting on study samples or changing a threshold.

## 04-samples: preserved flags and feature accounting

Accepted identities: previous stage inputs and computed rows. Output:
`metab-result-v1` sample records, retained count, reason counts and confounding.
Median normalization, if frozen, uses every positive observed corrected feature
in each sample before any filtering, then scales its median to the median of
sample medians. Empty positive signals refuse that normalization; `none` keeps
all factors one. All original missing values remain null.

For each retained feature and batch, form the median log1p normalized pooled-QC
intensity, requiring the frozen minimum QC count. For each sample, Euclidean
distance is sqrt(sum of squared differences) on its observed retained coordinates
with available QC medians. Report the number of such coordinates; different
counts are not directly comparable. Too few coordinates gives null distance and
`distance-unavailable`; distance strictly greater than the frozen threshold gives
`qc-distance-outlier`. Keep flagged samples in every table and report. Medians
use all observed normalized intensities including zero. Retained count and each
reason count are explicit; one row can contribute several reasons.

The two frozen groups are batch-confounded if their sets of study batches have
no overlap. Always flag this; do not infer that an unflagged design has no other
confounding. This pack performs no downstream contrast. Failure to report the
flag, silently dropping a sample, or hiding a feature/reason refuses admission.

## 05-handoff: bounded claims and independent review

Accepted input: `report`, evidence documents and their sources by path plus hash;
output `metab-result-v1`. Call
`python3 scripts/validate_metabolomics_feature_qc_pack.py BUNDLE` with exactly one
bundle argument. Success emits JSON to stdout, exit 0; labelled refusals including
missing/extra/unknown arguments emit JSON to stderr, exit 2. `--help` emits plain
usage to stdout, exit 0. There is no output-path option and no file write.
A second concurrent call observes the same immutable inputs or refuses changed
ones; termination leaves no output file or partial record. The coordinator must
save outputs separately using its existing atomic artifact/provenance protocol.

Claims have descriptive/associational kind and an existing claim status:
planned/supported/replicated/suggestive/conflicting/unsupported/withdrawn/unavailable.
No evidence requires unavailable. ANY cited unavailable kind or result forces
unavailable, even mixed with observed evidence and regardless of nonpositive
status. Unavailable text cannot assert supported/replicated/suggestive/significan*.
Positive statuses cannot cite computed/numerical agreement or review approval,
checked in both kind and result. Replicated is always refused: one synthetic
fixture cannot establish two independent studies. Labels never substitute for
evidence and origin aliases are refused by path OR bytes hash.

The conservative case-insensitive English whole-word prefix gate uses `\w*`:
**caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*,
recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*,
drive/drives/driv*, induc***. It additionally refuses biomarker*, pathway*,
identif*, compound identity, truth and physical validity. It applies to all claim
texts and the headline regardless of kind/status. It is incomplete: paraphrases,
other languages and compound names require independent source and method review.
Association is never causality, numerical agreement never physical or clinical
validity, and review approval never truth. Failed controls/negative results are
preserved; absent source records are unavailable, never negative evidence.

Register these domain records as ordinary artifacts through `$science-provenance`,
with separate claim-register entries using the unchanged global contracts. Send
hash-bound inputs/outputs, plan/checkpoint, reference-use ledger, environment,
execution record, assumptions, exclusions, negative controls, dependencies,
conflicts, uncertainty, limitations and falsifiable next checks to `$science-review`.
Coordinator owns rigor and independent review; this pack always reports review
unavailable. Gates apply only before installation, restricted transfer, new hosts,
GPU/remote/heavy compute or interpretation-changing choices. This validator
performs none of those operations.
