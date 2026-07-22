# Research design and statistical analysis

Read this file before `research-design-audit` or `statistical-analysis`. The commands write JSON artifacts; stdout contains only a short status message.

## Research-design input

```bash
uv run python scripts/validate_research_design.py design.input.json \
  --output artifacts/run/research-design.json \
  --require-clean
```

Required top-level fields:

```json
{
  "schema_version": 1,
  "design_id": "D1",
  "question": "...",
  "experimental_unit": "animal",
  "observational_unit": "cell",
  "outcome": {
    "name": "response",
    "measurement": "instrument and time point",
    "subjective": false
  },
  "estimand": {
    "population": "...",
    "contrast": "treatment minus control",
    "summary_measure": "mean difference",
    "causal": false
  },
  "assignment": {
    "type": "randomized",
    "mechanism": "blocked computer randomization",
    "allocation_concealment": true
  },
  "analysis": {
    "method": "cluster-aware model",
    "aggregation_unit": "animal",
    "cluster_adjustment": true
  },
  "primary_endpoints": [
    {"id": "primary", "decision_threshold": "prespecified interpretation rule"}
  ],
  "multiplicity": {"method": "none", "family_size": 1},
  "missing_data": {"strategy": "none-expected", "assumptions": "..."},
  "exclusions": {"prespecified": true, "criteria": ["..."]},
  "stopping": {"planned_looks": 1, "decision_rule": "one final analysis"},
  "sample_size": {"planned": 20, "rationale": "precision, power, or feasibility rationale"},
  "sensitivity_analyses": ["..."],
  "identification_assumptions": [],
  "blinding": {"outcome_assessor": true},
  "locked_before_outcomes": true
}
```

Assignment types are `randomized`, `observational`, `quasi-experimental`, `simulation`, and `descriptive`. A causal estimand needs explicit identification assumptions. Observational causal work also needs `analysis.confounding_strategy`.

The audit detects:

- observations treated as independent below the experimental unit;
- outcome-dependent design changes;
- understated multiplicity families;
- optional stopping without a decision rule or alpha spending;
- post-hoc or missing exclusions;
- missing sample-size rationale;
- unstated missingness assumptions;
- causal identification and confounding gaps;
- missing randomization mechanism or allocation concealment;
- unblinded subjective outcomes;
- missing sensitivity analysis.

`--require-clean` exits nonzero for deterministic findings. A clean design is a prerequisite, not evidence that the experiment is scientifically adequate.

## Statistical-analysis input

The built-in dependency-free runtime is deliberately bounded to independent or paired two-group contrasts. Use a domain-specific model outside this runtime when censoring, complex hierarchy, longitudinal dependence, survey weights, generalized outcomes, or adaptive designs are material; still retain the same research-design and artifact contracts.

```bash
uv run python scripts/run_statistical_analysis.py analysis.input.json \
  --output artifacts/run/statistical-analysis.json
```

```json
{
  "schema_version": 1,
  "analysis_id": "A1",
  "claim_id": "C1",
  "design_id": "D1",
  "analysis_type": "independent",
  "group_labels": ["control", "treatment"],
  "estimand": "mean-difference",
  "alternative": "two-sided",
  "confidence_level": 0.95,
  "seed": 20260722,
  "bootstrap_replicates": 5000,
  "permutation_replicates": 10000,
  "within_unit_aggregation": "mean",
  "data": [
    {"unit_id": "A1", "group": "control", "value": 1.2},
    {"unit_id": "B1", "group": "treatment", "value": 2.1}
  ],
  "hypotheses": []
}
```

For paired analysis, each row also carries `pair_id`. Repeated readings with the same `(group, unit_id)` are reduced by the declared mean or median before inference. This prevents technical readings from silently increasing the experimental-unit count.

Supported estimands:

- `mean-difference`
- `median-difference`

Supported alternatives:

- `two-sided`
- `greater`
- `less`

The runtime reports:

- raw observations, missing counts, independent-unit counts, and aggregated duplicates;
- effect estimate and a standardized estimate when defined;
- deterministic percentile-bootstrap interval;
- exact randomization or exact paired sign-flip p-value when the state space is small;
- seeded Monte Carlo randomization otherwise;
- optional Benjamini-Hochberg q-values for supplied p-values.

## Multiplicity

The built-in primary contrast is one hypothesis. To adjust a larger externally computed family, supply:

```json
"hypotheses": [
  {"id": "H1", "p_value": 0.01},
  {"id": "H2", "p_value": 0.04}
]
```

The output preserves IDs and adds BH q-values. This does not retroactively define the correct scientific family; the family must be declared in the design.

## Interpretation boundary

- Report effect, interval, unit count, missingness, and design before the p-value.
- The randomization p-value assumes the assignment or exchangeability model encoded by the design.
- A bootstrap interval can be poor for small, skewed, boundary, or multimodal samples.
- Statistical significance is not practical importance, replication, mechanism, or causality.
- `status: completed` means computation completed. It is intentionally not `passed`.
- Do not create a causal claim when `estimand.causal` is false or identification assumptions are absent.

## Failure handling

Stop and revise the design or use a domain-specific method when:

- a group has no independent units;
- a paired record lacks `pair_id`;
- sample size is confused with row count;
- the requested family or model is outside the two-group runtime;
- the seed, confidence level, or replication limits are missing or invalid;
- missing data are silently dropped contrary to the design;
- outcome inspection preceded a supposedly confirmatory design.
