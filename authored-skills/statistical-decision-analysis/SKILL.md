---
name: statistical-decision-analysis
description: "Compare finite actions under uncertainty with explicit states, loss, utility or risk-neutral payoff, priors, experiment likelihoods, and a declared decision criterion. Use for Bayes risk, expected utility or payoff, pure-action minimax, minimax regret, dominance, posterior decision policies, EVPI/EVSI, experiment-cost decisions, and prior-threshold sensitivity; do not use for ordinary statistical testing, causal identification, strategic games, or MDP/POMDP/RL planning."
license: MIT
---

# Statistical Decision Analysis

Turn a finite decision table into a conditional, reproducible policy without hiding the probability, preference, information, or criterion assumptions.

## Decision contract

Before calculation, record the decision question, claim ID, action set, mutually exclusive and exhaustive exogenous states, information available when the action is chosen, common consequence horizon, consequence scale and unit, complete action-by-state values, criterion and rationale, tie tolerance, applicability domain, and assumptions.

Use exactly one primary scale:

- `loss` with `encoded-in-loss` and minimization;
- `utility` with `encoded-in-utility` and maximization;
- `payoff` only with explicit `risk-neutral` treatment and maximization.

Do not silently treat money as utility, infer a prior or likelihood, scalarize incomparable outcomes, select Bayes versus minimax after seeing the preferred answer, or break an optimal tie arbitrarily.

## Reference usage

Read [the finite decision-analysis runtime](references/finite-decision-analysis.md) before authoring a `decision-analysis` input or interpreting EVPI, EVSI, regret, dominance, or prior sensitivity. It defines the exact schema, supported criteria, formulas, command, validation invariants, and interpretation limits.

For material work, record the reference hash with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/reference_lookup.py" "<plugin-root>/authored-skills/statistical-decision-analysis" --route decision-analysis --receipt-dir artifacts/run/reference-uses --claim CLAIM_ID`, then preserve the input, receipt, report, and reference-use receipt with `$science-provenance`.

## Workflow

1. Separate controllable actions from uncertain states and consequences. Confirm that the state set is exhaustive for the declared applicability domain.
2. Choose and justify one supported primary criterion before computation. Retain other computed criteria as comparisons, not interchangeable recommendations.
3. Express every experiment as finite outcomes with a complete `P(outcome | state)` table and its cost in the same loss, utility, or payoff units.
4. Author the bounded JSON contract and run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/run_decision_analysis.py" INPUT --output decision-analysis.json --report decision-analysis.md`.
5. Inspect dominance, ties, criterion conflicts, posterior outcome policies, EVPI/EVSI bounds, net experiment value, and prior ranges where the preferred action changes.
6. If plausible priors or values cross a decision boundary, report `decision-sensitive` and the conditional regions instead of one unconditional action.
7. Package the normalized problem, receipt, human report, source assumptions, and any upstream probability or causal evidence, then run `$science-review` for a material decision.

## Outputs

- `decision-analysis-v1` with normalized inputs, hashes, criterion score tables, optimal action set, dominance and regret tables, optional posterior policies, EVPI/EVSI, cost-adjusted information value, prior sensitivity, applicability, status, and limitations;
- a human-first `decision-analysis.md` that states the conditional action set, criterion conflicts, information value, decision boundaries, and interpretation boundary;
- upstream probability, likelihood, causal-effect, and utility-elicitation evidence referenced rather than re-created;
- manifest and independent review receipt through `$science-provenance` and `$science-review`.

## Boundaries

- The runtime supports finite, one-stage tables and pure-action minimax only. It does not solve continuous decisions, randomized minimax policies, optimal stopping, MDPs, POMDPs, RL, or strategic multi-agent games.
- EVPI is an upper bound on the gross value of a modeled experiment. `EVPI > cost` does not establish that a particular experiment is worthwhile; net EVSI requires its likelihood model.
- Expected payoff is valid only under the declared risk-neutral assumption. Utility and loss elicitation remain substantive inputs, not facts validated by the solver.
- A decision receipt cannot identify causal effects, justify priors, validate likelihood calibration, or make clinical, legal, financial, safety-critical, or policy choices on a person's behalf.
- Stop on an incomplete matrix, mixed units, non-normalized probability model, unspecified criterion, incomparable consequences, unmodeled material action, or missing authority for a consequential action.
- Keep multiple optima and sensitivity visible. A deterministic computation is not an independent review or a guarantee that the modeled action is correct in the world.

## Source basis

Original synthesis informed by the openly licensed and linked decision-theory and value-of-information sources recorded in `../../docs/TEXTBOOK_SOURCES.md`. The user-supplied 2003 draft is retained only as a scoping reference because no redistribution or adaptation license was identified; no prose, figures, formulas, or worked examples are copied from it.
