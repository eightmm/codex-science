---
name: quantitative-research
description: "Execute auditable quantitative research across preregistered study design, statistical inference, numerical verification, dimensional analysis, uncertainty propagation, counterexample search, and formal proof. Use when a scientific or mathematical question needs actual computation and machine-readable evidence rather than only explanation."
license: MIT
---

# Quantitative Research

Turn a mathematical or scientific question into evidence lanes whose conclusions cannot silently exceed their checks.

## Decision contract

Before computation, record:

- the exact question and stable claim IDs;
- population or mathematical domain, experimental unit, observational unit, variables, units, assumptions, and quantifiers;
- whether the intended result is descriptive, statistical, causal, numerical, finite exhaustive, deductive, or kernel-checked;
- primary estimand or theorem statement, decision threshold, stopping rule, and falsifier;
- which result would remain only `tested`, which may become `proved-finite`, and which requires a deductive or formal proof receipt.

Do not select a test, solver tolerance, search domain, or proof statement after seeing the desired conclusion without recording the change as exploratory.

## Reference usage

Inspect `references/index.json` and load only the entries required for the selected lanes.

- Read [research design and statistics](references/research-design-and-statistics.md) before `research-design-audit` or `statistical-analysis`.
- Read [mathematical claims and proof levels](references/mathematical-proof-and-counterexample.md) before `counterexample-search`, `proof-obligation-authoring`, or any `proved-*` status.
- Read [numerical, dimensional, and uncertainty verification](references/numerical-units-uncertainty.md) before `numerical-verification`, `dimension-check`, or `uncertainty-propagation`.
- Read [formal proof execution](references/formal-proof-runtime.md) before executing Lean or accepting a kernel-check receipt.
- Read [artifact and review handoff](references/artifact-and-review.md) before packaging a claim-bearing quantitative run.

For a material computation or claim, record the loaded reference hashes with `scripts/reference_lookup.py`. Do not infer CLI arguments, result schemas, evidence levels, or proof semantics from command names.

## Workflow

1. **Specify.** Normalize assumptions, quantifiers, variables, units, experimental units, outcomes, estimands, and claim status. Give each material claim an ID.
2. **Preregister.** For empirical work, author a `research-design` input and run `scripts/validate_research_design.py --require-clean` before outcome-driven analysis.
3. **Route evidence lanes.** Use `$cx-statistical-inference-experimental-design`, `$cx-proof-and-counterexample`, `$cx-formal-theorem-proving`, `$cx-numerical-analysis-error-control`, `$cx-dimensional-analysis-units`, and `$cx-experimental-uncertainty-propagation` as applicable.
4. **Execute.** Use only the bounded CLIs described in the selected references. Write results to files; never paste a large result stream into the conversation.
5. **Cross-check.** Require independent checks appropriate to the lane: exact randomization, sensitivity analysis, refinement order, residual, invariant, unit balance, covariance-aware propagation, counterexample verification, proof obligations, or kernel execution.
6. **Package.** Save quantitative sidecars under one hash-validated manifest with `$science-provenance`.
7. **Review.** Run `$science-review`. A statistical computation, numerical convergence trace, symbolic simplification, or bounded search cannot by itself justify a general proof or empirical causal claim.

## Outputs

A complete run uses the applicable machine-readable artifacts:

- `research-design`
- `statistical-analysis`
- `mathematical-claim`
- `counterexample-search`
- `proof-obligation-graph`
- `proof-receipt`
- `formal-proof-check`
- `numerical-verification`
- `dimension-check`
- `uncertainty-propagation`
- report, manifest, environment, execution record, and independent review receipt

Every receipt records hashes, explicit limitations, and a status whose meaning is narrower than the scientific conclusion.

## Boundaries

- A p-value is not effect size, practical importance, replication, or causality.
- Technical observations do not increase independent sample size.
- Failure to find a counterexample is not proof unless the declared finite exact domain was exhausted.
- Finite exhaustive proof does not automatically generalize beyond that finite domain.
- Computer algebra, random testing, numerical agreement, and convergence plots are not deductive proofs.
- Dimensional consistency is necessary but not sufficient for a correct physical equation.
- Monte Carlo uncertainty is conditional on the declared distributions and covariance model.
- A formal proof receipt covers the exact hashed theorem statement and trusted kernel environment, not an informal claim that merely resembles it.
- Stop rather than weaken assumptions, bounds, review, or evidence semantics to obtain a desired answer.
