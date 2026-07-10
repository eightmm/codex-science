---
name: numerical-analysis-error-control
description: "Design and audit numerical computations by separating problem conditioning from algorithmic stability and quantifying discretization, truncation, iteration, floating-point, and sampling errors. Use for root finding, interpolation, quadrature, numerical linear algebra, ODE/PDE solvers, optimization, and any result sensitive to tolerances or precision."
license: MIT
---

# Numerical Analysis Error Control

## Define the numerical claim

1. State the mathematical target, input uncertainty, output observable, requested tolerance,
   norm, and reference scale.
2. Identify all error sources: model, data, discretization, truncation, iteration, roundoff,
   stochastic sampling, and implementation.
3. Separate conditioning of the mathematical problem from stability of the chosen algorithm.
4. Predict expected convergence order and failure modes before running refinements.

## Design the computation

- Scale variables and avoid subtractive cancellation or overflow/underflow.
- Use bracketing for guaranteed scalar roots; use open methods only with basin and derivative checks.
- Prefer stable factorizations over explicit inverses and normal equations.
- Choose interpolation nodes and basis to control oscillation and conditioning.
- Match quadrature to smoothness, singularity, and oscillation.
- Match time integrators to stiffness, conservation, and stability-region requirements.
- Use absolute and relative tolerances tied to the physical or mathematical output scale.

## Establish a reference

Use one or more of:

- exact solution or identity;
- higher precision arithmetic;
- finer mesh/order with demonstrated asymptotic convergence;
- independent algorithm or implementation;
- interval/bound enclosure;
- manufactured solution with known forcing.

Do not use the same implementation at slightly tighter tolerance as the only reference.

## Measure error

1. Report absolute and scale-aware relative errors in a declared norm.
2. Run at least three resolutions when estimating convergence order.
3. Check residual and backward error; distinguish them from forward error.
4. Perturb inputs to estimate sensitivity and compare it with the condition estimate.
5. Repeat stochastic calculations with independent seeds and report Monte Carlo uncertainty.
6. Demonstrate that the reported digits are stable under reasonable precision/tolerance changes.

## Stop or downgrade the claim

Stop when the refinement sequence is not asymptotic, conservation or positivity fails, the
reference disagrees, the condition number makes the requested accuracy unattainable, or the error
budget is dominated by unknown model/data error. Report a bound or qualitative conclusion instead
of unsupported digits.

## Source basis

This error-control workflow is an original synthesis informed by Brin's *Tea Time Numerical
Analysis* and the CC BY numerical PDE text recorded in `../../docs/TEXTBOOK_SOURCES.md`.
