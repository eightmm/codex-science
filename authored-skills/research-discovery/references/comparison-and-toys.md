# Acceptance and comparison protocol

## CPU scenarios

The checked fixture uses inexpensive deterministic calculations and preserves
the same separation expected from a real cycle.

1. **Information loss versus capacity.** Construct labels that are identical
   under a deliberately lossy representation. Increase model capacity under
   that representation and then change the representation while holding the
   evaluator, training budget, and parameter accounting visible. The expected
   conclusion is that capacity cannot recover information absent from the
   representation; this is a software-contract check, not a model theorem.
2. **Implementation failure and repair.** Inject a shape or execution failure
   after preregistration. Classify the attempt as invalid measurement, repair
   only the declared code path, rerun under the same protected evaluation, and
   preserve the failed receipt. A failure must not be counted as evidence
   against the hypothesis.
3. **Honest inconclusive termination.** Give two hypotheses predictions within
   the declared measurement resolution or remove enough budget to separate
   them. The cycle must terminate as inconclusive with the unresolved
   prediction pair and next action, never manufacture a winner.

The generated acceptance input is
[`examples/research-discovery/input.json`](../../../examples/research-discovery/input.json)
and the acceptance test is
[`tests/test_research_discovery_acceptance.py`](../../../tests/test_research_discovery_acceptance.py).

## P4 comparison protocol

Compare ordinary Codex, the prior fixed workflow, and RDL only in matched
fresh tasks. Fix the model/version, tool set, input question, data access,
compute and wall-clock budget, evaluator/split/baseline/metric, stopping rule,
reviewer procedure, and artifact schema. Randomize or counterbalance task order
where practical and preregister primary outcomes such as valid supported
methods, correct failure classification, useful revision, cost, and time.
Report nulls, invalid runs, reviewer disagreements, and attrition. Separate
idea quality, implementation success, scientific result, novelty, and review
quality. Do not use the deterministic fixture as a P4 result and do not claim
research-capability improvement until actual matched runs are complete.

## Limitations

The scenarios are CPU-only, tiny, deterministic, and designed to expose state
and evidence-contract defects. They do not test GPU behavior, domain-specific
validity, real scientific novelty, broad literature coverage, or the ability of
an agent to originate useful hypotheses. External evaluator isolation and
independent review remain operational requirements for a real study.
