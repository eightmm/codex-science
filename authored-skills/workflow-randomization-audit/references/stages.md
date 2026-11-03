# Randomization audit stages and local records

## Invocation and immutable identities

Use `python3 scripts/validate_randomization_audit_pack.py BUNDLE` or Python
`validate_randomization_audit_pack(path)`. A single positional bundle is accepted;
there is no output option. Success is JSON on stdout, exit 0. Refusal is JSON
with `status: refused` and labelled `finding` on stderr, exit 2. Missing, extra
or unknown arguments follow the same refusal route; help is plain stdout, exit 0.
`reference_computation(protocol, unit_table)` regenerates allocation and metrics
without file access. Both public entry points are CPU-only and standard-library-only.

The bundle file's parent is its pinned root. Every artifact identity is exactly
`path` plus lowercase SHA-256 `sha256` of the bytes parsed. Paths must be canonical
relative POSIX names without traversal, backslashes, colons or symlink components.
Walk the absolute root component by component through O_DIRECTORY/O_NOFOLLOW
directory descriptors; record every ancestor's device/inode. Open artifacts
relative to the pinned descriptor with lstat, O_NONBLOCK/O_NOFOLLOW, fstat identity
and regular-file checks, then bounded reads. Cache raw and parsed bytes once per
inode, including hardlink aliases. Final separate hash reads and full ancestor-chain
checks before and after those reads refuse input replacement. A transient root or
ancestor swap at open must also be refused. No input is reopened by absolute name.

## Limits and parsing

Module constants bound dimensions before work scales with them:
`MAX_BYTES` 64 MiB per file, `MAX_TOTAL_BYTES` 256 MiB across unique inodes,
`MAX_ARTIFACTS` 128 unique inodes, `MAX_JSON_VALUES` 4,000,000 bundle-wide,
`MAX_UNITS` 10,000, `MAX_ARMS` 8, `MAX_COVARIATES` 16, `MAX_STRATA` 8 named
stratum fields, `MAX_GROUPS` 128 observed stratum combinations, `MAX_METRICS`
60,000 scope/pair/covariate combinations, `MAX_RECORDS` 128 claims, evidence
records or references per list, `MAX_ITEMS` 100,000 entries per JSON container,
`MAX_STRING` 4,096 characters per key/string, `MAX_DEPTH` 32, and `MAX_NUMBER`
1e100 numeric magnitude. Ratio sum and block size cannot exceed MAX_UNITS.

Enforce remaining byte budget from descriptor size before reading a new inode.
Enforce the JSON allowance before parsing: 1 + comma count + count of nonempty
containers, using a non-consuming lookahead and streaming match iteration,
never allocating a match list. Deduct this conservative upper bound once per
parsed inode. Duplicate keys at any depth, non-object roots, malformed UTF-8,
NaN/Infinity, excessive numbers/nesting and wrong types are labelled refusals.
Strings used as map/set keys are checked before membership operations. Empty
lists are allowed only for declared optional evidence/claim lists and strata.

All declared integers are real int values, never bool, float or numeric string:
`schema_version` exactly 1; seed 0..2^64-1; ratio weights 1..MAX_UNITS; block size
1..MAX_UNITS; minimum_per_arm 2..MAX_UNITS; attempts 1..MAX_UNITS; binary covariates
0 or 1; reported counts match regenerated integer counts. There is no earlier
writer or stored record class for these new local shapes. No existing validation
bound, global schema, receipt or manifest payload is changed.

## Pack-local schemas

Every input object has exact fields, including `schema`, `schema_version: 1`
and `fixture: synthetic fixture`. Only synthetic fixtures are admitted. This
label is an admission declaration, not proof that arbitrary supplied data is synthetic.
Identity objects have only `path` and `sha256`.

| Schema | Fields beyond shared fields |
| --- | --- |
| randomization-audit-pack-v1 | stages in fixed order; protocol identity; frozen_protocol_sha256; frozen_at and allocation_read_at timestamps; allocation and report identities; evidence identity list |
| randomization-audit-protocol-v1 | units identity; arms; allocation_ratio integer list; method; block_size; strata name list; seed; algorithm; blinding; allocation_concealment; thresholds with smd and risk_difference; covariates name-to-continuous/binary map; minimum_per_arm; outcome_available_at |
| randomization-audit-units-v1 | rows with unique unit_id, available boolean, covariates map matching all frozen names and strata map matching all frozen names |
| randomization-audit-allocation-v1 | rows with unique unit_id, known arm, recorded_at timestamp; attempts integer and after_balance_seen boolean |
| randomization-audit-report-v1 | protocol_sha256; applied_strata; block_size; reproduced and exploratory booleans; counts; stratum_counts; balance metric list; balanced boolean; headline; claims |
| randomization-audit-evidence-v1 | records with unique id, kind, result, origin internal/external/independent/preregistered, source identity; sources may be raw artifacts |
| randomization-audit-result-v1 | emitted schema_version and fixture; status arithmetic-only; review unavailable; stages; protocol_sha256; inputs path/hash list; reproduced; finding; exploratory; computation; claims; limitations |

Each metric entry has scope, covariate, arms pair, metric smd/risk_difference,
value and flag. Scope is overall or stratum: followed by compact JSON encoding
of the ordered stratum value tuple. Claims have unique id, kind
(descriptive/associational), status, text, and support (evidence IDs). Statuses:
planned, supported, replicated, suggestive, conflicting, unsupported, withdrawn,
unavailable. These are local records, registered as ordinary artifacts; transfer
claims to the existing separate claim-register without extending it.

## 01-freeze: rule and table identity

Input: bundle plus protocol path/hash, with protocol fixing units path/hash.
Check frozen_protocol_sha256 equals the parsed protocol hash and frozen_at is
strictly before allocation_read_at and outcome_available_at, before allocation is opened. Timestamps are
ISO 8601 with explicit timezone. Output: admitted randomization-audit-protocol-v1
and immutable table identity. Existing tools: coordinator plan/checkpoint and
$science-provenance. Failure: rule-freeze, blinding-missing, random-procedure,
block-size or labelled structural refusal. Missing blinding is refused; an
explicit unblinded statement is allowed. Concealment is a required declaration,
not an attestation. A material rule change needs a new freeze and coordinator
decision; hashes cannot establish historical preregistration.

## 02-table-qc: complete synthetic units

Input: unchanged entry/protocol and frozen units identity, then allocation
identity. Output: admitted randomization-audit-units-v1 and
randomization-audit-allocation-v1. Use the pack validator, no external skill or
retrieval. All IDs are unique and identical across tables; covariates finite;
named strata complete; arms known; available true. Missing/null covariates and
missing/unavailable units cause unit-unavailable, never a balanced zero.
Every recorded_at is strictly before outcome_available_at: equality also fails
allocation-after-outcomes. Minimum counts apply overall and to every evaluated
stratum. Controls are checked before summary or claim gates.

## 03-reproduction: fixed pseudo-random arithmetic

Input: the same hashes and frozen rules. Output: generated allocation and
reference metrics from reference_computation, checked against recorded rows.
Algorithm stdlib-mt19937-fisher-yates-v1 creates random.Random, seeds with
seed(..., version=2), and uses only Random.random(). Fisher–Yates traverses
indices n-1 down to 1, swapping index i with floor(random()*(i+1)). This fixes
call order and avoids version-dependent shuffle/randrange implementations.
Record the executing Python version and code revision separately with provenance.

Arm order and ratio order are frozen. IDs and stratum tuples sort in Python
lexicographic order. One generator is shared across all sorted strata and blocks.
Simple means complete random allocation with fixed marginal counts: floor
(n*weight/sum), distribute remaining slots by descending integer remainder,
ties by frozen arm order, then shuffle the arm roster once. This restricted
simple route is not independent Bernoulli assignment; it permits less than one
unit of rounding deviation from each ideal marginal.

Permuted blocks require block_size divisible by ratio sum. Shuffle a fresh full
ratio roster for each contiguous ID block, including the last incomplete block;
use its prefix only. Full blocks must have exact frozen counts; a partial block
cannot exceed any full-block arm capacity. Stratified permuted blocks restart
blocks within each named stratum and use the same generator stream. Never drop
strata. Per-arm counts and deviations are checked with these frozen capacities,
not an after-the-fact threshold. Wrong capacities fail block-size; simple
marginal violations fail allocation-ratio; ignored reported strata fail strata-ignored.

Compare regenerated and recorded allocation exactly, per ID. A false claim of
reproduction fails allocation-not-reproduced. A correctly disclosed mismatch
returns reproduced false and finding allocation-not-reproduced; it cannot be
reported as success of reproduction. Multiple attempts or after_balance_seen
require exploratory true, otherwise rerandomization-unlabelled. Alternative
seeds must remain separate immutable draws and need new frozen rules; this
route does not search or silently retry.

## 04-summary: covariate controls

Input: unchanged identities, recorded allocation and randomization-audit-report-v1.
Output: counts, stratum_counts, balance, balanced and exact reproduction finding.
Compute metrics on the recorded assignment, including when mismatch is disclosed.
For each overall/stratum arm pair, signed continuous SMD is (mean A - mean B) /
sqrt((sample variance A + sample variance B)/2). Binary signed risk difference
is mean A - mean B. Compare absolute metric value strictly greater than the
frozen threshold to flag; equality is accepted. Means use math.fsum; variances
use statistics.variance. Cache per-arm covariate moments within each scope.
Refuse zero pooled variance (including constant binary pairs), nonfinite results
and counts below the frozen minimum. No significance test is computed.

Reported metrics and flags must agree, with relative tolerance 1e-12 and zero
absolute tolerance for numerical comparisons. Distinct near-zero numbers are
not ties. Report balanced false for any flag. Imbalance itself remains a
reported negative control, never a reason to rerandomize. Ignored/misreported
flags fail covariate-imbalance. Counts and count types must match exactly.
Synthetic hand controls: A baseline 0,2,4,6 and B 1,3,5,7 have means 3,4, sample
variances 20/3 each and SMD -sqrt(3/20); binary A 0,0,1,1 and B 0,1,1,1 give
risk difference -1/4. Repeated across two strata, overall SMD is -sqrt(7/40).

## Claim and evidence gate

Every status checks kind and text. The conservative English lexical check is
case-insensitive, uses whole-word prefix families, and is incomplete:
caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*,
recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*,
drive/drives/driv*, induc*. It also refuses unbiased, valid*, confirmatory,
truth and patient benefit*. Negations are also refused; independent review
must inspect unlisted paraphrases. Positive statuses are supported, replicated,
suggestive. Check record kind AND result for review/approv/comput/numer/agreement/
truth/physical/clinic wording before allowing positive support: non-evidence.
Replicated is always refused for this single synthetic bundle: claim-replication.

Empty support or ANY unavailable cited kind/result (case insensitive) requires unavailable, even
when mixed with available records: unavailable-evidence. This gate precedes
replication. Unavailable claims cannot say supported, replicated, suggestive or
significan*: unavailable-positive. Unknown references are unavailable-evidence.
External/independent/preregistered labels are checked against every internal
input/output identity by both path and hash; aliases fail evidence-independence.
Labels alone cannot establish independence. Association never establishes
causality; computed agreement never establishes physical or clinical validity;
absence is unavailable, never negative evidence; approval never establishes truth.
Preserve failed controls and negative results.

## 05-handoff: bounded claims and independent review

Input: every unchanged input path/hash plus result hash, failures, assumptions,
applicability limits, dependencies, rejected alternatives and separate claim-register.
Output: ordinary domain artifacts and coordinator-owned $science-review packet;
no self-approved review receipt. The coordinator owns rigor classification and
record/source/method review. Reuse the existing plan step shape (id, description,
status) and one checkpoint with all five ordered IDs. No engine or global keys
are added. A human gate applies only before installation, restricted transfer,
new hosts, GPU/remote/heavy compute, or interpretation-changing choices.

The validator writes no file, ref or record. Concurrent calls read independent
snapshots; a kill leaves unchanged inputs and possibly partial captured stdout.
The coordinator captures JSON atomically outside the bundle and registers its
hash separately. Checked-in fixtures and benchmark questions are static synthetic
software controls. A second validation leaves them unchanged. Their existence
and review never establish a real experiment's merits.
