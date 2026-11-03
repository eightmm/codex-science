# Frozen enzyme-kinetics stages

All checked-in data are synthetic fixtures. The only accepted model is
Michaelis-Menten; optional substrate-inhibition fitting was not selected.
The validator is a read-only arithmetic admission check, not a physical assay,
an execution engine or an independent reviewer. Its code lives in
`src/codex_science/enzyme_kinetics_pack.py`; its thin entry point is
`scripts/validate_enzyme_kinetics_pack.py`.

## Shared identities and execution

Every stage consumes canonical bundle-relative paths and SHA-256 hashes.
`noiseless.pack.json` and `noisy.pack.json` bind protocol, data, report and
evidence bytes. Run the CLI with exactly one such bundle argument; it snapshots
and parses each distinct inode once and re-reads it for final hash checks.
Hardlink aliases share the snapshot and parse allowance. All raw reads,
including final rechecks, count against the byte allowance. No output file,
reference, checkpoint or source record is written by the validator.

Open every directory component through a pinned parent descriptor with
nonblocking, directory and no-follow flags. Record every ancestor's device and
inode from the filesystem root through the bundle root and compare the entire
chain again at recheck. Open artifacts relative to these descriptors, check
lstat/fstat identity, regular-file type and size, then perform a bounded read.
Symlinks, special files, traversal, escaping paths, replacements and growth are
refusals. A changed artifact descriptor identity before reading is `input-file`; a hash
mismatch for otherwise stable bytes is `input-hash`; growth during reading or
a changed final identity is `input-changed`. These earlier identity refusals
must not be delayed until later hash or scientific gates.

Pin the repository revision and Python version in the coordinator's existing
run provenance. Use one coordinator checkpoint and the existing manifest
`plan` entries with `id`, `description` and `status`, copied from `plan.json`.
The local bundle lists ordered stage IDs but creates no checkpoint record.
Record material reference paths and hashes in the existing reference-use-ledger.
Register each domain record as an ordinary artifact, with separate existing
claim-register entries. No pack-local schema extends a global sidecar or receipt.

## 01-freeze

Input: synthetic `protocol.json` path plus hash. Output:
`enzyme-kinetics-protocol-v1`, bound by `frozen_protocol_sha256` in
`enzyme-kinetics-pack-v1`. Calls: $science-provenance for ordinary registration;
the validator's protocol checks enforce the freeze before it opens rate data.

Before outcomes, fix substrate identity, concentration unit uM, enzyme
concentration in uM or explicit null, time unit s, product unit uM, rate unit
uM/s, ordered unique positive substrate levels, minimum level count, model,
method, weighting, exclusions, window, starting Vmax/Km, tolerance and maximum
iterations. Only unweighted nonlinear Gauss-Newton and no exclusions are
accepted. Default fixture levels are 0.25, 0.5, 1, 2, 4 and 8 uM; minimum 6.
The general minimum is 4 distinct levels. Concentrations and start values are
positive between one trillionth and one million in the declared reference units.

The fixture freezes the initial 0 through 3 seconds of a 4-second measured
progress curve, the first 75 percent of its duration: at least 4 points,
R-squared at least 0.99 and substrate depletion at most 0.1. The supported
window always starts at zero, with positive stop at most one million seconds,
minimum points at least 3, R-squared between zero and one and maximum depletion
strictly positive and at most 0.2. Bounds are inclusive unless stated otherwise.
Freeze starts Vmax 0.03 uM/s and Km 1.5 uM, relative log-step tolerance one ten
billionth and maximum 100 iterations; allowed tolerance is one trillionth
through one ten thousandth. The bundle declares freeze-before-rates true and
timezone-aware `frozen_at` strictly earlier than `rates_read_at`.

Failure: `protocol-freeze` precedes data availability checks; invalid units,
model, weighting, method or exclusions retain their labelled refusals. Hashes
and timestamps cannot prove historical freezing. Human gate: only a material
interpretation-changing choice; no routine stage approval. A correction gets a
new immutable bundle and retains the failed protocol and finding.

## 02-identity-qc

Input: frozen protocol identity plus `noiseless.data.json` or `noisy.data.json`
identity from the bundle. Output: admitted `enzyme-kinetics-data-v1` and the
rate rows subsequently embedded in `enzyme-kinetics-report-v1`. Calls:
`reference_computation` in the reference module and $science-provenance.

Enforce exactly the frozen ordered level range, unique curve IDs, positive
substrate concentrations and matching units and enzyme value. Each curve has
paired finite time/product arrays with strictly increasing time. Regress product
on time only within the frozen inclusive endpoints, which must both be present.
Reject insufficient points, zero time or product variance, nonpositive slope,
failed minimum R-squared, or declared rate differing from recomputation by more
than relative one billionth or absolute one trillionth. Points outside the
frozen window remain in the input; they never contribute to its rate.

Depletion is the maximum product increase from the window baseline divided by
the initial substrate level; refuse above the frozen fraction. Zero-variance
rates across levels are degenerate rather than an apparently precise fit.
Failure: preserve raw curves and the named QC finding, with no silent repair,
window extension or exclusion. Human gate: none for valid offline fixtures;
missing essential data stops the run rather than implying negative evidence.

## 03-fit

Input: admitted data and frozen protocol identities. Output:
`enzyme-kinetics-report-v1`, with full recomputation in
`enzyme-kinetics-result-v1`. Calls: the reference module and the one-bundle CLI;
no external fitter, installation or compute service is called.

Fit rates to Vmax times substrate divided by Km plus substrate. Use unweighted
least squares, Gauss-Newton in log parameters, frozen positive starting values
and a bounded halving line search. Stop at frozen log-step tolerance or its
stationary-gradient fallback; preserve the convergence flag and iteration count.
Refuse rank-deficient Jacobians. Covariance uses the inverse Jacobian normal
matrix with residual variance SSE divided by n minus 2. Transform covariance
back to natural parameters and propagate it to kcat and kcat/Km with enzyme
treated as fixed and known. kcat is Vmax divided by enzyme concentration.
These asymptotic standard errors are conditional model arithmetic, without
enzyme measurement uncertainty or a physical validity guarantee.

Bracket Km only when highest substrate is at least twice fitted Km and lowest
is at most half fitted Km; equality is accepted. Otherwise retain last iterates,
set reliability to unreliable and withhold parameter estimates and their errors.
Non-convergence likewise withholds estimates; specifically refuse a reported
Vmax. Missing enzyme value requires null kcat and efficiency and their errors,
while otherwise usable Vmax/Km can remain. Residual diagnostics count sign
changes explicitly, ignoring residual magnitude at most one ten billionth of
the maximum rate; nonzero residuals with fewer than 2 sign changes set the flag.
The flag is retained for review rather than treated as proof of model adequacy.

Failure: `primary-fit` refuses Lineweaver-Burk as primary fit;
`km-unreliable`, `fit-nonconverged`, `enzyme-missing`, `standard-errors` and
`unit-mismatch` are distinct report refusals before generic report matching.
Human gate: a model or interpretation change. An unlabeled post-outcome change
is `post-outcome-model`; an exploratory change still needs a separate frozen
bundle and this reference cannot fit substrate inhibition. No automatic method
switch, restart or result-dependent exclusion is allowed.

## 04-summary

Input: all frozen identities plus the supplied report identity. Output:
`enzyme-kinetics-result-v1` on stdout and a coordinator-owned bounded summary
registered as an ordinary artifact. Calls: CLI report comparison and
$science-provenance. No separate summary schema is invented.

Require all report fields, both model and method consistency, units, covariance,
residuals, convergence, reliability, rates, exclusions and all four standard-error
fields. Recomputed numerical values must match within relative one ten millionth
or absolute one ten billionth. Declared integers must be real integers, not
booleans, decimal floats or numeric strings. Preserve failures, nulls and negative
results. Invalid report content is refused rather than replaced by favorable
reference output. Human gate: none for routine summary; material interpretation
changes go back to the coordinator with the original evidence retained.

## 05-handoff

Input: result identity plus every evidence path/hash and source origin. Output:
ordinary `enzyme-kinetics-evidence-v1` artifacts and separate existing
claim-register entries, plus the coordinator's independent review packet.
Calls: $science-provenance and $science-review. The local claim rows in the pack
do not replace or extend the global claim-register schema. Rigor classification,
review mode, reviewer independence and any final acceptance remain coordinator
responsibilities. Review is always unavailable in the pack's result.

The coordinator retains normalized assumptions, control comparisons, failed and
negative results, unavailable sources, shared synthetic dependencies, conflicts,
uncertainty, exclusions, rejected alternatives, applicability limits and the
smallest falsifiable next arithmetic check. Human gates are limited to
installation, restricted transfers, new hosts, GPU/remote/heavy compute or a
material interpretation-changing choice; the offline fixture route needs none.
No transfer or new execution authority is created by this handoff.

## Claim boundaries

Association is never causality; computed or numerical agreement is never
physical or clinical validity; absence of a record is unavailable, never negative
evidence; review approval is never truth. Failed controls and negative results
are retained. Labels do not establish independence: an external, independent or
preregistered identity must differ in both path and hash from the study's own
inputs, outputs and bundle identity.

Check claim kind, status, text and support types before set membership. Only
descriptive or associational kinds are permitted. The conservative English
lexical gate is case-insensitive, matches whole words and extends these prefix
families to word-character suffixes: caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*.
Additional refusals cover truth, physical validity separated by whitespace or a
hyphen, diagnos*, patient* and drug*. This gate is incomplete and also refuses
negations; it cannot establish semantic safety or scientific validity.

An empty support list requires unavailable status. Any unavailable evidence kind
or result requires unavailable status, alone or mixed with observed citations,
for every other claim status. Unavailable text also refuses supported, replicated,
suggestive and significan* wording. Positive statuses supported, replicated and
suggestive are refused when either evidence kind or result contains review,
approv, comput, numer, agreement, truth, physical or clinic. Those evidence
refusals precede the replication and synthetic-only gates, keeping findings
distinct. Replicated is always refused: this single synthetic fixture cannot
establish independent studies. All other positive scientific statuses are also
refused for synthetic fixtures, regardless of evidence labels.

## Pack-local schemas

All records have `schema`, real integer `schema_version` 1 and `fixture` true.
Unknown or omitted fields are refused in validated input records. Identity
objects have exactly `path` and `sha256`; claim support additionally has `origin`
chosen from study, external, independent or preregistered. No global payload key
or schema is added. The two fixture descriptors below are repository acceptance
metadata consumed by tests, not additional CLI-admitted input record classes.

- `enzyme-kinetics-pack-v1`: `stages`, `inputs`, `frozen_protocol_sha256`,
  `freeze_before_rates`, `frozen_at`, `rates_read_at`, `study_outputs`, `claims`.
  Inputs contain protocol, data and report identities. Claim rows contain
  `id`, `kind`, `status`, `text`, `support`. Accepted statuses are planned,
  supported, replicated, suggestive, conflicting, unsupported, withdrawn and
  unavailable, subject to the stricter synthetic evidence gates above.
- `enzyme-kinetics-protocol-v1`: `substrate`, `concentration_unit`,
  `enzyme_concentration`, `enzyme_unit`, `time_unit`, `product_unit`, `rate_unit`,
  `model`, `method`, `weighting`, `exclusion_rule`, `substrate_levels`,
  `min_levels`, `window`, `start`, `tolerance`, `max_iterations`. Window fields
  are start, stop, min_points, min_r_squared and max_depletion_fraction;
  start values contain Vmax and Km.
- `enzyme-kinetics-data-v1`: `concentration_unit`, `enzyme_concentration`,
  `enzyme_unit`, `time_unit`, `product_unit`, `rate_unit`, `curves`. Each curve
  has id, substrate, time, product, rate and rate_window with start and stop.
- `enzyme-kinetics-report-v1`: `model`, `method`, `weighting`, `exploratory`,
  `calculation`. The calculation contains rates, converged, iterations,
  last_iterate, parameters, standard_errors, covariance_Vmax_Km, units,
  reliability, bracketed, sse, df, residuals, residual_pattern and excluded_ids.
  Parameter/error/unit maps have Vmax, Km, kcat and kcat/Km; last_iterate has
  Vmax and Km; residual_pattern has sign_changes and flag. Computed rate rows
  have id, substrate, rate, r_squared, depletion_fraction and integer n.
- `enzyme-kinetics-evidence-v1`: `kind` and `result`, both bounded text.
- `enzyme-kinetics-result-v1`: `stages`, `evidence_level`, `review`,
  `protocol_sha256`, `calculation`, `claims`, `input_identities`, `limitations`.
  evidence_level is synthetic-arithmetic-only; review is unavailable.
- `enzyme-kinetics-expected-fixture-v1`: `known_parameters` and `expected`,
  with noiseless/noisy parameters, standard_errors and sse. Tests independently
  check hand-derived rates, known parameters and Jacobian errors.
- `enzyme-kinetics-negative-fixture-v1`: `cases`, each with id, finding, target
  and field; every case has its own immutable negative bundle and API/CLI test.

## Limits

Bounds are enforced before work scaling with the corresponding dimension.
JSON decoding refuses duplicate nested keys, non-object roots, non-finite or
huge numbers, excessive nesting and malformed types with labelled ValueErrors.
Preparse JSON allowance counts one root, commas and nonempty containers through
an iterator with a non-consuming lookahead; it never builds a match list.

| Constant | Default bound |
| --- | --- |
| MAX_BYTES | 64 MiB per raw input |
| MAX_TOTAL_BYTES | 256 MiB across initial reads and final hash rereads |
| MAX_JSON_VALUES | 4,000,000 estimated values across distinct parsed inodes |
| MAX_ARTIFACTS | 128 distinct artifact paths |
| MAX_ROWS | 128 substrate levels or curves |
| MAX_CURVE_POINTS | 512 points per curve array |
| MAX_ITERATIONS | 200 frozen fit iterations |
| MAX_BACKTRACK | 24 halving trials per fit iteration |
| MAX_CLAIMS | 100 claim rows |
| MAX_SUPPORT | 100 identities per claim or study-output list |
| MAX_ITEMS | 20,000 fields or items per JSON container |
| MAX_TEXT | 4,096 characters per text value or object key |
| MAX_DEPTH | 32 JSON nesting levels |
| MAX_NUMBER | Numeric magnitude at most ten to the power 100 |

The code additionally bounds numeric domain fields as stated above; these are
pack-local synthetic record rules, not changed validation of stored global
records. Integer fields include every schema_version, min_levels,
max_iterations, window min_points, calculation iterations/df, rate n and
residual sign_changes. Null parameters remain null, never zero or negative
evidence. All list count checks precede per-item loops and set construction.

## Acceptance and interruption

`benchmarks/workflow-enzyme-kinetics/tasks.json` freezes noiseless, noisy and
seeded-refusal questions with CPU/memory budgets and no network or GPU.
`tests/test_workflow_kin_pack.py` covers hand arithmetic, all 14 planted defects,
integer types, counts, JSON, file limits, race refusals, CLI argument errors and
claim gates. L4 means synthetic software acceptance only. References and tests
cannot establish measured enzyme behavior or independent review.

Concurrent validator calls keep independent descriptors and caches and write
nothing. Killing either call leaves the original bundle and all other calls
unchanged; it may leave partial captured stdout/stderr outside the validator.
The coordinator must treat incomplete output as unavailable and preserve failed
controls. It must not overwrite immutable inputs while preparing a correction.
