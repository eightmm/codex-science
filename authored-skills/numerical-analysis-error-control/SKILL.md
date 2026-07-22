---
name: numerical-analysis-error-control
description: "Design and audit numerical computations by separating conditioning, stability, discretization, iteration, floating-point, sampling, and model errors, with executable refinement, residual, invariant, precision, and cross-method verification receipts."
license: MIT
---

# Numerical Analysis Error Control

## Decision contract

State the mathematical target, observable, norm, reference scale, requested accuracy, input uncertainty, solver precision, tolerances, expected convergence order, invariant or conservation conditions, and intended validity range before refinement. Separate model, data, discretization, truncation, iteration, roundoff, stochastic, and implementation errors.

Do not use tighter tolerance in the same implementation as the only reference.

## Reference usage

Read [the numerical verification runtime](references/numerical-verification-runtime.md) before `numerical-verification` or making a convergence, residual, invariant, or stable-digit claim. It defines refinement ordering, required levels, threshold fields, cross-method uncertainty, exact output semantics, and failure conditions.

Preserve inputs, code, environment, refinements, and receipts with `$science-provenance`, then use `$science-review` for material scientific interpretation.

## Workflow

1. Predict conditioning, stability restrictions, convergence order, invariants, and likely failure modes.
2. Choose a reference from exact solutions, manufactured solutions, independent implementations, interval bounds, or a demonstrated higher-accuracy method.
3. Run at least three refinement levels for an order claim and retain failed levels.
4. Record errors or reference value, residuals, invariants, precision, absolute and relative tolerances, and cross-method estimates with uncertainties.
5. Run `scripts/verify_numerical_result.py --require-clean`.
6. Perturb tolerances, precision, inputs, grids, and algorithm where the claim depends on them.
7. Report only digits and validity supported by the error budget and verification receipt.

## Outputs

- `numerical-verification` receipt with ordered refinements, observed order, residual, invariant, solver, and cross-method findings;
- reference or manufactured-solution record;
- conditioning and stability discussion;
- input, code, environment, and seed hashes;
- claim status and limitations;
- independent review receipt for claim-bearing results.

## Boundaries

- Residual, backward error, forward error, discretization error, and model discrepancy are different quantities.
- Small residual does not imply small forward error for an ill-conditioned problem.
- Agreement between two implementations is not independent evidence when they share code, discretization, data, or assumptions.
- Observed order on a finite range does not prove asymptotic convergence.
- Solver tolerance is not a discretization-error estimate.
- Stop or downgrade when refinement is non-asymptotic, invariants fail, the reference disagrees, conditioning makes requested accuracy unattainable, or unknown model/data error dominates.

## Source basis

This error-control workflow is an original synthesis informed by Brin's *Tea Time Numerical Analysis* and the CC BY numerical PDE text recorded in `../../docs/TEXTBOOK_SOURCES.md`.
