---
name: mathematical-problem-execution
description: "Drive a concrete mathematics problem from precise statement through method selection, derivation or proof, symbolic and numerical checks, edge cases, and a verified final result. Use for multi-step pure or applied mathematics problems where the user expects an actual solution rather than a formula lookup."
license: MIT
---

# Mathematical Problem Execution

Produce a checkable solution, not a plausible-looking derivation.

## Specify

1. Restate the target, domain, quantifiers, givens, unknowns, regularity assumptions,
   conventions, and requested output.
2. Separate facts supplied by the problem from assumptions introduced to make it
   solvable. Surface any missing condition that changes uniqueness or existence.
3. Classify the task as proof/refutation, exact computation, approximation,
   optimization, differential equation, inverse problem, or mathematical model.
4. Write a small solution plan and identify a second, independent check before
   doing the main derivation.

## Route

- Load `$cx-proof-and-counterexample` for theorem and refutation tasks.
- Load `$cx-linear-algebra-problem-solving` for systems, spaces, spectra, and factorizations.
- Load `$cx-ode-pde-solving` for differential equations and boundary-value problems.
- Load `$cx-numerical-analysis-error-control` for floating-point or discretized results.
- Load `$cx-dimensional-analysis-units` when physical quantities or scales appear.
- Use `kdense-sympy` only as a computational aid; do not treat computer algebra output
  as a proof without checking domains, branches, and assumptions.

## Solve

1. Work from definitions and state every theorem with the hypotheses actually used.
2. Prefer exact arithmetic and symbolic structure until approximation is necessary.
3. Track domains through division, roots, logarithms, inverse functions, coordinate
   changes, and limit interchanges.
4. Keep equivalent transformations separate from one-way implications.
5. For an approximation, state the expansion parameter, retained order, neglected
   terms, and expected validity region before computing.
6. For a model, distinguish mathematical consequences from empirical assumptions.

## Verify

Require at least two applicable checks:

- substitute the result into the original statement;
- derive it by an independent representation or method;
- test boundary, singular, symmetric, and low-dimensional cases;
- compare exact and high-precision numerical evaluations at nontrivial points;
- check monotonicity, convexity, sign, bounds, invariants, or conservation laws;
- estimate residual, conditioning, truncation, roundoff, and approximation error.

Random examples can falsify a universal claim but cannot prove one. Report non-uniqueness,
conditional results, and unresolved proof obligations explicitly.

## Deliver

Give the result first, then assumptions, derivation, checks, and limitations. Preserve
reproducible computations with `$science-provenance` and use `$science-review` when the
answer supports a scientific claim.

## Source basis

This workflow is an original synthesis of the openly licensed mathematical texts recorded
in `../../docs/TEXTBOOK_SOURCES.md`; it does not reproduce their prose or exercises.
