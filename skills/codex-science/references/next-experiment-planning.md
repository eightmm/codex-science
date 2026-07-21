# Multi-objective next-experiment planning

Read this reference before ranking candidates for a new assay, synthesis batch, simulation, data collection round, or other experiment. The planner produces a deterministic proposal from declared values and constraints. It does not execute an experiment or infer valid uncertainty, similarity, or information gain from a model label.

## Input contract

```json
{
  "schema_version": 1,
  "decision": "Select the next 24 compounds.",
  "objectives": [
    {
      "name": "potency",
      "direction": "maximize",
      "weight": 0.5,
      "required": true
    },
    {
      "name": "solubility",
      "direction": "maximize",
      "weight": 0.3,
      "required": true
    },
    {
      "name": "off_target_risk",
      "direction": "minimize",
      "weight": 0.2,
      "required": true
    }
  ],
  "candidates": [
    {
      "id": "compound-001",
      "properties": {
        "potency": 8.2,
        "solubility": 0.6,
        "off_target_risk": 0.2
      },
      "cost": 450,
      "uncertainty": 0.7,
      "diversity_group": "scaffold-A",
      "control": false,
      "eligible": true,
      "metadata": {
        "source_artifact": "candidate-table.parquet",
        "source_record": "compound-001"
      }
    }
  ],
  "constraints": {
    "batch_size": 24,
    "budget": 12000,
    "diversity_group_cap": 4,
    "minimum_controls": 2
  },
  "uncertainty_weight": 0.25,
  "diversity_bonus": 0.1,
  "claim_ids": ["C-potency", "C-selectivity"]
}
```

### Objectives

- `direction`: `maximize` or `minimize`;
- `weight`: non-negative; at least one weight must be positive;
- `required`: every eligible candidate must contain that property.

The planner performs within-contract min-max normalization. Therefore scores from different input batches are not directly comparable unless their candidate population and scaling contract are identical.

### Candidates

Required:

- stable candidate ID;
- numeric properties;
- non-negative cost;
- non-negative uncertainty;
- diversity group.

Optional:

- `control`;
- eligibility and exclusion reason;
- source metadata.

`diversity_group` is an explicit category supplied by the workflow. It may represent scaffold, target family, donor, site, assay plate, or another prespecified grouping. The planner does not derive chemical or biological similarity.

### Constraints

- `batch_size`: maximum selected records;
- `budget`: total declared cost cap;
- `diversity_group_cap`: maximum selected records per group;
- `minimum_controls`: required eligible controls.

Required controls are selected before optimization. If they cannot fit the batch, budget, or diversity cap, the proposal fails rather than silently removing them.

## CLI

```bash
python scripts/plan_next_experiment.py \
  artifacts/run-020/next-experiment-input.json \
  --output artifacts/run-020/next-experiment.proposal.json
```

The proposal is deterministic when the full input, including time field supplied by the API, is unchanged.

## Selection method

The current deterministic policy performs:

1. eligibility filtering;
2. objective min-max normalization with minimize directions inverted;
3. Pareto-front construction;
4. mandatory control selection;
5. weighted objective utility;
6. declared uncertainty bonus;
7. explicit diversity-group bonus;
8. greedy selection subject to budget, batch, and group cap;
9. explicit rejection reasons.

The utility score is a ranking instrument inside the proposal, not a calibrated expected outcome.

## Output contract

```json
{
  "schema_version": 1,
  "proposal_id": "experiment-...",
  "decision": "...",
  "status": "proposed",
  "executed": false,
  "selected": [],
  "rejected": [],
  "pareto_fronts": [],
  "total_cost": 11500,
  "remaining_budget": 500,
  "diversity_groups": {},
  "expected_information_gain_proxy": 0.42,
  "required_controls_satisfied": true,
  "approval_required": true,
  "claim_ids": [],
  "evidence_boundary": "...",
  "fingerprint": "..."
}
```

Every selected record retains:

- original declared properties;
- normalized objective values;
- uncertainty score;
- Pareto front;
- base utility;
- cost, control state, and diversity group.

Every rejected record retains one or more reasons such as:

```text
ineligible
reactive-substructure
budget
diversity-group-cap
not-selected-within-batch
```

Do not remove rejected candidates or reasons from the saved proposal.

## Required workflow

1. Define the decision and claims before candidate scoring.
2. Validate candidate identities and source artifacts.
3. Confirm objective direction, units, and applicability.
4. Validate uncertainty calibration separately; use zero uncertainty weight if unvalidated.
5. Define controls and diversity groups before outcome inspection.
6. Set budget and batch constraints.
7. Generate the proposal.
8. Inspect Pareto fronts, selected controls, repeated groups, costs, and rejection reasons.
9. Run domain-specific safety and feasibility filters that are not encoded in this generic planner.
10. Obtain experimental, remote, paid, synthesis, or write approval.
11. Save the approved experiment package and execute through the appropriate system.
12. Ingest results without dropping failed synthesis, assay failure, or missing outcomes.
13. Update claims and project evidence memory.
14. Review selection bias and whether the next round remains comparable.

## Applicability examples

### Compound selection

Use declared scaffold or series as `diversity_group`. Candidate properties may include potency, selectivity, solubility, permeability, synthesis confidence, novelty, or model uncertainty. Do not treat docking score as experimental potency.

### Single-cell follow-up

Use donor, condition, or cluster as diversity group. Include donor balance and controls explicitly. Do not select cells as independent biological replicates when donors are the experimental unit.

### Literature evidence acquisition

Candidates may be full texts, datasets, or experiments. Cost may be retrieval or curation effort. Uncertainty must describe the decision-relevant evidence gap, not search-engine score.

### Simulation allocation

Candidates may be receptor states, ligand microstates, initial conditions, or parameter regimes. Use cost and resource caps; do not call multiple seeds independent experimental evidence.

## Search patterns

- `## Input contract`
- `## Selection method`
- `## Output contract`
- `## Required workflow`
- `## Failure handling`
- `## Common mistakes`

## Failure handling

| Failure | Required response |
| --- | --- |
| required property missing | stop; repair the candidate table or mark the objective non-required with rationale |
| controls unavailable | redesign the batch; do not proceed without the declared controls |
| controls exceed budget/batch | revise the approved experiment contract |
| uncertainty not calibrated | set uncertainty weight to zero or treat it as exploratory only |
| diversity grouping unavailable | define a reviewed grouping or set a conservative cap of one per candidate |
| costs incomparable | convert to one declared unit or separate budgets |
| no candidate fits | return an empty/infeasible decision record; do not relax constraints silently |
| candidate excluded after proposal | preserve the original proposal and create a revision/diff |
| source properties changed | invalidate the proposal fingerprint and regenerate |

## Common mistakes

- Calling the utility score predicted efficacy.
- Treating the information-gain proxy as a calibrated expectation.
- Allowing model uncertainty to dominate without calibration.
- Deriving diversity from names instead of an explicit method.
- Omitting controls to fit more candidates.
- Counting samples, cells, conformers, or seeds as independent units incorrectly.
- Changing objective weights after inspecting the selected list without preserving a revision.
- Executing the proposal without feasibility, safety, cost, and write approval.

## Evidence boundary

The planner makes multi-objective constraints and selection bias inspectable. It does not validate candidate measurements, infer similarity, calibrate uncertainty, estimate real information gain, execute experiments, or prove that the selected batch is scientifically optimal.
