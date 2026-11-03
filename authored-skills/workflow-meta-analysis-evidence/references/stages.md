# Five-stage evidence synthesis contract

Every example is a labelled synthetic fixture. The validator consumes JSON only,
reads each artifact once into a hash-bound snapshot, and re-reads bytes only for
the final hash check. It writes nothing. Concurrency creates no shared state;
interruption leaves the input bundle unchanged. Hashes do not prove when a human
first saw results. Independently preserved protocol provenance is still required
for a preregistration claim, and independent review remains the coordinator's job.

## Stage 1: freeze

Accepted input: the question and eligibility supplied by the coordinator, before
opening extracted effects. Output `protocol.json`, `meta-analysis-protocol-v1`.
Use `$cx-literature-review` for population, eligibility, cutoff, study identity
and source bias. Freeze `question`, `eligibility`, `effect_measure`, `direction`,
`unit`, `model` (`fixed` or `random`), `min_studies` (integer >=2),
`i_squared_threshold` (0..100 percent), `tau_squared_threshold` (>=0), `subgroups`
(unique strings, possibly empty), and `frozen_before_extraction=true`. Include
population and cutoff in question/eligibility text. Hash all bytes before stage 2.
Human gate: only an interpretation-changing missing choice. No outcome-driven
model substitution is allowed; revise the protocol and label exploration.

## Stage 2: extraction

Input: immutable protocol path plus SHA-256. Output `studies.json`,
`meta-analysis-extraction-v1`, with `protocol_sha256`, `synthetic` and `studies`.
Each row has unique `study_id`, finite `effect`, positive `variance` or positive
`standard_error` (both must agree if provided), positive integer `n_exposed` and
`n_comparator`, `effect_measure`, `direction`, `unit`, `cohort_id`,
`independence_group`, nonempty unique `participant_ids`, `result` and `outputs`.
`outputs` is a list of immutable JSON source path-plus-hash references. Reuse
literature-review cohort and independence groups; never treat missing linkage as
independence. Identical participants, even across different cohort labels, count
once. Participant IDs must be consistently pseudonymized across the bundle and cover
both sample sizes exactly.

The complete extracted table, including excluded rows, is limited to 200 studies
(`MAX_STUDIES`). The validator checks this immediately after parsing the table,
before row validation, pooling or reported-number comparison. Larger tables are
refused as `MA_STUDY_LIMIT`. Do not split a table to evade the independence gate.

`result` is `recorded`, `negative`, `failed-control` or `unavailable`. A missing
record is unavailable, never no association. Retain failed controls and negative
results even when excluded. Do not fill missing variance or sample size.

## Stage 3: independence and comparability

Inputs: protocol and extraction paths plus hashes. Output `gate.json`,
`meta-analysis-gate-v1`. Fields: `included_studies` (unique IDs), `exclusions`
(objects with `study_id`, nonempty `reason`, `timing`, `exploratory`), `subgroups`
(objects with `name`, `timing`, `exploratory`) and `conversions` (objects with
`study_id`, `from_unit`, `to_unit`, positive `factor`, nonempty `reason`).
`timing` is `before-results` or `after-results`; `exploratory` is boolean.
Every extracted study occurs exactly once as included or excluded. Post-result
exclusions/subgroups and any subgroup absent from the frozen list must be
exploratory. Retain original rows. Failed-control and unavailable rows cannot be
pooled. Never count overlapping cohorts, independence groups or participants
twice. All included scales and directions must equal the frozen values.

Reuse `$cx-dimensional-analysis-units` for conversion justification. Different
units require a recorded factor, with effect multiplied by factor and variance
by factor squared. The validator checks arithmetic and labels, not the physical
correctness of that factor. Interpretation-changing conversions require human
choice; record the rationale for independent method review. No automatic unit
or sign guessing, repair or cross-scale pooling is provided.

## Stage 4: pooling

Inputs: protocol, extraction and gate paths plus hashes. Output `pooling.json`,
`meta-analysis-pooling-v1`, containing `status` (`computed` or `unavailable`),
`headline_model` and `results`. The public reference function is
`compute_meta_analysis(studies, min_studies=2)`; it accepts already harmonized
independent effects and checks numerical preconditions. Use the full validator
for independence and comparability. CPU-only stdlib, no randomness or network.
The same 200-study limit applies to this numerical entry point, bounding its
quadratic leave-one-out work. Empty or inadequate inputs retain `MA_MIN_STUDIES`.

For w_i=1/v_i, FE mean=sum(w_i*y_i)/sum(w_i), FE SE=sqrt(1/sum(w_i)).
Q=sum(w_i*(y_i-FE)^2), C=sum(w_i)-sum(w_i^2)/sum(w_i),
tau squared=max(0,(Q-(k-1))/C), I squared=max(0,(Q-(k-1))/Q)*100
(with I squared=0 when Q=0). RE uses weights 1/(v_i+tau squared).
Each model has `estimate`, `standard_error`, `ci_low`, `ci_high` using normal
z=1.959963984540054. These are approximate 95% Wald confidence intervals, not
prediction intervals, calibrated small-sample coverage or clinical validity.
The DL denominator and all computed values must be finite and nondegenerate.

`results` has `fixed`, `random`, `q`, `tau_squared`, `i_squared`,
`leave_one_out` and `small_study`. Each leave-one-out row names `omitted_study`,
both model estimates and heterogeneity values, plus `reversal` (sign change in
either model). A two-study input leaves one study in sensitivity: its tau squared
and I squared are zero by convention; this diagnostic is below the primary
minimum and cannot support a pooled synthesis claim. All reversals are disclosed.

The frozen model must match `headline_model`. A fixed headline is refused if
I squared OR tau squared strictly exceeds its frozen threshold; equality is
allowed. If the frozen fixed model fails, stop the confirmatory synthesis and
make any random-effects alternative a separately frozen exploratory revision.
If k<min_studies, require `status=unavailable`, `results=null` and no positive
synthesis claim. `small_study` uses `status=exploratory`, `method=Egger intercept
(descriptive only)`, `estimate`, `availability` and `reason`. Regress standardized
effect y/SE on precision 1/SE and report the intercept, with no p-value or
publication-bias inference. With fewer than three studies or constant precision,
`estimate=null` and `availability=unavailable`; otherwise availability is computed.
This uncalibrated diagnostic is never a confirmation or causal explanation. Preserve negative results rather than selecting significance.

## Stage 5: bounded claims and independent handoff

Inputs: all four prior output paths plus hashes. Output `handoff.json`,
`meta-analysis-handoff-v1`, containing `review_status=pending`, `claims` and
`evidence` path-plus-hash references, `claim_evidence` (claim ID to record-ID list),
`loo_reversals` (the ordered list of every omitted study that reverses sign), and
nonempty `limitations`. Use `$science-provenance` to register ordinary artifacts
and a separate existing `claims.json` claim-register. Do not extend that schema.

`evidence.json`, `meta-analysis-evidence-v1`, has `records`: unique `id`, `kind`,
`result`, `text`, `provenance` and `artifact` reference. Each source artifact uses
`meta-analysis-source-v1` with `kind`, `result`, `text`, `study_id` and `synthetic`.
Positive claims preserve literal source attribution. `external`, `independent`
and `preregistered` labels refuse a referenced path OR hash equal to any stage
or study output; labels alone do not establish independence. Separate evidence
requires a separately preserved source and independent review of its origin.

Every positive status (`supported`, `replicated`, `suggestive`) is checked even
when its `permitted_inference` says descriptive. Both the cited record AND source
are checked: kind or result containing `review`, `approv`, `comput`, `numerical`
or `simulat` cannot support positive claims. Neither can unavailable evidence or
failed controls. Claim kind alone cannot bypass the check. Review approval is
never scientific truth; computed agreement is never physical or clinical validity.

An empty claim evidence list requires status `unavailable`; every other status,
including `unsupported`, is refused as `MA_CLAIM`. Unavailable claims cannot assert
the positive words `supported`, `replicated`, `suggestive`, `significan*` or
`pooled estimate`, or any wording in the list below (`MA_CLAIM_BOUNDARY`).

The conservative, case-insensitive wording list uses word boundaries and refuses
positive claims matching
`caus*`, `therap*`, `clinic*`, `treat*`, `prescri*`, `recommend*`, `efficac*`,
`effective*`, `mechanis*`, `cure*`, `prevent*`, `dose*`, `dosing`, `activat*`,
`inhibit*`, `bind*` (binder included), `affinity/affinities`, `administ*`,
`induce/induces`, `drive/drives`, `lead/leads to`,
`physical valid*`, `physical correct*`,
`scientific truth`, or `prove/proves true`. Even a negated phrase can be refused;
rewording cannot substitute for scientific review. This finite English screen is
not a universal semantic detector. Use statistical-only descriptions. Evidence
absence is unavailable; review is not truth. The pack never self-attests review.

Hand the protocol, artifact hashes, separate claim register, exclusions, failed
controls, negative results, assumptions, sensitivity, dependencies, limitations
and next falsifiable action to `$science-review` (record, source, method).
Rigor and receipt admission stay with the coordinator. One checkpoint covers
all five stages; use existing manifest plan IDs and refresh/advance procedures.

## Schema and immutable identities

Root `pack.json`, `meta-analysis-pack-v1`, has boolean `synthetic` (all supplied
fixture labels must agree across the bundle) and five
ordered `stages`. Each embedded `meta-analysis-stage-v1` has `id`, `inputs`,
`output`; inputs equal the ordered list of all earlier output references.
A reference is exactly `{path, sha256}`; the digest is SHA-256 of the parsed
bytes, not reserialized JSON. Paths must be canonical, relative to the bundle,
without absolute components, `..`, backslashes or symlinks. All inputs are regular
files <=64 MiB, opened nonblocking with no symlink following and checked through
the descriptor. JSON must have an object root, unique keys recursively, finite
numbers of magnitude <=1e100 and depth <=64 (root depth zero). Booleans never
serve as numeric measurements. Every declared integer field requires a real
integer, never a boolean or float: protocol `min_studies`, extraction sample
sizes, claim-register `schema_version`, checkpoint `schema_version`,
`continuation_count`, `idle_continuations`, `continuation_budget`, `revision`,
wait `poll_interval_seconds` and run-budget `policy_version`,
`max_failed_attempts_per_class`, `max_review_rounds`. Existing checkpoint ranges
and versions remain supported; these pack-local checks add no counter limit.
The absolute bundle path is walked from the filesystem root using directory
descriptors and `O_DIRECTORY|O_NOFOLLOW` for each component. Each opened component
must match its descriptor-relative pre-open device/inode. The final descriptor
stays pinned for every artifact read and final hash check; root rechecks repeat
the same component walk and compare with the pinned identity. Root and ancestor
symlinks remain refused even when they point back to the original directory or
are hidden during pathname inspection. Descriptors close on success, refusal or
interruption. Empty/malformed files, special files, growth,
replacement and final hash changes are labelled refusals, never hangs.

The aggregate raw-byte budget is `MAX_TOTAL_BYTES = 256 * 1024 * 1024`
(256 MiB), checked against each new artifact's descriptor size before reading.
The aggregate JSON-value allowance is `MAX_TOTAL_NODES = 4000000`: before parsing,
count the root, every comma and the first value of every nonempty container with
a non-consuming lookahead. This conservative upper bound also counts matching
bytes inside strings. Equality passes; exhausted budgets refuse further unique
artifacts. Snapshots are keyed by `(st_dev, st_ino)`, so hardlink aliases share
one initial read, hash and parse and consume each budget once. Path identities
remain separate for hash checks and reporting. Final checks re-read each unique
inode once and check every referenced path; they do not consume the budgets again.
Byte or JSON-value exhaustion is `MA_LIMIT`.

`meta-analysis-validation-v1` is stdout only: `status`, `synthetic`,
`evidence=statistical only`, `review_status=pending`, `independent_studies`,
`headline_model`, `results`. It grants no scientific acceptance or independent
review. The benchmark record `meta-analysis-benchmark-v1` contains synthetic
frozen `tasks` with question, fixture, expected finding, acceptance criteria and
CPU/network/GPU budgets. No existing schema, receipt or runtime record changes.

## Failure handling and acceptance

CLI: `python3 scripts/validate_meta_analysis_pack.py <bundle-directory>`.
No output option or writes. Success exits 0 with a JSON record; refusal exits 1
with `status=refused`, named `finding` and `message`. Incorrect CLI syntax uses
argparse exit 2. Public Python validation raises labelled `ValueError`.
Correct the evidence or retain unavailable output; do not suppress controls,
mutate frozen thresholds after results, or retry unchanged failures.

The synthetic fixture is (-1,-1,4), each variance 1: FE=2/3, Q=50/3,
tau squared=22/3, I squared=88%, RE SE=5/3. Omitting C reverses the sign.
`tests/test_workflow_meta_analysis_pack.py` checks hand calculations, both public
entry points and each negative fixture. All examples and benchmark tasks are
synthetic fixtures, not biological or clinical conclusions. No live-source
fidelity or causal interpretation is tested. Human gates apply only before
installation, restricted transfers, new hosts, GPU/remote/heavy compute or
interpretation-changing choices; this pack performs none of those operations.

Refusal codes: `MA_LIMIT` (aggregate bytes or JSON values), `MA_FORMAT` (record shape), `MA_JSON` (encoding, duplicate keys,
nesting or numbers), `MA_PATH` (canonical path), `MA_INPUT` (unreadable or special
file), `MA_CHANGED` (growth, replacement or final change), `MA_HASH` (identity
mismatch), `MA_STAGES` (ordered handoff), `MA_PROTOCOL` (freeze), `MA_MIN_STUDIES`
(inadequate count), `MA_VARIANCE` (missing/non-positive uncertainty), `MA_SAMPLE`
(sample sizes/linkage coverage), `MA_INDEPENDENCE` (double-counting),
`MA_STUDY_LIMIT` (more than 200 extracted or numerical-input studies),
`MA_COMPARABILITY` (scale/direction), `MA_UNITS` (conversion), `MA_POSTHOC`
(unlabelled exploration), `MA_PRESERVATION` (missing/failed evidence), `MA_MODEL`
(frozen model), `MA_HETEROGENEITY` (fixed headline), `MA_NUMERIC` (reference
mismatch or degeneracy), `MA_LOO` (hidden reversal), `MA_REVIEW` (self-review),
`MA_EXTERNAL` (aliased evidence), `MA_CLAIM` (attribution),
`MA_CLAIM_BOUNDARY` (overclaim) and `MA_CLAIM_EVIDENCE` (inadmissible support).

The root also binds exactly one `checkpoint` path-plus-hash reference. Use the
existing checkpoint schema unchanged; its five ordered step IDs must match
`stage-01` through `stage-05`. A mismatched/invalid checkpoint is `MA_CHECKPOINT`.
The synthetic fixture uses a supported legacy checkpoint shape, with stage 5
still in progress while independent review is pending. No existing checkpoint
writer or shared validation contract is changed; this pack additionally refuses
non-integer representations of declared checkpoint integer fields.

When registering with the existing packaging script, use explicit kind overrides
for the local domain records. In particular, `protocol.json` and `studies.json`
otherwise trigger existing global basename conventions. Use the existing
`package_run.py refresh --run-dir <run-dir> --default-kind provenance-record
--kind protocol.json=meta-analysis-protocol --kind studies.json=meta-analysis-extraction`
route (prefix both paths when the pack is in a subdirectory). Keep `claims.json`
as the separate existing claim-register and `checkpoint.json` operational.
Do not register the pack-local extraction as the global study-table schema.
