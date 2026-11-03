# Synthetic stability reference contract

## Invocation and immutable identities

Use `python3 scripts/validate_stability_shelf_life_pack.py BUNDLE` with exactly one
pack JSON argument. It returns JSON on stdout with exit 0; labelled refusals are
JSON on stderr with exit 2, including missing, extra and unknown arguments.
`--help` prints plain usage on stdout with exit 0. There is no output option.
The Python entry points are `validate_stability_shelf_life_pack`,
`compute_stability` and `t_quantile` in
`src/codex_science/stability_shelf_life_pack.py`.

Every input identity is an object with exactly `path` and `sha256`; the latter is
64 lowercase hexadecimal characters hashing the bytes actually parsed. Artifact
paths are canonical relative paths within the pack's containing directory; no
absolute paths, parent traversal, backslashes, colons or symlinked components.
Open all ancestors from the filesystem root with directory descriptors and
no-follow flags; retain every device/inode pair. Open artifacts relative to the
pinned directory using nonblocking no-follow descriptors, compare lstat/fstat
identities and regular-file signatures, then bound each read. Recheck all input
hashes and the whole ancestor identity chain before success. Hardlink aliases
share raw bytes, parsing and budgets by device/inode. No validator writes occur,
so repeated or concurrent calls and interrupted calls leave inputs unchanged.
A final rehash necessarily rereads each distinct inode once, without reparsing.

## Limits before work

The named constants in the module are part of this pack's admission contract:
MAX_BYTES 64 MiB per artifact; MAX_TOTAL_BYTES 256 MiB across distinct inodes;
MAX_JSON_VALUES 4,000,000 across parsed artifacts; MAX_ARTIFACTS 256 referenced
paths; MAX_ROWS 10,000 measurements; MAX_BATCHES 128; MAX_TIME_POINTS 512;
MAX_RECORDS 128 evidence descriptors, aggregate evidence records, claims and
support IDs; MAX_ITEMS 20,000 entries per JSON container; MAX_TEXT 4,096
characters per string; MAX_DEPTH 32; MAX_NUMBER absolute JSON magnitude ten to
the power 100; MAX_MEASUREMENT absolute attribute magnitude ten to the power 12;
MAX_TIME one million; MAX_EXTRAPOLATION 10 observed-duration multiples.
BETA_ITERATIONS is 1,000 and SOLVER_ITERATIONS is 100; no unbounded solver runs.

Enforce list limits immediately after parsing, before indexing, set building or
regression. Enforce raw budgets from fstat before reads. Before JSON parsing,
count an upper bound of one plus commas plus nonempty opening containers using
a streaming match iterator without allocating a match list. Conservative counts
can overestimate for strings. Reject duplicate keys at any depth, invalid UTF-8,
NaN, Infinity, huge numbers, non-object roots and excess nesting with labelled
ValueError. Boolean and float values never satisfy integer fields. A JSON string
is checked for length before use as a key. Every refusal preserves the input.

## 01-rule-freeze

Input: proposed protocol at `protocol.json` plus SHA-256; no results read yet.
Use this pack's protocol checks, the existing coordinator checkpoint and
`$science-provenance`. Output: `stability-shelf-life-protocol-v1`, then
`stability-shelf-life-pack-v1` binding that hash in `frozen_protocol_sha256` and
asserting `frozen_before_results_read` true. A declaration cannot prove timing.

Freeze measured attribute, units, time unit, storage condition, numeric
specification and lower or upper direction, ordered unique batch IDs and time
points beginning at zero, model `linear-in-time`, poolability rule
`slope-then-intercept-else-individual`, significance alpha strictly between zero
and one, confidence 0.95, extrapolation multiple from 1 through 10 inclusive,
minimum batches at least 3 and minimum time points at least 3. Example minima
are 3 and 4. No rule or specification selection from outcomes without an
exploratory label; no retrospective historical-freeze claim. A different model,
direction, batch set or schedule requires a separate protocol and human
interpretation decision. Reversible offline steps require no additional gate.

## 02-data-qc

Input: `data.json` path plus SHA-256 bound by the pack.
Use this pack's QC; output: admitted `stability-shelf-life-data-v1`, with failed
controls retained in the coordinator's execution log if admission refuses.
Each batch/time pair identifies one measured result; time must increase within
each batch, be nonnegative, include zero and exactly match the frozen grid.
Units match the protocol, results are finite, and each frozen minimum is met.
A censored row carries null result, true censored flag and numeric nonnegative
quantification limit. An uncensored row has a number, false flag and null limit.
Censored-as-zero refuses `below-quantification-zero`. Correct censoring is
preserved and stops OLS with `censored-fit-unavailable`; no uncensored subset is
silently fitted. Missing baseline, small batches/time counts, duplicates and
mixed units have distinct refusal codes. No retry invents measurements.

## 03-regression

Inputs: admitted protocol/data path-plus-hash identities and immutable report.
Call `compute_stability` via the validator CLI. Output: the computation object
inside `stability-shelf-life-result-v1`, compared with the report. Zero time
variance, zero residual variance, empty data or insufficient n refuses rather
than returning significance. Per-batch fits cache centered sums and n.

For each batch, let xbar and ybar be means, Sxx the sum of squared centered
times and Sxy the sum of centered time times centered result. Slope is Sxy/Sxx;
intercept is ybar minus slope times xbar; SSE is the sum of squared centered
residuals; residual df is n minus 2 and s squared is SSE/df. Use math.fsum.
Assume independent, homoscedastic normal residuals and a linear mean in time;
none of those assumptions is established by a small synthetic fixture.

With k batches and total N, full separate-line SSE has N minus 2k residual df.
The common-slope, separate-intercept model has slope equal to the sum of batch
Sxx times slope divided by total Sxx. Its SSE is full SSE plus the sum of batch
Sxx times squared deviations from the common slope. The slope F statistic is
the difference in those SSEs divided by k minus 1, divided by full SSE over
N minus 2k. Reject equality if its survival probability is less than frozen
alpha. On rejection, select individual fits and report intercept as
`not-tested-after-slope-rejection`.

Otherwise fit a single pooled line. Test intercept equality using the pooled
SSE minus common-slope SSE, divided by k minus 1, divided by common-slope SSE
over N minus k minus 1. Pool only when this second survival probability is at
least alpha. Equality with alpha permits pooling. Rejection chooses individual
fits; this reference does not select an intermediate common-slope model.
Poolability requires the tests even if a report calls its fits pooled.

For a lower specification, the pointwise bound is the fitted mean minus the
95th Student t percentile times s times the square root of one over n plus
squared distance from xbar over Sxx. For an upper specification, add instead.
There is no extra prediction variance term and no two-sided percentile.
The selected fit's own residual df supplies its t percentile. Confidence is
pointwise, with no simultaneous or multiplicity claim across time or batches.

The stdlib t approach evaluates a regularized incomplete beta function with
log-gamma scaling, symmetry and a bounded continued fraction. For positive t,
CDF is one minus half the regularized beta at df divided by df plus t squared,
with beta parameters df/2 and 1/2. Bracket by doubling and invert by bounded
bisection. For F with d1 and d2 df, the survival probability is regularized beta
at d2 divided by d2 plus d1 times F, parameters d2/2 and d1/2. Unconverged or
nonfinite arithmetic is a labelled refusal. The numerical methods and formula
choices are implementation inferences from these primary mathematical sources:
NIST t distribution https://itl.nist.gov/div898/handbook/eda/section3/eda3664.htm
and t critical values https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm;
the R stats F distribution manual gives the incomplete-beta identity at
https://www.stat.ethz.ch/R-manual/R-devel/library/stats/html/Fdist.html .
These sources establish formulas, not product or regulatory validity.

Search from zero to frozen multiple times the observed duration. The signed
safe margin is linear minus a positive square-root norm, hence concave.
If already outside at zero, crossing is zero. If both endpoints are positive,
no interior crossing is possible. Otherwise bisection finds the first crossing;
compare signs explicitly without multiplying potentially subnormal margins.
Use the earliest crossing among selected individual fits. If none crosses,
return exactly `not-reached-within-observed-range`; also return maximum_time,
which may extend beyond observation under the frozen multiple. That string
never asserts observations beyond the actual last time point. No uncapped
extrapolation, prediction bound or two-sided bound is admitted.

## 04-summary

Input: report identity and computation; output: validated
`stability-shelf-life-report-v1` and returned `stability-shelf-life-result-v1`.
Check reported pooling, evaluation horizon, n, per-selected-fit residual df and
earliest crossing against recomputation. Reported n/df must be real integers.
A changed specification requires exploratory true and recomputation under the
new limit while retaining the original protocol/hash. Any unsupported change
gets a separate, explicitly exploratory run instead of rewriting the freeze.
Preserve failed controls and negative results; numerical agreement is arithmetic
only. The validator's status is arithmetic-only and review is unavailable.

## 05-handoff and claim gates

Input: all path-plus-hash identities, existing execution logs and claim register.
Use `$science-provenance` to register domain records as ordinary artifacts;
use separate existing claim-register entries for adjudication. Keep the same
checkpoint and ordered plan throughout. Coordinator alone classifies rigor and
requests independent `$science-review` source, record and method checks; review
approval is never truth. No pack output claims reviewed status.

Claim fields are id, kind, status, text and evidence IDs. Only descriptive and
associational kinds are admitted. Positive statuses supported, suggestive and
replicated cannot cite review approval or computed/numerical records; both
record kind and result are checked, regardless of the claim kind label.
An empty evidence list requires unavailable. A citation with kind or result
unavailable requires unavailable for every other status, including mixed lists.
Unavailable text additionally refuses supported, replicated, suggestive and
words beginning significan. Replicated is always refused for this single
synthetic-fixture pack, even for declared observed sources.

The conservative English lexical guard matches case-insensitive whole-word
prefix families: caus*, mechanis*, therap*, clinic*, efficac*, effective*,
treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*, inhibit*, activat*,
regulat*, drive/drives/driv*, induc*. An asterisk means any continuation of word
characters. This is incomplete for unlisted paraphrases and includes negations.
It additionally refuses truth, shelf life (joined, spaced or hyphenated), words
beginning expir, product quality or product safety, physical validity and words
beginning patient benefit; spaces or hyphens separate those phrase words.
The same guard applies to report headlines and claims at all statuses.
Evidence kind/result checks conservatively search review, approv, comput,
numer, agreement, truth, physical and clinic even within longer labels.
External, independent and preregistered origins must have both source path and
hash distinct from every study artifact; labels cannot establish independence.
Missing evidence is unavailable, never a negative observation.

Stop on missing essential input or any labelled refusal. Human gates occur only
before installation, restricted transfer, new hosts, GPU/remote/heavy compute,
or interpretation-changing choices. None is needed for the offline fixture.

## Pack-local schemas

All document fields below are exact: unknown or missing keys refuse. Each input
has schema set to its listed name and fixture set to synthetic fixture.
No schema_version integer is used; the version is part of the schema name.

- stability-shelf-life-pack-v1: stages, protocol, frozen_protocol_sha256,
  frozen_before_results_read, data, report, evidence. The three named input
  descriptors and evidence list entries are path/hash objects. stages must be
  the five ordered IDs; the freeze flag is boolean.
- stability-shelf-life-protocol-v1: attribute, units, time_unit,
  specification_limit, direction, storage_condition, time_points, batches,
  model, poolability_rule, alpha, confidence_level, extrapolation_multiple,
  minimum_batches, minimum_time_points. Only the two minima are integers;
  the other numerical fields accept finite numbers, excluding bool.
- stability-shelf-life-data-v1: rows; each row is batch, time, result, units,
  censored, quantification_limit. Null is permitted only as described in QC.
- stability-shelf-life-report-v1: protocol_sha256, poolability_tested,
  selected_model, bound_sides, bound_type, specification_limit, exploratory,
  evaluation_time, summary, headline, claims. Flags are boolean. Summary is n,
  df and earliest_crossing; df maps the selected batch IDs or pooled to integers.
- stability-shelf-life-evidence-v1: records, each containing id, kind, result,
  origin and source path/hash. Origin is internal, external, independent or
  preregistered. IDs are unique; support references must resolve.
- stability-shelf-life-result-v1: status arithmetic-only, review unavailable,
  stages, exploratory, inputs path/hash list, computation, claims, limitations.
  Computation includes selected_model, poolability, per_batch, selected_fits,
  n, df, bound, t_quantiles, observed_duration, maximum_time, crossings and
  earliest_crossing. Fits contain n, df, slope, intercept, x_mean, sxx, sse,
  mse. F tests contain f, df1, df2, p. Computation integer fields are generated
  from admitted list counts, never coerced from supplied values.
- stability-shelf-life-expected-fixture-v1: computation, an exact deterministic
  fixture oracle checked by tests, plus schema and fixture.
- stability-shelf-life-negative-fixtures-v1: cases with id, code and changes;
  changes contain target, path key/index list and value. This fixture-only
  mutation format is exercised through the public API and CLI by
  tests/test_workflow_stab_pack.py, not a global runtime schema.

## Hand-derived fixture and acceptance

Three synthetic batches share times 0, 1, 2, 3 and intercept 10. Slopes are
minus 1, minus 1, minus 2. Add residuals 0.1, minus 0.1, minus 0.1, 0.1 to
each line. These residuals sum to zero and are orthogonal to time. Each fit has
n 4, df 2, xbar 1.5, Sxx 5, SSE 0.04 and MSE 0.02. Full SSE is 0.12;
common slope is minus 4/3; common SSE is 0.12 plus 10/3. Slope F is 250/3
on 2 and 6 df. Its survival probability is the cube of 6 divided by 6 plus
twice F, about 0.0000419593. Individual fits must be selected.

For df 2, the 95th t percentile is square root of 162/19. The lower-bound
crossing for batch-c against limit 4 solves 10 minus twice time minus that
t percentile times square root of 0.02 times the sum of 0.25 and squared
distance from 1.5 over 5, equal to 4. The earliest solution is approximately
2.83893068942765 within the frozen horizon 6. Changing batch-c to slope minus
1 pools all data with SSE 0.12 and df 10; then a batch intercept shift must
reject intercept equality and restore individual fits. No-crossing, zero-time,
upper-direction, horizon equality, correctly censored and degenerate cases
also have explicit tests. All seeded defects in negative-cases.json are tested
for their stated codes through both API and CLI and mutation-checked.
