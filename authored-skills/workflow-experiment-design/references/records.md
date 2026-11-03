# Pack-local records and commands

All examples under `examples/workflow-experiment-design/` are deterministic,
redistributable **synthetic fixtures**, not scientific evidence, performed
experiments or review receipts. Read the complete example JSON for the selected
route. The Python validator is authoritative for required fields and refusals.
No existing runtime writes these local schemas; no earlier stored record class
changes validation. All records are JSON objects. Required strings are nonempty;
counts/seeds are integers, excluding booleans; all numbers must be finite.

## Local schemas

| Schema | Fields and constraints |
| --- | --- |
| experiment-design-pack-v1 | `schema`; six identities named `question`, `power`, `randomisation`, `analysis_plan`, `controls`, `handoff`. Audit additionally requires `analysis`, `results`, timezone-aware `data_collection_started_at`, `outcomes_available_at`. Preregister requires no analysis or collection/outcome timestamps. |
| experiment-question-v1 | `schema`, question, estimand, population, experimental_unit, observational_unit, assignment_mechanism, primary_outcome, observation_window; `claims` list of conservative boundary tags. |
| experiment-power-v1 | `schema`, method=`normal-approximation-two-group`, count_unit matching the experimental unit, positive assumed_effect and variance, target_power strictly inside (0,1); effect_source={origin, artifact}, variance_source identity; two unique arms; cost_unit. Each arm has id, required_analyzable integer >=2, planned integer >=2, attrition in [0,1), positive allocation, cost_per_unit >=0. Effect origin is external, independent-pilot or scientific-minimum. |
| experiment-randomisation-v1 | `schema`, assignment_mechanism matching question; method, blinding and allocation_concealment text; assignment_seed and blinding_seed integers >=0. Seeds specify the plan; the validator performs no assignment. |
| experiment-analysis-plan-v1 | `schema`, timezone-aware frozen_at, outcomes_seen=false; method; primary_family nonempty unique {id, outcome, threshold} rows; alpha in (0,1), multiplicity none for a singleton or bonferroni; all thresholds >0 and <= alpha/family size; missing_data_rule, unique exclusion_rules list (empty allowed), sequential boolean, stopping_rule; sequential_error_control text required when sequential. |
| experiment-controls-v1 | `schema`, nonempty unique control_ids, failure_rule, negative_result_handling. These are commitments for the reviewer, not proof controls passed. |
| experiment-handoff-v1 | `schema`, distinct producer/reviewer names, status=pending-independent-review, handed_off_at >= frozen_at; analysis_plan identity; inputs object binding the exact five prior identities. It is a handoff, not an independent review receipt. |
| experiment-analysis-v1 | `schema`, used_plan identity, actual primary_family and method/multiplicity/missing_data_rule/exclusion_rules/sequential/stopping_rule (plus sequential_error_control when needed); deviations list; reported_results list; claims list. Each deviation is {kind, target, label=exploratory, reason}. Every detected discrepancy must match one label; unmatched labels are refused too. |
| experiment-results-v1 | `schema`, nonempty results rows {id, status, control_status}. IDs are unique; include every frozen and actual comparison and control. status is positive/negative/null/failed/unavailable; control_status is passed/failed/unavailable. Preserve the complete inventory in reported_results without changing any row, including additional fields. |
| experiment-design-validation-v1 | Output only: schema, mode, status=`ready-for-independent-review` for preregistration or `unreviewed-audit` for audit, ordered stage_ids, immutable stage inputs, power {achieved_power, planned_cost, planned_units}, deviations and limitations. It is not a claim register or a review receipt. |

Identities contain `path` and lowercase 64-character hexadecimal `sha256`.
Paths must be bundle-relative with no parent traversal, backslash or resolved
escape; unavailable files and malformed JSON are refused. Source assumptions
are ordinary hash-bound JSON artifacts, not new globally validated records.
The `fixture` labels in examples are descriptive, not required in real records.

## Power and boundaries

The validator checks the declared two-sided, independent two-group known-variance
normal approximation at the smallest frozen family threshold. It uses the
declared analyzable counts, effect and variance with Python stdlib NormalDist.
This is a consistency check of assumptions, not a general sample-size solver.
For each arm, planned >= ceil(required_analyzable/(1-attrition)); planned arm
ratios must agree with the declared allocation (relative tolerance 1e-12).
Total cost is sum(planned * cost_per_unit). Zero cost/attrition and zero seeds
are allowed. Cluster, paired, binary, survival, adaptive or sequential power
requires specialist design; this approximation does not qualify those designs.
Effect/variance provenance must be reviewed; hashes do not establish independence.

The post-hoc deviation kinds are `changed-outcome`, `changed-threshold`,
`added-comparison`, `dropped-comparison`, `post-hoc-exclusion`, `dropped-exclusion`,
and `changed-analysis-rule` (target names the rule). The audit preserves any
failed controls and withholds reviewed status; the coordinator decides claim
impact and review. Required outcome/threshold changes cannot be hidden in an
unrelated exploratory comparison.

Claims here are boundary tags, not evidence assertions or claim-register rows:
`association` permits only `association`; `numerical-agreement` only
`numerical-agreement`; `unavailable` only `unavailable`; `review-approval` only
`review-status`. Any promotion to causality, physical/clinical validity,
negative evidence or truth is refused as `inference-boundary`.
Domain-specific stronger claims belong to the coordinator's supported claim
register and independent review, never to this validator's self-assessment.

## Commands and failure behavior

```bash
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/preregister.json
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/audit.json --mode audit
python3 scripts/validate_experiment_design_pack.py examples/workflow-experiment-design/exploratory-audit.json --mode audit
```

The public Python entry point is `validate_experiment_design_pack(path, mode=...)`.
CLI `input` selects the pack; `--mode preregister|audit` defaults to preregister.
Success prints JSON to stdout, exit 0. A labelled ValueError or named IO error
prints `error: experiment-design-pack: ...` to stderr, exit 1, no traceback.
Argument errors use argparse's normal exit 2. The validator writes no files and
has no output-path option, execution, install or transfer behavior.
Two concurrent validations read the same immutable bytes without shared writes.
Killing validation leaves every input unchanged and may leave partial stdout;
never register partial stdout as a completed artifact. The coordinator writes
reports to fresh paths and registers hashes only after successful completion.

## Acceptance and seeded refusals

`expected-preregister.json` and `expected-audit.json` are frozen synthetic
validator outputs. `exploratory-audit.json` covers all required deviation kinds.
`negative-cases.json` maps the eight seeded defects to input, mode and exact
refusal code. Every fixture is exercised through the public CLI by
`tests/test_workflow_experiment_design.py`. The frozen benchmark tasks add
acceptance criteria and CPU/offline budgets; L4 denotes these deterministic
contract tests, not real-world scientific efficacy or authenticated timing.
