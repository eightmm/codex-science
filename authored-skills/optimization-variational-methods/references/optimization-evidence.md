# Optimization and variational evidence

## Claim semantics

- **Numerical candidate:** a solver returned a point or function satisfying its stopping rule. Report it as a candidate with residuals and scaling, not an optimum proof.
- **Feasibility:** verify original constraints with declared tolerances and units. Feasibility in transformed or penalized coordinates is not automatically feasibility of the original problem.
- **KKT point:** stationarity, primal feasibility, dual feasibility, and complementary slackness are necessary only under an appropriate constraint qualification for the stated problem. They are sufficient for global optimality under convexity and the relevant assumptions, not generally for nonconvex problems.
- **Local optimum:** use applicable second-order conditions on the feasible tangent/critical directions or a justified local theorem. A positive Hessian on the ambient space may not answer the constrained question.
- **Global optimum:** support with convexity plus valid sufficiency conditions, a certified bound/gap, exhaustive finite search, or another theorem matching the domain. Multi-start agreement is heuristic evidence, not a global certificate.
- **Euler-Lagrange stationary function:** derive first variation and natural or fixed boundary conditions in the stated admissible class. A stationary function is not necessarily a minimizer; a second-variation test is local and requires regularity and boundary assumptions.
- **Discretized solution:** distinguish optimizer termination from discretization error. Mesh refinement and consistency evidence are needed before a continuous-functional claim.

## Source dependencies and independence

Record exact formulation, units, data and parameter versions, variable transforms, constraint scaling, solver and library version, tolerances, initialization, derivative implementation, discretization, quadrature, and boundary conditions. Pin releases or commits for mutable software. Preserve random seeds for stochastic algorithms.

Gradient checks are not independent when both paths share the same derivative code. An automatic-differentiation result and a solver using that same graph share implementation risk; finite differences provide a separate numerical check but are themselves step- and conditioning-sensitive. Multiple starts share the same objective, constraints, solver, and local landscape; do not count them as independent proof. Record shared preprocessing, fitted parameters, and data.

## Uncertainty

Separate data/model uncertainty, stochastic optimization variability, derivative approximation error, feasibility tolerance, solver optimality gap, and discretization error. Report objective and constraint residuals with units/scales, start-to-start variation, and bounds where available. Retain unsuccessful starts and explain nonconvergence. If a global gap or second-order condition is unavailable, state that explicitly rather than translating solver confidence into proof.

## Domain-specific controls

- Test a small convex quadratic with known solution and constraints to check objective sign, gradient, constraint orientation, KKT residual, and reported gap.
- Verify analytic or automatic gradients against centered finite differences over more than one step size; use points away from nonsmooth kinks and separately identify nonsmooth regions.
- Re-evaluate the returned candidate in the original unscaled objective and constraints.
- For constrained methods, include an active-boundary case and a deliberately infeasible start when supported; check the solver does not label feasibility based only on a penalty objective.
- For variational derivations, test a simple Lagrangian with known Euler-Lagrange equation and verify boundary terms under fixed and free endpoint conditions.
- For a second variation, use a known convex functional as a positive control and a saddle or non-minimizing stationary point as a negative control when the model permits.

## Sensitivity analysis

Vary initial points, variable and constraint scaling, solver family, tolerances, finite-difference step, penalty/barrier settings, discretization mesh and quadrature, parameter/data uncertainty, and boundary conditions. A conclusion is fragile if plausible starts yield materially different feasible candidates, small perturbations alter active constraints or local classification, gradient signs depend on step size, residuals change under rescaling, or mesh refinement changes the reported value/profile beyond the declared tolerance. Report all material variation and do not select only the best run without stating selection policy.

## Applicability domain

Classical smooth KKT and Euler-Lagrange arguments require their differentiability, regularity, and constraint assumptions. Nonsmooth, infinite-dimensional, noncompact, nonconvex, and ill-conditioned problems may require specialized theory. Numerical solutions apply to the discretized, scaled, finite-tolerance problem actually solved. Local methods do not certify unvisited basins or global optima. Existence cannot be inferred from solver convergence.

## Common failure modes and detection

- **KKT treated as sufficient in a nonconvex problem:** inspect convexity and theorem assumptions; relabel as stationary candidate when absent.
- **Constraint qualification assumed:** state and test the relevant condition; if unresolved, withhold the KKT inference.
- **Local result called global:** seek a valid bound/gap or convexity argument; multi-start agreement remains heuristic.
- **Gradient bug hidden by one finite-difference step:** vary step size and test multiple points against an independent derivative path.
- **Scaling masks poor conditioning:** report scaled and original residuals and inspect conditioning.
- **Penalty optimum mistaken for feasible point:** evaluate original constraints independently.
- **Discretization error conflated with optimizer error:** refine mesh independently of solver tolerance and track both residual and objective/profile changes.
- **Euler-Lagrange stationary path called a minimizer:** derive boundary terms and test second variation or a stronger convexity theorem.

## Sources

Boyd and Vandenberghe, *Convex Optimization*, 2004, covers convexity, duality, and KKT sufficiency under stated assumptions. Nocedal and Wright, *Numerical Optimization*, 2nd ed., 2006, covers numerical algorithms and optimality conditions. Gelfand and Fomin, *Calculus of Variations*, 1963, covers first variation, Euler-Lagrange equations, and boundary conditions. These texts do not certify a specific numerical result without its assumptions and evidence.

## Numerical analysis record

Record the exact objective and constraint functions evaluated by the solver, transformed variables, inverse transformations, units, and feasibility tolerances in original coordinates. Keep solver termination status distinct from the returned candidate's independently calculated feasibility and stationarity residuals. State whether a bound is analytic, dual, interval-based, or numerical.

Finite-difference gradient checks require an explicit perturbation scale and representative points. Central differences can fail near bounds, nonsmooth points, or under cancellation; compare several step sizes and inspect expected convergence before interpreting disagreement. Automatic differentiation checks do not independently validate an incorrectly specified objective graph.

For multi-start work, state how feasible starts were chosen, how duplicates were clustered, and whether failed starts were retained. Report candidate distribution rather than only the best value. If starting points are sampled from a restricted region, conclusions apply only to that search region and initialization policy.

For a functional discretization, record basis or mesh, quadrature, boundary enforcement, and refinement schedule. Refine the discretization while keeping optimizer tolerances sufficiently tight to distinguish optimization error from approximation error. Verify the candidate against the original functional and boundary conditions; transformed equations or penalty objectives can alter the problem.

For variational problems, write the first variation including endpoint terms and state which endpoint values are fixed or free. A natural boundary condition follows only for a free endpoint under the relevant regularity assumptions. A second-variation sign test must specify admissible perturbations and boundary restrictions; it does not by itself establish global minimality.

## Decision language

Use “feasible candidate” when original constraints pass but optimality is not certified. Use “stationary candidate” when first-order conditions pass under stated tolerances. Use “local minimum” only with applicable local second-order or theorem evidence. Reserve “global minimum” for a matching global certificate or valid theorem; record the certificate and its assumptions explicitly.

When comparing candidate optima, report objective values with units and precision, constraint violations, start identity, termination reason, and whether the candidates differ beyond declared tolerance. Similar objective values do not prove equivalent solutions, and a lower computed value can reflect a feasibility violation or scaling error.

If the problem is infeasible or existence is unknown, preserve that as an outcome rather than repairing constraints silently. If a solver fails, distinguish numerical failure from evidence that no solution exists. A penalty method's failure to find a feasible point does not prove infeasibility.

For reported sensitivities, distinguish local derivatives of the optimum value from re-solving under changed parameters. Active-set changes can make local sensitivity discontinuous or undefined. State whether values are conditional on a fixed active set or were recomputed over the full changed problem.

For dual bounds, state the primal and dual formulations, sign convention, feasibility status, and numerical gap. A small reported gap is meaningful only if both sides were evaluated consistently and their residual tolerances are disclosed. If dual feasibility is approximate, qualify the bound.
