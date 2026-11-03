# Synthetic calibration stages and local records

Every example in `examples/workflow-calibration-lod/` is a synthetic fixture.
This contract describes offline arithmetic, not measured assay validation.

## Commands and handoffs

From the repository root:

```sh
python3 scripts/validate_calibration_lod_pack.py examples/workflow-calibration-lod/pack.json
```

One positional bundle argument is accepted. Success is result JSON on stdout
and exit 0. Every refusal, including missing, extra or unknown arguments, is
`{"status":"refused","finding":"CODE: reason"}` JSON on stderr and exit 2.
`--help` prints plain usage on stdout and exits 0. There is no output option.
The public Python entry points are `validate_calibration_lod_pack(path)` and
`reference_computation(protocol, data)` in `codex_science.calibration_lod_pack`.
The latter consumes already-decoded synthetic fixture records and writes nothing.

Each input identity is exactly `{path, sha256}`: a canonical relative path and
lowercase 64-digit SHA-256 of the bytes parsed. No absolute path, traversal,
backslash, symlink component, FIFO, device, directory or oversized file is
admitted. Root and every ancestor are pinned through directory descriptors,
identified by device/inode and rechecked as a chain. Artifacts are opened relative
to that root with no-follow/nonblocking flags, lstat/fstat identity checks and
bounded reads. Unique inodes are read and parsed once for the snapshot; final
hash rereads verify immutability, with hardlink aliases sharing that reread.
The validator writes no file, ref or record: concurrent calls and interruption
between reads leave supplied artifacts untouched. A concurrent writer causes
a labelled refusal when identity, metadata or final bytes differ.

## Pack-local schemas

All admitted records have `schema`, integer `schema_version: 1` and
`fixture: true`, and exactly the fields below. No existing global schema changes.
Examples provide complete concrete shapes; required fields cannot be omitted.

- **calibration-lod-pack-v1:** `stages`, `inputs` (protocol/data/report identities),
  `frozen_protocol_sha256`, boolean `freeze_before_responses`, timezone-aware
  `frozen_at` and `responses_read_at`, `study_outputs` (evidence identities),
  and `claims`. Each claim is `{id, kind, status, text, support}`. Each support
  identity adds `origin`: study, external, independent or preregistered.
- **calibration-lod-protocol-v1:** `analyte`, `concentration_unit`, `response_unit`,
  `model` (linear or weighted-linear), `weighting` (none, 1/x or 1/x^2),
  `intercept` (free or zero), `acceptance` with `percent_deviation` and
  `lowest_percent_deviation`, integer `min_levels` and `min_replicates`,
  `limit_rule` with `method`, integer `min_blanks`, `lod_k`, `loq_k`,
  `validity` with positive ordered `min` and `max`, and `exclusion_rule`
  (none or failed-back-calculation-once).
- **calibration-lod-data-v1:** `standards`, `blanks`, `unknowns` lists. Every row
  has `id`, `response`, `concentration_unit`, `response_unit`; standards also
  have `concentration`. All IDs are unique across all three lists. Replicate
  rows share a nominal level; distinct levels increase strictly in input order.
- **calibration-lod-report-v1:** `model`, `weighting`, `intercept`, boolean
  `exploratory`, ordered `acceptance_evidence` (back-calculated-deviations,
  replicate-counts, residuals), and the complete `calculation` described below.
  Weight changes without an exploratory label are refused first. Labelled changes
  still require a separate newly frozen bundle; this record preserves its freeze.
- **calibration-lod-evidence-v1:** text `kind` and `result`. Neither label alone
  is sufficient evidence. Computed and review-approval fixtures are negative controls.
- **calibration-lod-result-v1:** `stages`, `evidence_level` fixed to
  synthetic-arithmetic-only, `review` fixed to unavailable, `protocol_sha256`,
  `input_identities`, `calculation`, `claims`, `limitations`.
- **calibration-lod-expected-fixture-v1:** test-only fixture envelope with
  `calculation` and `hand_calculation`. Not accepted as a run record; tests check
  its numbers independently and compare its complete calculation to the validator.

The `calculation` contains `initial_fit`, `fit`, `excluded_ids`, `levels`,
`limits`, `unknowns` and `acceptance` (passed/failed). Each fit contains slope,
intercept, r_squared, residual_standard_error, integer n and df, and
back_calculated rows with id, concentration, percent_deviation, limit_percent,
boolean failed and residual. Levels contain concentration, integer n_initial
and n_retained. Limits contain method, integer blank_n, blank_mean, blank_sd,
lod and loq. Unknown rows contain id, status and concentration; out-of-range
and unavailable concentrations are JSON null. Below-loq values are arithmetic
back-calculations, never quantified concentration claims.

## Limits

Bounds are checked immediately after parsing lists and before per-item work.
Module constants are MAX_BYTES = 64 MiB per artifact, MAX_TOTAL_BYTES = 256 MiB
per unique snapshot, MAX_JSON_VALUES = 4,000,000 across unique parsed artifacts,
MAX_ARTIFACTS = 128 relative paths, MAX_ROWS = 10,000 per standard/blank/unknown
list, MAX_CLAIMS = 100, MAX_SUPPORT = 100 per output/support list,
MAX_ITEMS = 20,000 per JSON container, MAX_TEXT = 4096 characters,
MAX_DEPTH = 32 and MAX_NUMBER = 1e100 in absolute input magnitude.
Final hash checks read each unique artifact at most once more within its
per-file bound. The value allowance is conservatively checked before JSON
parsing by counting commas and nonempty containers without allocating matches.
Duplicate keys, invalid UTF-8, NaN/Infinity, non-object roots, excessive nesting,
huge numbers and wrong types are labelled refusals. Booleans never count as
numbers; declared integers never accept floats or numeric strings.

## 01-freeze

Input: `pack.json` plus path/hash for `protocol.json`, admitted and hashed before
opening `data.json`. Output: admitted calibration-lod-protocol-v1 identity and
the first existing manifest plan step. Calls: this pack's read-only validator
and the existing coordinator checkpoint. Freeze analyte, units, model, weights,
intercept, deviation criteria, minimum levels/replicates/blanks, limit rule,
range and exclusion before responses. Thresholds: minimum 3 levels, 2 replicates
per level and 3 blanks; deviations 0..100 percent, lowest threshold strictly
looser than the others. Frozen timestamp must precede first response read.
Failure: protocol-freeze or a labelled record/model/rule refusal; retain input
and failure. Human gate: only interpretation-changing choices or scope extensions.
Hashes and declared times cannot prove actual chronological precommitment.

## 02-identity-qc

Input: immutable calibration-lod-data-v1 path/hash and the frozen protocol.
Output: admitted identities, standard groups and QC findings in the result.
Calls: validator identity/QC checks. Controls: finite responses, positive ordered
nominal levels, unique IDs, exact frozen units on every row, sufficient blanks
and retained standard counts. Validity must lie within the standards. Unsupported
log models are refused; nonpositive concentrations are refused for all models,
including weighted models. Failure stops arithmetic; unavailable input never
becomes a negative result. No additional human gate for valid offline inputs.

## 03-fit-limits

Input: admitted protocol/data path/hash identities. Output: initial and final
fit plus detection/quantification fields in calibration-lod-result-v1; submitted
calibration-lod-report-v1 identity must match. Calls: reference_computation and
the read-only CLI. Use WLS with weights proportional to 1, 1/x or 1/x^2;
normalizing by the lowest x preserves the fit. Free intercept uses weighted
centered normal equations; a frozen zero intercept uses a one-parameter fit.
Slope must be finite and positive; concentrations and responses cannot be
degenerate, and underflowed weights are refused. Sums use math.fsum.

R-squared uses centered weighted response variation for every intercept choice
and is descriptive (it can be negative for a zero-intercept fit). Residual
standard error is the unweighted square root of sum of squared residuals divided
by n minus 2 for a free intercept or n minus 1 for zero. Back-calculated x is
(response - intercept)/slope; deviation is 100*(back-calculated - nominal)/nominal.
Flag absolute deviations strictly above the frozen threshold; equality passes.
The lowest nominal level uses the frozen looser threshold.

The one-pass exclusion rule removes exactly initial deviation failures, preserves
all originals, then refits once. No iterative pruning for R-squared is permitted.
Counts and validity support must survive exclusion. With rule none, failed
standards remain in the fit; final failed acceptance is preserved and unknown
quantification becomes unavailable. No silent data cleaning or favorable retries.

Both limit rules use sample SD of at least the frozen minimum blank responses;
zero SD is refused. For blank-mean, response thresholds are blank mean + k*SD,
then converted by (threshold - intercept)/slope. For calibration-slope, LOD is
3.3*SD/slope and LOQ is 10*SD/slope. Blank-mean requires 0 < lod_k < loq_k;
the slope rule fixes 3.3 and 10. Require 0 <= LOD < LOQ and LOQ within the
retained standard span and frozen validity. Never clamp an unsupported LOQ.
Out-of-range unknowns have status out-of-range and null concentration. Within
validity, values below LOQ get below-loq; other values get in-range only if
standards pass. Numerical overflow, zero variance and insufficient n refuse.
Human gate: any interpretation-changing replacement rule requires a new freeze.

## 04-summary

Input: protocol/data/report path/hash identities. Output: calibration-lod-result-v1
including per-level counts and all flags. Calls: CLI and `$science-provenance`.
Report equality uses relative tolerance 1e-9 and absolute tolerance 1e-10 for
floating results; counts, booleans, identities and categories match exactly.
R-squared-only acceptance, unfrozen exclusions, forced intercept, changed weights,
extrapolation and unsupported LOQ retain distinct finding codes before generic
report comparison. Preserve failed controls and negative acceptance; do not
rewrite supplied reports. No stage-specific permission prompt.

## 05-handoff

Input: immutable result, all input and ordinary evidence output identities plus
separate claim-register entries. Output: coordinator review packet, never a
self-reviewed pack. Calls: `$science-provenance` and coordinator `$science-review`;
the pack result keeps review unavailable. Share counts, exclusions, failures,
negative results, limitations, rejected alternatives and dependencies. Rigor
classification stays with the coordinator. New installations, restricted transfers,
new hosts, GPU/remote/heavy compute need separate authorization; none are called here.

## Claim boundaries

The conservative English lexical gate is case-insensitive, whole-word, with
prefix families using `\w*`: caus*, mechanis*, therap*, clinic*, efficac*,
effective*, treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*,
inhibit*, activat*, regulat*, drive/drives/driv*, induc*. Extra refusals cover
truth, physical validity (space or hyphen), diagnos* and patient*. This filter
is incomplete and refuses negations too; independent review is mandatory.
It checks claim text and kind, never trusts a descriptive label to sanitize text.

Empty support requires unavailable. Unavailable text additionally refuses
supported, replicated, suggestive and significan*. Any cited kind or result
unavailable requires unavailable status for every other status, even mixed with
available evidence. External, independent and preregistered identities must
not alias the study's inputs, output paths or hashes. Positive statuses check
both declared kind and result for review, approv, comput, numer, agreement,
truth, physical and clinic. Replicated is always refused for one synthetic
fixture; other positive scientific statuses are refused too. Boundary and
evidence refusals precede this final synthetic-evidence refusal.
Association is never causality; arithmetic is never physical or clinical
validity; absent records are unavailable; approval is never truth. No claim
about true concentration, clinical cut-offs, diagnostic accuracy, regulatory
validity or patient-level meaning is admitted.
