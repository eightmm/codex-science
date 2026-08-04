# Finite decision-analysis runtime

Read this file before authoring or interpreting a `decision-analysis-v1` receipt. The runtime is dependency-free, deterministic, and bounded to finite one-stage decisions.

## Command

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/run_decision_analysis.py" \
  input.json \
  --output artifacts/run/decision-analysis.json \
  --report artifacts/run/decision-analysis.md
```

The command writes files atomically. Standard output contains only the output location; invalid contracts fail without producing a scientific conclusion.

## Input schema

```json
{
  "schema_version": 1,
  "analysis_id": "decision-example-v1",
  "claim_id": "claim-decision-example",
  "question": "Which candidate minimizes expected loss, and is the assay worth its cost?",
  "information_boundary": "Choose once, after observing at most one assay outcome.",
  "consequence_horizon": "Loss accumulated over the same 30-day horizon for every cell.",
  "state_model": "exogenous",
  "applicability": "The declared two-state model and listed candidates only.",
  "criterion": "bayes-risk",
  "criterion_rationale": "A recorded prior is available and loss is the decision scale.",
  "scale": {
    "kind": "loss",
    "unit": "loss-point",
    "risk_attitude": "encoded-in-loss"
  },
  "tie_tolerance": 1e-12,
  "actions": [
    {"id": "candidate-a", "label": "Candidate A"},
    {"id": "candidate-b", "label": "Candidate B"}
  ],
  "states": [
    {"id": "state-1", "label": "State 1", "prior": 0.6},
    {"id": "state-2", "label": "State 2", "prior": 0.4}
  ],
  "values": [
    {"action": "candidate-a", "state": "state-1", "value": 0},
    {"action": "candidate-a", "state": "state-2", "value": 8},
    {"action": "candidate-b", "state": "state-1", "value": 5},
    {"action": "candidate-b", "state": "state-2", "value": 1}
  ],
  "experiments": [
    {
      "id": "bounded-assay",
      "cost_in_scale_units": 0.5,
      "outcomes": [
        {"id": "positive", "likelihoods": {"state-1": 0.8, "state-2": 0.2}},
        {"id": "negative", "likelihoods": {"state-1": 0.2, "state-2": 0.8}}
      ]
    }
  ],
  "sensitivity": {
    "two_state_prior": {"state_id": "state-1", "minimum": 0, "maximum": 1}
  },
  "assumptions": ["The states are mutually exclusive and exhaustive for this comparison."]
}
```

IDs must be unique. `state_model` must be `exogenous`; action-dependent state probabilities require another model. Every value must use one consequence horizon and unit. The table must contain exactly one finite value for every action-state pair. Priors are all-or-none and must sum to one. For each experiment and state, likelihoods over all outcomes must sum to one. Experiment cost is expressed on the same scale as the table.

## Supported criteria

| Scale | Required declaration | Criteria |
| --- | --- | --- |
| `loss` | `encoded-in-loss` | `bayes-risk`, `minimax-loss`, `minimax-regret` |
| `utility` | `encoded-in-utility` | `expected-utility`, `minimax-regret` |
| `payoff` | `risk-neutral` | `expected-payoff`, `minimax-regret` |

For prior probabilities `p(s)` and table value `v(a,s)`, expected criteria use `sum_s p(s) v(a,s)`. Loss is minimized; utility and risk-neutral payoff are maximized. Pure minimax loss minimizes `max_s v(a,s)`. Regret is the state-wise distance from the best action in the declared direction, and minimax regret minimizes the maximum regret.

The receipt computes every criterion supported by the supplied scale and prior, but only the preregistered `criterion` controls the conditional action set. Differences between Bayes and minimax results are reported rather than reconciled automatically.

Weak dominance requires one action to be no worse in every state and strictly better in at least one state, within `tie_tolerance`. Dominated actions remain in the receipt for auditability but cannot become uniquely optimal under a compatible criterion.

## Information value

Experiments are allowed only with `bayes-risk`, `expected-utility`, or `expected-payoff` and a complete prior.

- EVPI compares the current optimal expected value with an oracle that reveals the state before action.
- Gross EVSI compares the current optimum with the preposterior optimum obtained from `P(outcome | state)`, Bayes' rule, and the outcome-specific optimal action.
- Net EVSI is gross EVSI minus `cost_in_scale_units`.

The runtime verifies `EVPI >= 0` and `0 <= EVSI <= EVPI` up to numeric tolerance. A zero-probability outcome is retained as `unreachable` and is not assigned a fabricated posterior. `EVPI < cost` rules out that experiment under the model; `EVPI > cost` is only an upper-bound screen, while actual value requires net EVSI.

## Prior sensitivity

`sensitivity.two_state_prior` is available only for two-state expected criteria. It varies the named state's prior over the declared interval, sets the other prior to its complement, finds action-score intersections, and reports only positive-width optimal regions and decision-relevant boundary ties. Crossings between actions that are never optimal are omitted. `decision-sensitive` means the interior-optimal policy changes within that range; a tie only at one exact boundary is not presented as a robust action reversal.

Do not choose the sensitivity range after finding a desired conclusion. For more than two states, supply preregistered scenarios and analyze them separately; the bounded runtime does not invent a path through a probability simplex.

## Receipt fields

The `decision-analysis-v1` receipt includes the normalized `problem`, criterion score tables, selected conditional action set, dominance and regret records, optional information value and outcome policy, optional prior sensitivity, applicability, fixed limitations, normalized-input SHA-256, and a full fingerprint. Receipt validation deterministically recomputes the analysis from the normalized problem.

`completed`, `multiple-optima`, and `decision-sensitive` are computational statuses. None means that the world model, causal evidence, utility elicitation, or authority to act has passed scientific review.

## Validation and failure handling

Reject rather than silently repair:

- incomplete or duplicate table cells;
- unknown action, state, outcome, or sensitivity IDs;
- non-finite values, negative experiment cost, or mixed scale units;
- partial priors or probabilities outside `[0,1]`;
- priors or state-conditional likelihoods that do not sum to one;
- payoff without `risk-neutral`, or utility/loss without an encoded preference declaration;
- a criterion incompatible with the scale;
- experiment valuation under a non-expected criterion;
- a prior-sensitivity request outside the supported two-state expected route;
- a modified receipt whose fingerprint or deterministic recomputation fails.

Review the probability and likelihood sources, causal assumptions, value elicitation, omitted actions and states, applicability, criterion rationale, sensitivity range, and information timing independently. Use `$science-provenance` for hashes and `$science-review` before using a material result.
