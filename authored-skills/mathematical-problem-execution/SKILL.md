---
name: mathematical-problem-execution
description: "Drive a concrete pure or applied mathematics problem from exact statement through method selection, derivation, proof or computation, executable checks, error control, edge cases, and machine-readable evidence without promoting bounded tests to proofs."
license: MIT
---

# Mathematical Problem Execution

## Decision contract

Restate the target, domain, quantifiers, givens, unknowns, regularity assumptions, conventions, requested output, and acceptable evidence level. Separate supplied facts from introduced assumptions. Classify the task as proof/refutation, exact computation, approximation, optimization, differential equation, inverse problem, or mathematical model.

Give every material claim a stable ID and decide which independent check would falsify it before doing the main derivation.

## Reference usage

Read [the problem execution and routing contract](references/problem-execution-runtime.md) before selecting an executable check, assigning a proof status, or packaging a result. It maps problem classes to quantitative commands and defines evidence levels, required cross-checks, and stop conditions.

Record material reference hashes. Preserve computations with `$science-provenance` and use `$science-review` when the result supports a scientific, engineering, or published mathematical claim.

## Workflow

1. Specify the exact statement and identify missing conditions that change existence, uniqueness, or equivalence.
2. Route to `$cx-proof-and-counterexample`, `$cx-linear-algebra-problem-solving`, `$cx-ode-pde-solving`, `$cx-numerical-analysis-error-control`, `$cx-dimensional-analysis-units`, `$cx-experimental-uncertainty-propagation`, or `$cx-formal-theorem-proving` as needed.
3. Work from definitions and state every theorem with the hypotheses actually used.
4. Prefer exact arithmetic and symbolic structure until approximation is necessary. Track branches, domains, one-way implications, and lost solutions.
5. Use bounded CLIs only for their documented purpose: counterexample, statistics, numerical verification, dimensions, uncertainty, or formal checking.
6. Require at least two applicable checks: substitution, independent derivation, limiting cases, exact versus high-precision evaluation, invariant, residual, condition estimate, or formal kernel check.
7. Package claims and receipts with the narrowest supported statuses and explicit limitations.

## Outputs

- exact problem statement, assumptions, and claim IDs;
- derivation or proof with theorem dependencies;
- applicable `mathematical-claim`, `counterexample-search`, `proof-obligation-graph`, `proof-receipt`, `numerical-verification`, `dimension-check`, or `uncertainty-propagation` artifacts;
- independent checks and failed cases;
- final result, validity region, error or uncertainty, and unresolved obligations;
- manifest and review receipt for material work.

## Boundaries

- Computer algebra output is not proof until domains, branches, assumptions, and transformations are checked.
- Random examples can falsify a universal claim but cannot prove one.
- Numerical agreement does not establish exact equality or general convergence.
- A model consequence is conditional on the model assumptions and is not empirical evidence by itself.
- Do not hide non-uniqueness, singular cases, lost roots, or failed proof obligations.
- Stop and return `conditional`, `tested`, `unavailable`, or a corrected theorem rather than inventing missing assumptions or unsupported digits.

## Source basis

This workflow is an original synthesis of the openly licensed mathematical texts recorded in `../../docs/TEXTBOOK_SOURCES.md`; it does not reproduce their prose or exercises.
