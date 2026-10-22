---
name: chaos-nonlinear-dynamics
description: "Analyze nonlinear dynamical systems, bifurcations, and deterministic chaos. Use for flows and maps, phase portraits, fixed points, limit cycles, Lyapunov exponents, Poincare sections, attractors, continuation, and distinguishing chaos from noise or numerical artifacts."
license: MIT
---

# Chaos and Nonlinear Dynamics

## Decision contract
State the equations or map, parameter regime, initial conditions or ensemble, observables, and whether the requested conclusion concerns local stability, long-time structure, bifurcation, or chaos. Treat finite trajectory evidence as bounded by its numerical and observational resolution. Distinguish exact or numerical solver output from a verified mathematical or dynamical property.

## Reference usage
Read [references/nonlinear-dynamics-evidence.md](references/nonlinear-dynamics-evidence.md) before assigning a dynamics claim, estimating Lyapunov exponents or attractor structure, or interpreting a bifurcation. It defines diagnostic, dependence, sensitivity, and applicability limits.

## Workflow
1. Define the autonomous or forced equations or map, state space, parameters, time scale, initial ensemble, constraints, observables, and continuous- or discrete-time convention; nondimensionalize where useful and declare transients and sampling intervals.
2. Locate fixed points and invariant sets from the equations; record candidate solutions and residuals, and treat solver convergence alone as candidate evidence.
3. Linearize at each fixed point and classify local stability from eigenvalues; when eigenvalues are marginal, repeated, or near the unit boundary, record the unresolved nonlinear analysis required.
4. For a bifurcation claim, continue solutions or sweep a prespecified parameter range and identify the local normal-form signature and stability change; record alternatives and do not infer a global transition from a local signature.
5. For chaos, estimate finite-time and asymptotic Lyapunov behavior with declared tangent dynamics, transient removal, renormalization, duration, and sampling; cross-check with independent diagnostics such as return maps and spectral or entropy measures, and compare deterministic, stochastic, and measurement-noise explanations for observed data.
6. Construct Poincare sections or return maps with a declared section and event rule; check repeatability across solver, step size, tolerances, and initial conditions, and record section definition and sensitivity.
7. Use nullclines, invariant manifolds, or symmetry reductions when they clarify the structure; check boundedness, invariants, symmetries, precision, aliasing, stiffness, interpolation, and short-data artifacts. Vary integrator family, step size, tolerance, data window, transient length, and initial ensemble, recording diagnostics that change classification.
8. Assign each claim supported, contradicted, inconclusive, or unavailable from convergent diagnostics and their limits; report uncertainty, alternatives, applicability domain, and the smallest falsifiable next action, then verify artifact completeness and hand off with `$science-provenance` and `$science-review`.

## Outputs
Return `dynamics-evidence-v1` with required fields: claim identifier (`claim_id`), claim class (`claim_class`), status (`status`: supported, contradicted, inconclusive, or unavailable), equations or map (`equations_or_map`), parameter values (`parameters`), initial conditions or ensemble (`initial_conditions`), observable (`observable`), analysis method (`method`), numerical controls (`numerical_controls`), source dependencies (`source_dependencies`), uncertainty (`uncertainty`), sensitivity results (`sensitivity`), applicability domain (`applicability_domain`), evidence artifact paths and hashes (`evidence_artifacts`), and limitations (`limitations`). Include normalized inputs and assumptions, commands or derivations, preserved failures and nulls, and the smallest falsifiable next action. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A long or irregular trajectory alone does not establish deterministic chaos, and nearby chaotic trajectories need not agree pointwise. Fixed-point roots, eigenvalues, solver outputs, finite-time Lyapunov estimates, Poincare plots, and dimension estimates are numerical evidence with declared resolution, not verified global properties. Stop short of a chaos claim when diagnostics fail to converge under numerical and sampling checks. Attractor dimension estimates depend on data length, noise, embedding, and scaling range; shadowing of a computed orbit is not guaranteed for arbitrary duration.

## Source basis

Original synthesis informed by Lebl's openly licensed nonlinear differential-equations chapters and numerical
analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
