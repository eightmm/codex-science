---
name: ode-pde-solving
description: "Classify, solve, approximate, and verify ordinary and partial differential equations with explicit domains, initial or boundary data, well-posedness, residuals, and convergence checks. Use for IVPs, BVPs, dynamical systems, eigenvalue problems, Fourier methods, diffusion, waves, Laplace or Poisson equations, and nonlinear differential equations."
license: MIT
---

# ODE and PDE Solving

## Decision contract

State the equation, domain, data, parameters and units, requested observable, regularity, and function space. Distinguish an analytic theorem from conclusions about one computed trajectory. Classify each result as a proven result with stated assumptions, a numerically verified result with convergence and conditioning evidence, a simulated estimate with Monte Carlo error, or a conjecture. Record the baseline, inference limit, uncertainty rule, falsifier, and any missing choice that would materially change the method.

## Reference usage

- Read [references/ode-pde-evidence.md](references/ode-pde-evidence.md) before assigning a claim class, relying on well-posedness, interpreting a numerical solution, or reporting a sensitivity or applicability conclusion.

## Workflow

1. **Formulate:** normalize the independent and dependent variables, domain, parameters, units, equation order, initial or boundary data, regularity, function space, and requested observable; if an omitted condition changes the equation or method, ask for it, and record all assumptions.
2. **Assess well-posedness:** classify linearity, autonomy, homogeneity, stiffness, conservation form, singular points, and (for PDEs) type, dimensions, boundary geometry, and compatibility; state the existence, uniqueness, and continuous-dependence theorem and hypotheses, or mark that claim unknown, and record the function-space and boundary/initial-condition assumptions.
3. **Choose an analytic route:** for first-order ODEs consider separation, integrating factors, exact equations, substitutions, or phase lines; for higher-order linear ODEs use characteristic roots, variation of parameters, Green functions, Laplace transforms, or series; for systems consider matrix exponentials, eigenstructure, phase portraits, invariant manifolds, or linearization; for PDEs consider characteristics, separation, Fourier transforms or series, eigenfunction expansions, similarity variables, or Green functions; record why the route applies, transform conventions, convergence assumptions, and condition checks.
4. **Choose a numerical route:** define discretization, mesh, time step, solver tolerances, and boundary implementation; match the method to stiffness, conservation, oscillation, discontinuity, and geometry; establish consistency, expected order, and stability restrictions before a full run; record method, scaling, revisions, and expected convergence behavior.
5. **Run a discriminating case:** begin with the smallest case that can expose a method or implementation defect; compare the requested observable, not only the state vector; preserve commands, environment, parameters, failed runs, and the baseline, and record why the case is adequate.
6. **Verify:** substitute analytic solutions into the differential operator and data; for numerical results compute a normalized residual, check initial/boundary conditions separately from the interior residual, test conserved quantities, positivity, maximum principles, energy estimates, or monotonicity as applicable, compare refinement ratios with expected order, compare with a closed-form solution, manufactured solution, or independently implemented baseline, and test long-time, steady-state, zero-source, symmetry, and parameter-limit behavior; retain at least two refinements and use at least three levels for an observed-order claim, recording all diagnostics and failures.
7. **Test sensitivity and domain:** vary tolerances, precision, time step, mesh, parameters, solver, and relevant boundary data; treat a claim as fragile if its status, requested observable, or reported digits change beyond the prespecified error budget; record the tested range and where stiffness, singularities, incompatible data, or model assumptions limit applicability.
8. **Classify and hand off:** assign stable claim IDs and proven, numerically verified, simulated-estimate, or conjecture class with supported, contradicted, inconclusive, or unavailable status; record dependencies, uncertainty, limitations, and the smallest falsifiable next action; preserve commands, derivations, artifacts, and hashes with `$science-provenance`, then run `$science-review` before material or consequential scientific conclusions.

## Outputs

Return one `ode-pde-evidence-v1` record containing: normalized equation and assumptions (`normalized_inputs`); domain and function space (`domain_function_space`); initial and boundary conditions (`initial_boundary_conditions`); claim identifiers, classes, statuses, and theorem hypotheses (`claims`); analytic derivation or numerical method (`method`); source and implementation dependencies (`dependencies`); residual, convergence, stability, and control results (`verification`); uncertainty and sensitivity (`uncertainty_sensitivity`); applicability domain and limitations (`applicability_limitations`); failed/null cases and inclusion rationale (`failures_exclusions`); falsifier and smallest next action (`next_action`); commands, environment, artifact paths, and hashes (`provenance`); `$science-provenance` record and `$science-review` findings (`review`).

## Boundaries

Do not infer uniqueness or stability from one numerical trajectory or residual. Distinguish discretization instability, ill-conditioning, chaotic sensitivity, and model uncertainty. A finite refinement series does not establish asymptotic convergence. Stop or qualify a claim when well-posedness, compatibility, or convergence evidence is missing; preserve failures and nulls. Use `$cx-numerical-analysis-error-control` for conditioning, truncation, and solver-error analysis. Run `$science-review` before material or consequential conclusions.

## Source basis

The workflow is independently synthesized from Lebl's *Notes on Diffy Qs* and the open numerical
texts listed in `../../docs/TEXTBOOK_SOURCES.md`.
