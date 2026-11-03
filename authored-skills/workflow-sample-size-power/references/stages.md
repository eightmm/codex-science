# Frozen sample-size stages

All checked-in examples are redistributable synthetic fixtures. They demonstrate software behavior, never measured effects, historical preregistration or scientific validity. No network, downloads, installation, remote execution, GPU or third-party dependency is used.

## Inputs and identity

The public entry points are `normal_quantile(probability)`, `reference_computation(assumptions)` and `validate_sample_size_power_pack(path)` in `src/codex_science/sample_size_power_pack.py`. Only bundle validation checks source identities; the reference computation alone cannot establish provenance. The thin CLI `scripts/validate_sample_size_power_pack.py` takes exactly one bundle JSON path, prints a result on stdout, and writes no files. Missing, extra and unknown arguments produce JSON `{status: refused, finding: invalid-arguments: ...}` on stderr with exit 2; `--help` prints ordinary usage on stdout with exit 0. Other refusals are labelled ValueError findings, never tracebacks.

Each accepted input identity is exactly `{path, sha256}`: canonical POSIX path relative to the bundle and lower-case 64-character SHA-256 of the bytes actually parsed. No absolute paths, parent traversal, backslashes, symlinked components, special files or directories are admitted as artifacts. The bundle entry identifies its parent as the root. Every ancestor from the filesystem root is pinned through directory descriptors using O_DIRECTORY/O_NOFOLLOW; lstat/fstat identities and the complete ancestor chain are compared again at the end. Artifacts are opened relative to pinned descriptors with O_NONBLOCK/O_NOFOLLOW, checked as regular files before and after open, and read with a bounded limit-plus-one read. JSON is parsed once per unique device/inode; a final bounded read rechecks hashes, including hardlink aliases. This is a detected-change check, not a transactional snapshot or proof against a change after return.

## Pack-local schemas

These five local shapes are validated by the pack module; no global schema, artifact kind, checkpoint or receipt changes. All records include exactly `schema`, real-integer `schema_version: 1`, boolean `fixture`, and the fields below. Unknown/missing fields are refused. Checked-in records have `fixture: true`; supplied records may be false.

| Schema | Additional required fields |
| --- | --- |
| `sample-size-power-pack-v1` | `stages`, `inputs: {assumptions, calculation}` identities, `frozen_assumptions_sha256`, timezone-aware `frozen_at`, nullable `outcomes_available_at`, boolean `exploratory`, `study_outputs` source identities, `claims` |
| `sample-size-power-assumptions-v1` | `study_id`, `setting: laboratory/preclinical`, `outcome_type: continuous/binary`, `sidedness: one-sided/two-sided`, `one_sided_justification`, and the parameter records below |
| `sample-size-power-source-v1` | bounded non-empty strings `study_id`, `kind`, `result`, `text` |
| `sample-size-power-calculation-v1` | `power_basis: prospective`, `effect_basis: frozen-prior`, `result` |
| `sample-size-power-result-v1` | `stages`, `status: computed/exploratory`, `evidence_level: arithmetic-only`, `review: unavailable`, `result`, `input_identities`, `claims`, `limitations` |

The table is exhaustive; the plan, reference index, quality declaration and benchmark use existing repository shapes, not additional domain schemas.

Assumption parameters are `alpha`, `adjusted_alpha`, `target_power`, `allocation_ratio`, `nuisance`, `effect`, `attrition`, `multiplicity`, `minimum_n`, `sensitivity_points`, `outcome_range`. Each is exactly `{value, source, assumption, rationale}`; `source` is null or an identity, `assumption` is boolean, and `rationale` is non-empty text. `nuisance` additionally requires two numeric `uncertainty` endpoints; `outcome_range.value` contains two numeric bounds. `multiplicity`, `minimum_n`, `sensitivity_points`, every schema version and every arm size are real ints, never bool, float or numeric string. Every number requires a non-null source or an explicit assumption label; the minimum effect always requires a prior source. A source's study identity, path and hash are compared against this study and all declared outputs, regardless of external/independent/preregistered labels.

`result` is exactly `{nuisance, analyzable_n, enrolled_n, power, minimum_detectable_effect, sensitivity}`. Each sensitivity row has the same fields except `sensitivity`. Arm vectors contain two positive integer counts. Claims are exactly `{id, kind, status, text, support}`; support entries are `{path, sha256, origin}`, with origin study/external/independent/preregistered. These local claim summaries do not replace the existing separate claim register with its required semantics.

## 01-freeze

Accepted identities: supplied prior source records and the assumptions file, each path plus hash. Use this conductor and `$science-provenance`; the output is `sample-size-power-assumptions-v1` and its frozen hash in `sample-size-power-pack-v1`, plus the existing manifest and reference-use ledger. Copy the existing `{plan: [{id, description, status: pending}]}` shape from `plan.json` into the coordinator plan and create one checkpoint per run, with the five exact ordered IDs.

Freeze all parameter values, uncertainty endpoints, units, experimental unit, sources/cutoff, time horizon and claim scope before outcomes exist. `frozen_at` must precede non-null `outcomes_available_at`, unless `exploratory` is true. Hash mismatch always refuses; an exploratory revision preserves the original artifact and separately freezes the new file. Hashes and timestamps cannot prove a historical freeze or source authenticity. A material interpretation-changing choice is a human gate; ordinary local hashing is not.

## 02-qc

Accepted identities: frozen assumptions and all referenced source records, plus declared own-output identities for leakage checks. Call the pack validator; emit its labelled finding on failure, retaining the source bundle. QC is included in the local result rather than a new record schema. Review unavailable assumptions with `$cx-experimental-uncertainty-propagation` when their interpretation matters.

Require alpha, adjusted alpha and target power in (0,1), adjusted alpha equal to family alpha divided by the frozen positive multiplicity count, power greater than adjusted alpha, positive SD/control proportion within its uncertainty endpoints, positive effect no greater than the plausible outcome range, and attrition in [0,1). For binary outcomes the range is exactly [0,1] and every control plus effect across uncertainty remains strictly below 1. A one-sided test requires a frozen directional justification. A source marked unavailable cannot supply a number. Own-outcome sources are refused even when relabelled prior or external. Empty, malformed, zero-variance and non-finite inputs refuse rather than returning useful-looking numbers.

## 03-computation

Accepted identities: the frozen assumptions and prior sources admitted by QC. Call `reference_computation`; output `sample-size-power-calculation-v1`. Freeze the following normal-approximation formulas, not a simulation, t-test or clinical-trial design. Let r be n2/n1, d the positive minimum effect, a the adjusted alpha, q the target power, f attrition and Phi the standard normal CDF. z(p) is found by 100 bisections on [-9,9] using `(1+erf(z/sqrt(2)))/2`, without rounded lookup-table quantiles. Set c=z(1-a/2) for two-sided or z(1-a) for one-sided and k=c+z(q).

For continuous outcomes, V=sigma^2(1+1/r). For binary outcomes with control p and alternative p+d, V=p(1-p)+(p+d)(1-p-d)/r. Set n1=max(minimum_n,ceil(V*k^2/d^2)), n2=max(minimum_n,ceil(r*n1)); enroll ceil(n1/(1-f)) and ceil(n2/(1-f)). Compute SE=sigma*sqrt(1/n1+1/n2) for continuous outcomes and sqrt(p(1-p)/n1+(p+d)(1-p-d)/n2) for binary outcomes. Achieved power is Phi(d/SE-c), plus Phi(-d/SE-c) for two-sided tests. The sizing formula ignores that small opposite tail; the achieved power includes it.

Continuous MDE is k*SE. Binary MDE solves d^2=k^2[p(1-p)/n1+(p+d)(1-p-d)/n2]: A=1+k^2/n2, B=-k^2(1-2p)/n2, C=-k^2*p(1-p)(1/n1+1/n2). Use its positive root, with the cancellation-safe equivalent -2C/(B+sqrt(B^2-4AC)) when B>0, and require p+MDE<1. The MDE uses the same sizing approximation, not exact two-tailed inversion. Recompute every row of an evenly spaced frozen nuisance grid including endpoints; no outcome-dependent adjustment or fitting is allowed.

Hand checks: the continuous synthetic fixture uses sigma=2, d=1, a=.025, q=.8, r=1 and f=.1. With c=2.241402727604947 and z(q)=.841621233572914, 8*k^2=76.04029396..., giving [77,77] analyzable and [86,86] enrolled; achieved power .8053853429909763 and MDE .9937486026230442. The SD endpoints 1.5 and 2.5 give [43,43] and [119,119]. The binary fixture with p=.2 and d=.1 has V=.37, n=[352,352], enrolled=[392,392], power .8003846192662507. The justified one-sided r=2 fixture has n=[48,96], enrolled=[54,107], power .8074295788138212. All are synthetic arithmetic controls.

## 04-consistency

Accepted identities: the same frozen inputs plus stated calculation, each path/hash. Call `validate_sample_size_power_pack`; emit `sample-size-power-result-v1`. Compare arm sizes exactly before the remaining numbers, which must agree with recomputation within absolute `POWER_TOLERANCE=1e-9`. `rounding-attrition` therefore precedes `power-consistency`; provenance and assumption refusals precede both. A non-integer count never passes via tolerance. Preserve failed controls and negative results without rerunning with tuned assumptions. Recheck every identity and the complete ancestor chain at the end.

## 05-handoff and bounded claims

Accepted identities: the validated inputs, calculation, source records, result and coordinator artifact manifest, all hash-bound. Register domain files as ordinary artifacts through `$science-provenance`, and separate claim-register entries with stable IDs, required support, falsifiers, dependencies/conflicts, uncertainty and applicability. Complete the matching plan/checkpoint stages. Send the whole decision contract, prior provenance, deviations, unavailable evidence, sensitivity and retained refusals to `$science-review`. Rigor and independent review are coordinator-owned; this pack's result always says review unavailable. Review approval is never truth.

All claim statuses reject causal/therapeutic/clinical-action/efficacy/mechanism wording, regardless of kind labels. The conservative English case-insensitive whole-word prefix families are caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*. Additional matches: adequate, well powered (space/hyphen), no effect (space/hyphen), truth, physical validity (space/hyphen), observed power, post hoc/post-hoc power. Negation does not bypass the gate; other languages and paraphrases are incompletely covered. Only descriptive/associational kinds are admitted; association never establishes causality and numerical agreement never establishes physical or clinical validity.

Empty support requires unavailable status. Any cited source whose declared kind OR result is unavailable forces unavailable status, even mixed with other evidence. Unavailable text cannot say supported, replicated, suggestive or significan*. Positive statuses supported/replicated/suggestive cannot cite kind OR result matching review, approv, comput, numer, agreement, truth, physical or clinic. All replicated statuses are refused: this pack cannot establish independent replication. Refusal ordering keeps boundary/evidence findings ahead of that replication gate. Absent records remain unavailable, never evidence of no effect.

## Bounded input envelope

Module constants are checked before dimension-dependent work: `MAX_BYTES=67108864` per artifact, `MAX_TOTAL_BYTES=268435456` across unique inodes, `MAX_TOTAL_NODES=4000000` across JSON values, `MAX_ARTIFACTS=128` path identities, `MAX_ITEMS=1024` per JSON container, `MAX_TEXT=4096` characters, `MAX_DEPTH=32` container depth, `MAX_CLAIMS=100`, `MAX_SUPPORT=32`, `MAX_GRID=9`, `MAX_N=1000000000`, `MAX_MULTIPLICITY=10000`, `MAX_NUMBER=1e100`, `MIN_PROBABILITY=1e-12`. Allocation ratio is [0.001,1000], minimum_n is [2,MAX_N], sensitivity_points is [2,MAX_GRID]. Adjusted alpha must be at least MIN_PROBABILITY and power at most 1-MIN_PROBABILITY. Quantile probabilities use [MIN_PROBABILITY/2,1-MIN_PROBABILITY/2].

Before JSON parsing, charge the conservative bound one plus the comma count plus the number of non-empty containers (opening brackets or braces not immediately closed), the latter counted by streaming iteration; punctuation in strings may conservatively overcharge. Never allocate a findall match list. After parsing, enforce actual values/depth/container/string bounds and charge the larger estimate. Reject duplicate nested keys, non-object roots, non-finite/huge numbers, malformed UTF-8 and excessive nesting with labelled findings. Aggregate byte budgets are checked from fstat before reading; hardlinks are parsed once. No retry or budget escalation is automatic.

## Acceptance and interruption

`tests/test_workflow_power_pack.py` exercises all 24 entries of `examples/workflow-sample-size-power/negative-cases.json` for their distinct stated codes, hand-derived arithmetic, JSON/descriptor attacks, CLI argument errors and deterministic root/ancestor swaps. `benchmarks/workflow-sample-size-power/tasks.json` freezes questions, criteria and offline budgets. L4 means these synthetic software checks, not empirical adequacy or review.

The validator and CLI write no record, ref or checkpoint. Concurrent calls read the same immutable bundle and produce independent stdout results; termination leaves no bundle changes, although a caller capturing stdout may retain a partial JSON stream and must check exit status. Coordinator writes and checkpoint updates use the existing coordinator mechanisms; they are outside this validator. Retain immutable input versions rather than replacing a bundle under validation.
