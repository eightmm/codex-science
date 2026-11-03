# Diagnostic accuracy: fixed stages and record contracts

## Invocation and identities

The bundle is a JSON file whose parent directory is the bundle root. All named
artifacts use canonical relative POSIX `path` plus the lowercase SHA-256 of the
exact UTF-8 bytes parsed. No absolute paths, traversal, backslashes, symlinked
components, directories, devices or FIFOs are admitted. The root is pinned using
directory descriptors and O_DIRECTORY/O_NOFOLLOW; every ancestor is checked.
Files use lstat, O_NONBLOCK/O_NOFOLLOW, fstat, a bounded read and a metadata/hash
comparison. Parse each input once and cache it; a separate final read rechecks
all hashes and identities and reopens the root without following links.
The visible root identity is checked last, after the final artifact hash reads,
so a replacement during those reads is also refused.

From the repository root:

```sh
python3 scripts/validate_diagnostic_accuracy_pack.py examples/workflow-diagnostic-accuracy/pack.json
```

The single positional argument is `bundle`; there is no output option. Success
prints JSON to stdout, exit 0. Refusal prints JSON with `status: refused` and a
labelled `finding` to stderr, exit 2; no traceback or partial result is emitted.
The public Python entry points are `validate_diagnostic_accuracy_pack(path)` and
`reference_computation(protocol, case_table)`. Both are read-only, CPU-only and
standard-library-only. No retrieval, installation or remote execution is called.

## Limits

Before any work scaling with a dimension, enforce named module limits:
`MAX_BYTES = 64 * 1024 * 1024` per file, `MAX_DEPTH = 64` container nesting,
`MAX_TOTAL_BYTES = 128 * 1024 * 1024` admitted bytes across at most
`MAX_ARTIFACTS = 256` unique inputs (including the entry bundle),
`MAX_ROWS = 10000` combined subjects, `MAX_DRAWS = 2000`, `MAX_CLAIMS = 100`,
`MAX_SUPPORT = 100` per claim or study-output list, `MAX_TEXT = 4096` characters
per string/key, `MAX_ITEMS = 20000` entries per JSON container and
`MAX_NODES = 200000` total JSON values. At most two predictive-value entries are
accepted, one each for PPV and NPV. Bound integer and floating magnitudes by
`MAX_NUMBER = 1e100` before computation; reject booleans as numbers, NaN,
Infinity, huge JSON integers, duplicate keys at any depth, non-object roots,
malformed UTF-8 and excess nesting with labelled ValueError refusals.
Check the unique-artifact count and remaining total byte budget before opening
and reading each new file; final cached-identity reads do not consume it again.

These bounds are new pack-local admission rules; no earlier stored record class
or runtime writer exists for this pack. Every integer field is a real integer:
all `schema_version` values equal 1; `minimum_cases`/`minimum_controls` are in
1..MAX_ROWS; `draws` is in 1..MAX_DRAWS; `seed` is in signed 64-bit range; and
`reference_label` is 0 or 1. Numeric strings, booleans and float spellings such as
1729.0 do not substitute for integers. JSON field names and all values used as
map/set keys are validated as strings before membership checks.

## Pack-local schemas

All records have `schema`, integer `schema_version: 1` and boolean `fixture`.
Every checked-in example sets `fixture: true` and is synthetic. Real supplied
records may set it false; this does not attest source accuracy. Unknown or
missing fields are refused. These schemas are ordinary artifacts; no existing
global schema, checkpoint, claim-register, manifest or receipt is extended.

| Schema | Required content beyond shared fields |
| --- | --- |
| `diagnostic-accuracy-pack-v1` | Exact ordered `stages`; `inputs` containing `protocol` and `cases` identities; `frozen_protocol_sha256`; boolean `freeze_before_labels`; timezone-aware `frozen_at` strictly earlier than `labels_read_at`; `study_outputs` evidence-record identities; `predictive_values`; `claims`. |
| `diagnostic-accuracy-protocol-v1` | Nonempty `index_test`, `reference_standard`, `target_condition`, `population`; `direction` higher/lower; `threshold`; integer `minimum_cases`/`minimum_controls`; `intervals`; `verification_rule: all-subjects`; boolean `incorporates_index_test: false`; boolean `unblinded_reference_disclosed`. |
| `diagnostic-accuracy-cases-v1` | Nonempty bounded `rows`; each has unique `subject_id`, finite `score`, integer `reference_label` 0/1, boolean `reference_applied`, boolean `blinded`, and `split` evaluation/training. Missing labels are unavailable and refused, never recoded. |
| `diagnostic-accuracy-evidence-v1` | Nonempty `kind` and `result`. Positive support requires `kind: statistical-evidence`, `result: held-out-discrimination`; review approval and computed agreement cannot substitute. |
| `diagnostic-accuracy-result-v1` | Ordered `stages`, `evidence_level: statistical-only`, `review: unavailable`, `protocol_sha256`, immutable `input_identities`, `metrics`, `predictive_values`, bounded `claims` and `limitations`. The result is an emitted artifact schema, not an input-validation route. |

`threshold` has exactly `method`, `chosen_on`, `value`. Fixed route: `method:
fixed`, `chosen_on: before-outcomes`, finite numeric value. Training route:
`method: youden-training`, `chosen_on: training`, `value: null`; the frozen rule
maximizes sensitivity + specificity - 1 over distinct training scores and the
predict-none threshold, breaking ties by the smallest numeric threshold.
Evaluation labels cannot choose the method, direction, value or tie rule.

`intervals` has `binomial: wilson-95`, `auc:
stratified-bootstrap-percentile-95`, integer `draws`, integer `seed` and
`minimum_success_fraction` in [0.5, 1]. These are nominal 95% intervals, not
guarantees of coverage, especially for tiny or separated synthetic fixtures.

Each predictive entry has `metric: ppv|npv`, numeric `value` in [0,1], numeric
`assumed_prevalence` in [0,1] and equal `applied_prevalence`. Both metrics must
be present, unique, and recomputed from the admitted sensitivity/specificity at
that stated prevalence (relative tolerance 1e-10, absolute tolerance 1e-12).
These formulas assume transportable sensitivity/specificity and do not establish
that assumption. A different target prevalence requires a new recorded
calculation; it cannot be attached to the old predictive value.

Claims have unique `id`, `kind` descriptive/associational, `status`, nonempty
`text`, and `support` identities with an `origin` string. Statuses are planned,
supported, replicated, suggestive, conflicting, unsupported, withdrawn,
unavailable. Empty support requires unavailable. Replicated is refused for this
single-table route. A positive status is supported/suggestive (replicated is
checked and refused); it must cite statistical evidence. These local fields do
not extend the coordinator's existing separate claim-register schema.

## 01-protocol: freeze before reference labels

Input identities: entry bundle plus protocol path/hash. First load and validate
only the protocol; compare `frozen_protocol_sha256` to its actual parsed-byte
hash, require `freeze_before_labels: true` and strict timestamp order before
opening `cases`. The ordered protocol fixes index test/direction, reference,
target/population, threshold or training-only rule, denominators and intervals.
Output: admitted immutable `diagnostic-accuracy-protocol-v1` and its identity.
Use the existing coordinator plan/checkpoint and `$science-provenance`, with no
installation or external skill needed. Failure: `protocol-freeze`,
`evaluation-threshold`, `interval-method` or a labelled structural refusal.
No automated rewrite after outcomes; a material choice requires a new freeze
and coordinator interpretation gate. Declarations cannot prove historical timing.

## 02-cases: subject and split identity

Input identities: the same entry/protocol plus `cases` path/hash. Output:
admitted `diagnostic-accuracy-cases-v1`, retained subject/split identities and
any disclosed unblinded subjects. Check the row count before per-row work.
Every subject must occur once over the combined training/evaluation table.
Validate real integer reference labels, finite scores and boolean flags; never
impute absent reference results as negatives. Failure: `subject-leakage`,
`missing-reference`, `verification-bias` or a structural refusal. Preserve the
failed admission externally; the validator writes no replacement record.
No repeated human gate for admitted offline identity checks.

## 03-bias: refuse invalid accuracy claims

Input identities: frozen protocol and case table, unchanged from 01/02.
Output: admitted bias control state and retained limitations in
`diagnostic-accuracy-result-v1`. Require every supplied subject to have the
reference applied independently of score, `verification_rule: all-subjects`,
and no index-test incorporation. An omitted verification mechanism cannot be
proved from a table: independent source review must assess whether subjects
were excluded upstream. Every evaluation class must exist and meet its frozen
minimum; a training-selected threshold needs both training classes meeting those
same minima. Combined scores within each used split must be nonconstant;
constant-within-class but separated classes remain valid discrimination inputs.

Refuse `verification-bias`, `incorporation-bias`, `undefined-class`,
`insufficient-class`, `constant-scores`, or `unblinded-reference` when reference
reading was unblinded without disclosure. Disclosure retains IDs and a residual
bias limitation; it does not establish freedom from bias. Frozen threshold
selection cannot use evaluation outcomes. Preserve failed controls and all
negative results, never retry for a better score. A method-changing correction
requires coordinator resolution; routine controls require no human approval.

## 04-computation: descriptive accuracy

Input identities: the identical frozen protocol/cases and any output/evidence
identities. Output: `metrics` in `diagnostic-accuracy-result-v1`.
Use `reference_computation` in this pack; no third-party skill or dependency is
needed. The code sorts once per AUC calculation, scans exact equal-score groups,
and computes the Mann-Whitney statistic from integer pair counts with half
credit for ties. It never uses an approximate tie tolerance or quadratic pair
scan. Higher direction means score >= threshold; lower means score <= threshold.
The training rule caches class counts and scans sorted training scores once.

Report `confusion` tp/fp/tn/fn; evaluation `cases` and `controls` and total
`training_subjects`; `threshold`, `direction`; sensitivity tp/(tp+fn), specificity
tn/(tn+fp), each with Wilson intervals at z = Normal(0,1) quantile 0.975; and
`evaluation_prevalence`. AUC uses the stated direction. Independently resample
each reference class with replacement at its original size for every frozen
draw. Only a labelled `bootstrap-degenerate` constant-score draw is counted as
unsuccessful; unrelated errors propagate. Fail `bootstrap-success` if no draw
succeeds or the success fraction is below the frozen inclusive bound. Sort
successful AUCs and linearly interpolate the 2.5th/97.5th percentiles at
(n-1)*p. Retain successful and attempted counts and the fixed seed.

At prevalence p and sensitivity Se/specificity Sp, PPV = Se*p /
(Se*p + (1-Sp)*(1-p)); NPV = Sp*(1-p) / (Sp*(1-p) + (1-Se)*p). Use math.fsum
for floating sums. A zero predictive denominator is `predictive-undefined`,
missing or mismatched prevalence is `predictive-prevalence`, and a numerical
disagreement is `predictive-value`. Endpoints p=0 and p=1 are accepted only when
the requested ratio is defined. Preserve null/disappointing results; no control
or result may be selected for a favorable point estimate. Synthetic hand
controls give tp=tn=3, fp=fn=1, Se=Sp=3/4, AUC=15/16, PPV=NPV=3/4 at p=1/2.

## Claim boundaries

Every status checks claim kind and text. The conservative English lexical check
is case-insensitive, whole-word, and incomplete. It refuses prefix families
`caus*`, `mechanis*`, `therap*`, `clinic*`, `efficac*`, `effective*`, `treat*`,
`cure*`, `prevent*`, `recommend*`, `prescri*`, `bind*`, `affinit*`, `inhibit*`,
`activat*`, `regulat*`, `driv*` (including drive/drives), `induc*`; implementation
uses `\w*`. It also refuses `truth`, `screening utility`, `screening use`,
`physical validity` and `patient benefit*` with spaces/hyphens. It refuses these
even in negations. Review must inspect unlisted paraphrases. An unavailable
claim also cannot say supported, replicated, suggestive or significant
(`significan*`). Empty support cannot be negative evidence.

If any cited record has `kind` or `result` equal to `unavailable`, the claim must
be unavailable; every other status is refused as `unavailable-evidence`.
Available co-citations cannot override an unavailable record. This check also
precedes the single-table `claim-replication` refusal for replicated claims.

Every positive status checks cited evidence `kind` AND `result`; strings
containing review, approv, comput, numer, physical, clinic or truth are refused
as `non-evidence`. A statistical label cannot disguise a computed result.
An evidence identity declared external, independent or preregistered must differ
by both path and hash from every study input, entry bundle and declared study
output; copied aliases fail `evidence-independence`. This mechanical check
cannot establish genuine independence. Association is never causality,
computed agreement never physical/clinical validity, absence never negative
evidence, and approval never truth. Failed controls and negative results remain.

## 05-handoff: coordinator-owned independent review

Input identities: all unchanged source identities, the result plus negative
results, failures, assumptions, applicability and dependencies, and separate
existing claim-register entries. Output: ordinary domain artifacts registered
with `$science-provenance` and the existing `$science-review` packet, never a
self-approved receipt. Leave `review: unavailable`; the coordinator owns rigor,
source/record/method review and final acceptance. One checkpoint holds the five
ordered IDs; immutable path-plus-hash stage handoffs avoid duplicated run state.

Gates apply only to installation, restricted transfers, a new host, GPU/remote/
heavy compute or interpretation-changing choices; none is part of this offline
reference route. Read-only calls write no file/ref/record. Concurrent calls
compute independently; a kill leaves only possibly partial captured stdout,
never a changed bundle. The coordinator must capture any output atomically
outside the input bundle and register its hash separately. Failed runs preserve
their original immutable inputs; independent review approval is not truth.
