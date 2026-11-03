# Frozen flow cytometry QC stages

All supplied data are synthetic fixtures. This document controls procedure,
never biological, physical or clinical evidence. The coordinator uses one existing
checkpoint, the manifest plan shape in plan.json and $science-provenance ordinary
artifact records plus separate existing claim-register entries. $science-review
owns independent record/source/method review and rigor classification.

## Invocation and immutable identities

`python3 scripts/validate_flow_cytometry_qc_pack.py BUNDLE` accepts one JSON bundle
and prints JSON, writing nothing. Success is exit 0; every refusal, including
missing/extra/unknown arguments, is exit 2 with JSON on stderr containing status
`refused` and the labelled `finding`. `--help` prints ordinary usage and exits 0.
The primary accepting synthetic fixture is examples/workflow-flow-cytometry-qc/pack.json.

Artifact identities have exactly path and sha256. Paths are canonical relative
POSIX paths below the bundle root, with no symlinks, absolute paths, parent hops,
backslashes or aliases through dot components. Digests are lowercase 64-hex SHA-256
of the exact bytes parsed. Pin every ancestor from filesystem root through the
bundle via directory descriptors, compare lstat/fstat identities before descriptor
reads, then recheck the entire ancestor chain and every input hash at completion.
Use O_NOFOLLOW and O_NONBLOCK: FIFOs, directories, devices, symlinks, oversized,
growing, replaced or unreadable files are labelled refusals. Hardlink aliases are
cached by device/inode and parsed once. Reads occur once for computation and once
for final hash verification; the final check never reparses or changes the result.

Limits are module constants: MAX_BYTES 64 MiB per artifact; MAX_TOTAL_BYTES 256 MiB
per bundle across distinct inodes; MAX_JSON_VALUES 4,000,000 bundle-wide values
estimated conservatively before parsing; MAX_ARTIFACTS 128 named artifacts;
MAX_ROWS 10,000 aggregate events; MAX_SAMPLES 32 including controls; MAX_CHANNELS
16; MAX_GATES 32 population gates; MAX_BINS 128 time bins; MAX_RECORDS 128 claims,
evidence records or evidence citations; MAX_ITEMS 20,000 JSON container entries;
MAX_STRING 4096 characters; MAX_DEPTH 32; MAX_NUMBER 1e100 magnitude. All dimensions
are bounded before dependent sets, matrices or loops. Malformed/duplicate-key,
deep, huge-number or non-finite JSON is refused; real integer fields never accept
booleans, floats or numeric strings. The JSON preparse estimate counts commas and
nonempty containers with an iterator, without allocating a regex match list.

## 01-rule-freeze

Accepted input: rules.json plus hash, and the compensation source path plus hash.
Call the pack-local validator before opening events.json. The output is the
hash-frozen flow-cytometry-qc-rules-v1 record and the ordinary artifact identity.
Freeze panel channel/fluorochrome pairs, units, linear scale, square unit-diagonal
invertible matrix, source identity, strictly increasing time-bin edges in seconds,
rate bound, area/height ratio bounds, live-dye maximum, rectangular/interval gate
bounds, both boundary control IDs, control types and positive-rate maxima, parent
order and minimum counts. Hash before event admission; outcomes_seen requires
exploratory true. Retain both snapshots after an interpretation-changing choice.
No silent re-placement and no automatic retries with relaxed controls.

## 02-event-qc

Accepted input: frozen rules identity and events.json plus hash. The output is
flow-cytometry-qc-events-v1 and explicit admitted sample/control identities.
Call the pack-local integrity checks. Require globally unique event IDs, unique
sample IDs, exact panel channel names, declared matching units/scale, finite
non-negative raw values and nondecreasing time per sample within half-open frozen
bins. Equal event times are allowed. Empty available samples are refused; empty
unavailable samples retain unavailable counts and percentages. A compensation
count other than zero is refused. Height must be positive for ratio computation.
A required FMO/isotype control must be present and available, with matching role.

## 03-compensation-gates

Accepted inputs: immutable frozen rules and events identities. Call
reference_computation in src/codex_science/flow_cytometry_qc_pack.py. Output is the
computed fields of flow-cytometry-qc-report-v1. The matrix maps true channel values
to measured ones; solve M x = measured by partial-pivot Gaussian elimination,
never multiply measured events by the spillover matrix. Compensated values may be
negative, but all intermediates remain finite within the arithmetic envelope.

Frozen order is stability, singlets, live, then population gates. Stability uses
all available sample/control events: half-open bin counts divided by bin widths,
variation (maximum rate minus minimum rate) / mean rate. Require variation at or
below max_rate_variation. Population bounds are inclusive and form rectangles.
Singlets use the inclusive area/height interval; live uses dye at or below its
maximum. Every population must descend from live, so doublets and dead events
cannot re-enter. Count parent-relative percentages as 100 * child / parent only
when child >= min_gate_events and parent >= min_percentage_events; otherwise
retain the count and percentage `unavailable`, including a zero-event gate.

For each population and each distinct boundary control, count control events
inside that gate after frozen exclusions; the denominator is that control's live
events. This fixed FMO denominator avoids an undefined denominator when a nested
positive FMO gate is empty. Require denominator >= min_percentage_events, then
compare 100 * positive / live against max_positive_percentage, inclusively. Failed
FMO/isotype and stability controls refuse the bundle before summary comparison.
Thresholds are arithmetic rules, not power or biological-validation justifications.

## 04-summary

Accepted inputs: rules and event identities plus report.json with its own hash.
Call validate_flow_cytometry_qc_pack and compare every count, denominator, time-bin
count/rate, variation and control percentage. Output is flow-cytometry-qc-result-v1,
status arithmetic-only, review unavailable. Real integers are required for counts;
floating agreement uses relative tolerance 1e-9 and zero absolute tolerance. Missing
singlet/live exclusions, reordered gates, invented zero percentages or changed
handoff hashes refuse. Preserve failures and negative results as ordinary artifacts
in the coordinator's run; the validator itself performs no writes.

## 05-handoff and claims

Accepted input: immutable pack, rules, source, events and report identities plus
pack-local evidence and claims. Call $science-provenance and $science-review via
the existing coordinator. No new global schemas, tool contracts or execution
engine are introduced. Outputs remain unreviewed ordinary domain artifacts with
separate claim-register entries. Checkpoint completion, rigor and independent
review require the existing coordinator; this validator attests neither.

Every evidence entry declares id, kind, result, origin, source. Origin is internal,
external, independent or preregistered. Non-internal labels must not alias the
study's own pack, rules, compensation source, events or report by path or hash.
A label cannot prove true independence or historical preregistration. Positive
statuses supported, replicated and suggestive cannot cite computed, numerical,
physical-validity or review-approval records, checking both kind and result.
Every citation to unavailable kind/result requires unavailable status, even mixed
with observed sources. Empty evidence requires unavailable status. Unavailable
claims cannot assert supported, replicated, suggestive or significant evidence.
Replicated is always refused: this synthetic fixture cannot establish replication.

Claims permit descriptive or associational kinds only. The conservative English
lexical wording gate is case-insensitive, whole-word with prefix families:
caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*.
It additionally refuses diagnos*, disease*, cell identity, functional state,
physical validity and truth, including negated wording. It is incomplete for
unlisted paraphrases and other languages. Association is never causality;
computed agreement is never physical or clinical validity; review approval is
never truth; unavailable evidence is never negative evidence. Cell identity,
function and disease interpretation are outside this pack.

Human gates occur only before installation, restricted transfer, new hosts,
GPU/remote/heavy compute or interpretation-changing choices. No per-stage prompt
is required for authorized offline fixture checks. Stop on missing essential input,
failed controls, malformed/unbounded data, changed identities or overreaching claims.

## Pack-local schemas

All input records have schema and fixture `synthetic fixture`, with exact fields:

- flow-cytometry-qc-pack-v1: stages, rules, frozen_rules_sha256, events, report,
  evidence, claims. Identities have path and sha256. Claims have id, kind, status,
  text, evidence (IDs). Evidence has id, kind, result, origin, source (identity).
- flow-cytometry-qc-rules-v1: panel (channel/fluorochrome), units, scale,
  compensation (matrix/source identity), time (units/bin_edges/max_rate_variation),
  singlet (area/height/ratio_bounds), live (channel/max), populations
  (id/parent/bounds), controls (id/type/channel/max_positive_percentage), order,
  min_gate_events, min_percentage_events, hashed_before_events, outcomes_seen,
  exploratory. Each bound has channel/low/high/low_control/high_control.
- flow-cytometry-qc-events-v1: units, scale, samples. Each sample has id, role,
  status, compensation_applied (integer), events. Each event has id, time and
  values, mapping every panel channel to one finite non-negative raw value.
- flow-cytometry-qc-report-v1: rules_sha256, events_sha256, kind computed, samples,
  controls, exploratory. Each sample has id/status/stability/gates. Stability is
  unavailable or bin_counts/rates/variation. Gates have id/parent/count/
  parent_count/percentage. Controls have control/gate/count/parent_count/percentage.
  Counts are real integers or unavailable only for missing samples; percentage is
  numerical or unavailable according to the frozen minimums.
- flow-cytometry-qc-result-v1: status arithmetic-only, review unavailable, stages,
  computation (samples/controls/exploratory), inputs (path/hash), limitations.

These are pack-local records only; no stored record class from an earlier runtime
is newly rejected because this pack and these schema names are new. The loose
compensation-source fixture is hashed as bytes and is not a new record schema.
Concurrent validators read immutable snapshots and write no files, refs or records.
A killed validator leaves the bundle untouched; separate stdout/stderr captures may
be incomplete and must not be admitted as a result without a successful exit.
