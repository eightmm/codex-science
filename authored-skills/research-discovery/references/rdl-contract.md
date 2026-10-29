# Research Discovery Loop contract

This reference is the detailed contract for a `research-cycle-v1`. The runtime
validates its machine fields and hashes; Codex remains responsible for the
scientific interpretation.

## Cycle schema

A cycle contains `problem` (`observed`, `interpreted`), `evaluation`
(`evaluator`, `baseline`, `split`, `budget_rule`, `primary_metric`,
`threshold`, `budget`, and artifact references), `hypotheses`, `methods`,
`experiments`, `events`, and lifecycle status. Each snapshot records a
monotonic revision number,
parent snapshot hash and content hash. Snapshots are
append-only: correcting a statement creates a new revision with a reason and
does not rewrite the observation that caused it.

Artifact `sha256` references must be lowercase hexadecimal SHA-256 digests;
admission refuses uppercase spellings rather than rewriting stored values.

The frozen `evaluation` object identifies evaluator, split, baseline, metric,
threshold, budget rule, and budget. If protection is procedural rather than
externally isolated, record that limitation in the evaluation evidence; code
hashing alone does not prove holdout inaccessibility.

## Method contract

Every method has an ID and links one or more hypotheses to:

- representation and input/output tensor shapes;
- ordered data flow and train/eval behavior;
- objective, optimization variables, and controls;
- assumptions and invariants (including conservation, equivariance, units, or
  shape constraints where applicable);
- asymptotic time and memory complexity and the measured budget;
- repository code location and implementation revision when executable. Idea
  records may omit `code_refs`; reserving an experiment requires code refs.
- prediction, falsifier, and invalidation conditions.

Allowed generation operators are `representation`, `objective`,
`assumption`, `conditioning`, `computation`, and `transfer`. A cross-domain
mapping uses `transfer` and its `mapping` fields: `source_variables`,
`target_variables`, `correspondence`, and `validity_conditions`. These name the
source formalism, target object, correspondence, and boundary where the analogy
breaks.

Literature-guided candidates: reference the allocation artifact from the cycle
like other evidence. A method's operator remains one of the allowed operators
above; paper ID, mechanism family, and excerpt provenance live in the allocation
artifact, whose `selected` entries copy each paper's `excerpt` and, when
supplied, `source_sha256`. The allocator input is `method-landscape-v1`: a
positive integer `budget`, `topics` with `id` and boolean
`covered_by_baseline`, and `papers` with `paper_id`, nonempty string `topics`,
a 20-2000 character `excerpt`, and optional `source_sha256`.

## Predictions and experiments

A prediction includes the expected direction or interval, resolution, inputs,
controls, and the result that would weaken the linked hypothesis. Two
predictions are distinguishable only when the gap between their intervals is at least the
declared measurement resolution under the same evaluator and budget. A proposed
experiment that cannot distinguish the linked explanations receives the rejection
reason `no-distinguishable-pair-at-declared-resolution`, and is not selected
merely because it is cheap or likely to score.
The selector compares interval gaps, resolution, and total candidate plus control
costs using exact decimal spellings of validated numbers. Equality meets the
resolution threshold and budget cap; no numerical tolerance admits excess cost
or an unresolved gap.

The `discriminate_first_v1` selector may be used only with explicit prediction
intervals, resolution, controls, cost, and remaining budget. The legacy planner
remains valid for routes that lack this contract. Finite decision analysis may
be reused only when its separate one-stage contract is satisfied; uncertainty
proxies, EIG, and EVSI are not interchangeable. The discovery decision input
requires `state_model_rationale`, `assumption_refs` (each a confined path and
SHA-256), and `decision_contract` using the existing finite decision schema.
EVSI remains in the declared loss/utility/payoff units and is never silently
compared with the compute budget; no automatic belief or posterior is inferred
from a model score or uncertainty proxy.

## Observation classification

Record four axes independently:

1. `method_effect`: `positive`, `nonpositive`, or `inconclusive` for completed observations;
2. `explanation_support`: `consistent`, `contradicted`, or `inconclusive` for
   each hypothesis;
3. `verification`: `pending`; completing a calculation never self-attests review;
4. `novelty`: `unassessed`; novelty review is separate evidence.

Classification uses the declared scalar measurement and half the declared
resolution on either side. This is a deterministic tolerance, not a calibrated
confidence interval or sampling-uncertainty estimate. `consistent` means that
the bounded observation agrees with a prediction; it does not establish a
mechanism, and multiple competing explanations can remain consistent. Broader
statistical inference needs its own design and uncertainty analysis.

An implementation or environment error cannot refute a hypothesis. Runtime
failure events use `failure_kind: implementation`, `execution`, or
`measurement`; they remain failure records rather than scientific refutations.
A valid null result is retained and can weaken a method or explanation. A result that occurs
only under one declared condition remains conditional until the condition is
tested independently. Novelty is never inferred from a score or from a search
that was not recorded.

## Recovery

Registered revisions in the run manifest form a minimum committed prefix:
loading or saving refuses missing registered snapshots or snapshot bytes that
do not match their registered SHA-256 digest. Newer saved snapshots
remain recoverable when manifest attachment lags. A failed write, flush, or
fsync removes its unpublished temporary file so an unchanged save can retry.

The primary metric may declare a `json_pointer`; completed observations must use
that same pointer, and their declared value must equal the hashed JSON artifact
value. Pointer tokens escape `~` as `~0` and `/` as `~1`; array indices use `0`
or ASCII decimal digits without leading zeros. Failed events may carry hashed
`evidence_refs` when the failure itself has a diagnostic artifact.

## Successful execution receipt

A `complete` event must include `execution_refs` pointing to at least one
confined JSON receipt. The receipt is a correspondence check across the
declared experiment, method, evaluator, and measurements:

```json
{
  "schema_version": 1,
  "experiment_id": "E1",
  "experiment_fingerprint": "<sha256-of-declared-experiment>",
  "method_id": "M1",
  "code_refs": [{"path": "code.py", "sha256": "<method-code-sha256>"}],
  "evaluation_refs": [{"path": "evaluation.json", "sha256": "<frozen-evaluation-sha256>"}],
  "measurement_refs": [{"path": "result.json", "sha256": "<observation-artifact-sha256>"}],
  "exit_code": 0
}
```

`code_refs` and `evaluation_refs` must exactly match the method and frozen
evaluation references; `measurement_refs` must include every completed
observation artifact. An optional `candidate_sha256` must match a declared
method code reference. This verifies declared cross-identity and hash
correspondence. It does not establish OS isolation, authenticated provenance,
or that a producer honestly executed the claimed code.

The existing checkpoint owns execution identity, approval, waiting, resume, and
completion. The research cycle owns only scientific snapshots and references to
those runs. On interruption, reconcile the cycle snapshot, manifest, and
checkpoint before acting. If submission state is ambiguous, inspect the
existing execution receipt and do not resubmit by default. A repeated
fingerprint is idempotent only when the prior identity and inputs match;
otherwise create a new declared experiment.
Experiment definitions compare numeric values when checking duplicates, so
integer and float spellings alone do not create a new experiment. A duplicate
requires `retry_of` naming the latest matching failed experiment; its stored
fingerprint still hashes the original spelling.

Do not rewrite an observed prediction, evaluator, split, baseline, metric, or
budget after seeing an outcome. If the protected evaluation contract must
change, start a new cycle; a revision may append hypotheses, methods, or
experiments only while retaining the frozen problem and evaluation.

Budget exhaustion, a failed implementation, or an unresolved measurement is a
terminal recorded outcome for that attempt, not a promoted success. Continue
only with a declared repair, revised prediction, or new experiment.
Reserved cost and control cost totals use exact decimal spellings for budget
comparison, preserving stored numbers and admitting totals equal to the budget.

`discovery assess` projects each `revise` event into `revision_outcomes`
(`insufficient_evidence`, `repetition`, `necessary_repair_candidate`,
`substantive_progress_candidate`) from recorded fields only; it is read-only, and
candidate labels require review.

## Operating the evidence loop

For material method work, initialize with `--require-design`. This records that
a reservation requires a complete theory-to-code contract: the current method
and unexplained observation, assumptions, linked hypotheses, operator,
inputs/outputs, computation, invariants, complexity, failure modes,
applicability, predictions, baseline difference, and implementation/correctness
references (`design.implementation.code_refs` and `design.correctness_refs`).
Missing correctness references block implementation readiness and reservation
under this policy; legacy readiness is unchanged. `discovery audit` reports
readiness; it does not certify that a
method works. An idea may be recorded without `code_refs`, but cannot be
reserved until its implementation identity is present.

Before generating new candidates in a project with prior runs, read the
ProjectStore-backed `discovery memory` view. It combines only exact matching
evaluation, method, and hypothesis identities. Different problems, protected
evaluators, splits, budgets, or method-design contracts remain heterogeneous;
they are never votes or independent replications. A shared execution identity
also has unknown independence. Missing historical fields are a request to
preserve the minimum scientific state, not permission to infer it.

After initialization and each event, use `discovery next`. It first requests
reconciliation of an ambiguous submission, then existing reserved/running work,
then repair of an unresolved failure, and only then an eligible discriminating
proposal. Its labels remain conditional on the frozen evaluation, controls,
resolution, and budget. A contradiction identifies a prediction/applicability
boundary for a revision; it does not automatically reject a universal
mechanism. A nonpositive effect does not prove a competing explanation.

`discovery graph` emits evidence graph v2 edges only for completed,
preregistered prediction compatibility. A support/contradiction edge is scoped
to those conditions and never confirms causality, novelty, or replication.
`discovery assess` consumes optional hashed `review_refs` and reports separate
record, source, method, and reproduction axes. A `novelty_comparison` may
record a bounded, sourced comparison, but neither hashes nor review receipts
prove novelty.

The optional observed finite-decision policy is available only after a real
completed measurement. Its `observed_outcome` must bind an actual artifact and
JSON pointer to a frozen `preregistered_decision_ref` in evaluation evidence;
the prior record must contain the exact `observation_bindings`. The resulting
policy is conditional once on that recorded category, not a posterior over
coexisting hypotheses or a sequential research policy.

Review scope is explicit: `assess` includes all registered review receipts plus
any supplied supplemental refs. The latter are not persisted by this read-only
view. `passed_in_review_scope` never attests completeness beyond the bundle.
Observation bindings include the exact preregistered `artifact_path` as well as
the experiment IDs and JSON pointer, preventing post-hoc selection among results.
