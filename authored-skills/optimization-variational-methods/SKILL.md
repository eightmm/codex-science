---
name: optimization-variational-methods
description: "Formulate, solve, and verify finite-dimensional optimization and calculus-of-variations problems. Use for convex programs, constrained extrema, KKT systems, duality, optimal control, Euler-Lagrange equations, and numerical optimization."
license: MIT
---

# Optimization and Variational Methods

## Decision contract
State variables or admissible functions, objective, domain, constraints, units, and whether a local or global optimum is sought. State feasibility and existence assumptions before selecting an optimization method. Solver termination is evidence about an algorithm run, not proof of optimality.

## Reference usage
Read [references/optimization-evidence.md](references/optimization-evidence.md) before using KKT conditions, making a global-optimum claim, or deriving Euler-Lagrange equations and second variations. It defines regularity, conditioning, and numerical verification requirements.

## Workflow
1. Write the objective, variables or admissible functions, domain, equality/inequality constraints, boundary conditions, regularity class, units, and local/global target; record normalized formulation and claim.
2. Check feasibility and existence conditions before solving; record constraint qualification candidates and any assumptions not established.
3. Assess convexity or curvature, remove arbitrary scale or gauge freedom, and scale variables and residuals; for smooth unconstrained problems derive first- and second-order conditions, and for nonconvex constrained problems treat KKT as necessary only unless stronger assumptions or bounds apply, recording the argument.
4. For constrained problems, verify the applicable constraint qualification and KKT residuals; for functionals derive the first variation, boundary terms, and Euler-Lagrange equations, recording each condition.
5. Select and run a solver with tolerances tied to the scientific question, scaling, starts, discretization, and stopping rule; consider a dual formulation when it supplies a bound, decomposition, or numerical advantage. Use multiple feasible starts for nonconvex problems and preserve iteration histories and failures.
6. Verify gradients by finite differences at representative points, feasibility, stationarity, complementarity, duality gap or valid bound where applicable; perturb candidates to inspect local curvature, and for functionals check boundary conditions and second variation.
7. Vary starts, scaling, finite-difference step, solver tolerance, mesh/resolution, and model parameters; report changes that affect feasibility, candidate value, or local/global classification.
8. Assign claims supported, contradicted, inconclusive, or unavailable; report uncertainty, applicability domain, local/global/heuristic status, and smallest falsifiable next action; verify artifacts and hand off with `$science-provenance` and `$science-review`.

## Outputs
Return `optimization-evidence-v1` with required fields: claim identifier (`claim_id`), claim class (`claim_class`), status (`status`: supported, contradicted, inconclusive, or unavailable), problem formulation (`formulation`), feasibility and existence assessment (`feasibility_and_existence`), convexity or curvature assessment (`convexity_or_curvature`), constraint qualification (`constraint_qualification`), solver and initialization (`solver_and_initialization`), optimality residuals or bounds (`optimality_residuals_or_bounds`), uncertainty (`uncertainty`), sensitivity results (`sensitivity`), applicability domain (`applicability_domain`), and evidence artifact paths and hashes (`evidence_artifacts`). Include normalized inputs and assumptions, commands or derivations, preserved failures and nulls, and the smallest falsifiable next action. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A local solver result is not a global optimum absent a theorem or valid bound; optimizer termination does not establish discretization accuracy. Stop global claims when feasibility, existence, or constraint qualification is unsupported. A discretized Euler-Lagrange solution inherits approximation and boundary-condition error and does not alone establish a minimizer.

## Source basis

Original synthesis informed by open calculus-of-variations and numerical-analysis sources recorded in
`../../docs/TEXTBOOK_SOURCES.md`.
