---
name: optimization-variational-methods
description: "Formulate, solve, and verify finite-dimensional optimization and calculus-of-variations problems. Use for convex programs, constrained extrema, KKT systems, duality, optimal control, Euler-Lagrange equations, and numerical optimization."
license: MIT
---

# Optimization and Variational Methods

## Formulate the problem

Write the objective, variables or admissible functions, domain, equality and inequality constraints,
boundary conditions, regularity class, units, and whether the task seeks a local or global optimum. Remove
arbitrary scale or gauge freedom. Check feasibility and existence before choosing an algorithm.

## Select a route

- For smooth unconstrained problems, derive first- and second-order conditions and inspect curvature.
- For convex problems, state the convexity argument and a constraint qualification before using KKT sufficiency.
- For constrained nonconvex problems, use KKT as necessary conditions and compare multiple feasible starts.
- For functionals, derive the first variation, natural boundary terms, and Euler-Lagrange equations.
- Use a dual formulation when it supplies a bound, decomposition, or numerical advantage.

## Solve

Scale variables and residuals, choose tolerances tied to the scientific question, and retain iteration history.
For discretized functionals, distinguish discretization error from optimizer termination. Do not infer a global
optimum from a single local solver run unless a theorem or valid bound supports it.

## Verify

- Check feasibility, stationarity, complementary slackness, and primal-dual gap where applicable.
- Compare analytic derivatives with finite differences or automatic differentiation at test points.
- Test perturbations around the candidate and verify second-order or convexity conditions.
- Refine discretization and solver tolerances independently; inspect sensitivity to initialization and scaling.
- Substitute the result into the original objective and constraints, not only transformed equations.

## Deliver

Report formulation, existence or convexity conditions, solver and initialization, residuals, bounds, sensitivity,
and whether the conclusion is local, global, or heuristic.

## Source basis

Original synthesis informed by open calculus-of-variations and numerical-analysis sources recorded in
`../../docs/TEXTBOOK_SOURCES.md`.
