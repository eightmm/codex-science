# Fixed stages and immutable handoffs

Use one existing coordinator checkpoint and one existing manifest. Copy the
`plan` array from `plan.json`; step objects retain `id`, `description`, `status`.
The requested `planner.py` is absent in this checkout; the shape is evidenced by
`src/codex_science/artifacts.py:new_manifest`, the manifest example in
`examples/literature-review-reviewed-run/manifest.json`, and consumption by
`src/codex_science/pipeline_compiler.py`. This pack adds no execution engine.

Every input identity is `{path, sha256}`, relative to the pack index directory,
with exact file-byte SHA-256. Register stage outputs as ordinary artifacts;
register claim assertions separately in the existing claim register. Never add
domain fields to the global manifest, checkpoint or review receipt. Material
references go in the existing reference-use-ledger. Freeze each artifact before
handoff, and preserve earlier versions. A hash detects changed bytes; trusted
registration and independent review are needed to establish actual timing.

| Stage | Accepted input identities | Existing skill/script | Output and schema | Fixed controls and failure handling |
| --- | --- | --- | --- | --- |
| 01-question | Supplied protocol/assumptions path plus hash | statistical-inference-experimental-design; validate_research_design.py | question.json; experiment-question-v1 | Fix estimand, population/window, experimental/observational units, assignment and outcome before outcomes. Ambiguous unit or unidentified claim stops interpretation. |
| 02-power | question.json and effect/variance-source JSON paths plus hashes | statistical-inference-experimental-design; experimental-uncertainty-propagation/propagate_uncertainty.py for supplied uncertainty models; statistical-decision-analysis/run_decision_analysis.py for supplied cost models | power.json; experiment-power-v1 | Fix target, effect, variance, primary-family alpha, allocation, arm-level attrition and cost. Refuse study-result effects, observational-unit counts or insufficient recruited counts. Never invent variance or a utility model. |
| 03-randomisation | question.json, power.json paths plus hashes | statistical-inference-experimental-design | randomisation.json; experiment-randomisation-v1 | Fix assignment/blinding seeds, method, concealment and unit-level allocation. Missing or incompatible assignment fails. Preserve masking limitations. |
| 04-analysis-plan | Prior three stage paths plus hashes | statistical-inference-experimental-design; existing statistics_runtime/run_statistical_analysis.py only later for supported analyses | analysis-plan.json; experiment-analysis-plan-v1 | Freeze exact bytes with primary family, correction, alpha/thresholds, missing-data, exclusion and stopping rules. Refuse absent sequential stopping; do not treat a normal power approximation as sequential validation. |
| 05-controls | question.json and analysis-plan.json paths plus hashes | statistical-inference-experimental-design; experimental-uncertainty-propagation | controls.json; experiment-controls-v1 | Fix control IDs, failed-control response and negative/null retention. Preserve controls, failures and unavailable observations; withhold material interpretation when controls fail. |
| 06-review-handoff | All five prior outputs by path plus hash | science-provenance, then independent science-review via coordinator | handoff.json; experiment-handoff-v1, pack index; experiment-design-pack-v1 | Validate before collection; bind all inputs and the plan, name distinct producer/reviewer, remain pending-independent-review. Pack cannot issue a passed receipt or classify rigor. |

`validate_experiment_design_pack.py` reads the existing records without changing
them and returns `experiment-design-validation-v1` to stdout. A refusal is a
labelled error with exit 1; retain the failed record and fix the actual defect.
Do not retry by changing the endpoint, excluding an inconvenient unit or
relaxing a threshold. Missing evidence blocks that evidence-dependent step;
it is unavailable, not a negative observation. No automatic network fallback.

## Human decision gates

Continue ordinary reversible in-scope stage work. Gate only installation,
restricted transfers, new hosts, GPU/remote/heavy compute and substantive
interpretation-changing choices. The independent review handoff is mandatory
before data collection but is not a user approval prompt at each stage.
The coordinator owns permissions, rigor and actual collection authorization.
Clinical, animal, physical or other consequential collection is not authorized
by a passing fixture or validator. No stage in this pack executes collection.

## Post-hoc audit

Accepted identities: the frozen six-stage bundle; the actual `used_plan` path
plus hash; analysis.json; and the complete results.json inventory, including
negative/null comparisons, failed controls and explicitly unavailable results.
Run `--mode audit` using the local contract in `records.md`. Compare frozen and
actual primary families, outcomes, thresholds, exclusions, missingness,
multiplicity and stopping rules. Each discrepancy needs its own exploratory
label and reason. Added or dropped comparisons remain visible even if absent
from the finished narrative. Analysis and results must retain the same rows.
Hash mismatches are refused rather than relabelled into agreement. Bind any
legitimate amendment as a separate record while preserving the original plan.
Audit output remains unreviewed and goes to independent science-review.

The local `experiment-question-v1` and `experiment-analysis-v1` records differ
from the existing `research-design` and `statistical-analysis` interfaces.
Existing scripts consume their own unchanged schemas: use the selected sibling
skill's reference to author those inputs, then retain their native receipts as
ordinary artifacts. Never pass a pack-local stage record directly to an
existing runtime or extend that runtime's contract to accommodate the pack.

For a supported later analysis, reuse `run_statistical_analysis.py` and its
`statistical-analysis` receipt, including unit aggregation and recorded seeds.
The pack does not replace that schema or serialize its fields into a new
global receipt. More complex analysis and sequential operating characteristics
need a suitable specialist method and independent review before execution.
