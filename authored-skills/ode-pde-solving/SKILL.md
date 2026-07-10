---
name: ode-pde-solving
description: "Classify, solve, approximate, and verify ordinary and partial differential equations with explicit domains, initial or boundary data, well-posedness, residuals, and convergence checks. Use for IVPs, BVPs, dynamical systems, eigenvalue problems, Fourier methods, diffusion, waves, Laplace or Poisson equations, and nonlinear differential equations."
license: MIT
---

# ODE and PDE Solving

## Formulate

1. State independent/dependent variables, domain, parameters, units, equation order,
   initial/boundary data, regularity, and requested observable.
2. Classify linearity, autonomy, homogeneity, stiffness, conservation form, and singular points.
3. For PDEs, classify type where applicable and identify spatial/temporal dimensions,
   boundary geometry, and compatibility conditions.
4. Ask whether existence, uniqueness, and continuous dependence are supported by the assumptions.

## Choose an analytic route

- First-order ODE: separation, integrating factor, exact equation, substitution, or phase line.
- Higher-order linear ODE: characteristic roots, variation of parameters, Green functions,
  Laplace transform, or series methods.
- Systems: matrix exponential, eigenstructure, phase portrait, invariant manifolds, or linearization.
- PDE: characteristics, separation of variables, Fourier transform/series, eigenfunction expansion,
  similarity variables, or Green functions.

State transform conventions and convergence assumptions. Enforce every initial and boundary condition.

## Choose a numerical route

1. Define the discretization, mesh, time step, solver tolerances, and boundary implementation.
2. Match the method to stiffness, conservation, oscillation, discontinuity, and geometry.
3. Establish consistency and expected order; check stability restrictions before a full run.
4. Run at least two refinements and compare the requested observable, not only the state vector.
5. Use `$cx-numerical-analysis-error-control` for conditioning, truncation, and solver-error analysis.

## Verify

- Substitute analytic solutions into the differential operator and data.
- Compute a normalized residual for numerical solutions.
- Check initial/boundary conditions separately from the interior residual.
- Test conserved quantities, positivity, maximum principles, energy estimates, or monotonicity.
- Compare refinement ratios with the expected convergence order.
- Compare against a closed-form solution, manufactured solution, or independently implemented baseline.
- Test long-time, steady-state, zero-source, symmetry, and parameter-limit behavior.

Do not infer uniqueness from one numerical trajectory. Distinguish discretization instability,
ill-conditioning, chaotic sensitivity, and model uncertainty.

## Source basis

The workflow is independently synthesized from Lebl's *Notes on Diffy Qs* and the open numerical
texts listed in `../../docs/TEXTBOOK_SOURCES.md`.
