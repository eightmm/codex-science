---
name: chaos-nonlinear-dynamics
description: "Analyze nonlinear dynamical systems, bifurcations, and deterministic chaos. Use for flows and maps, phase portraits, fixed points, limit cycles, Lyapunov exponents, Poincare sections, attractors, continuation, and distinguishing chaos from noise or numerical artifacts."
license: MIT
---

# Chaos and Nonlinear Dynamics

## Decision contract
State the equations or map, parameter regime, initial conditions or ensemble, observables, and whether the requested conclusion concerns local stability, long-time structure, bifurcation, or chaos. Treat finite trajectory evidence as bounded by its numerical and observational resolution.

## Workflow
1. **Define the dynamics.**
   State the autonomous or forced equations or map, state space, parameters, time scale, initial ensemble,
   constraints, observables, and continuous- or discrete-time convention. Identify equilibria and invariant sets
   before interpreting a trajectory. Nondimensionalize and declare transients and sampling intervals.

2. **Analyze structure.**
   - Linearize at equilibria and classify local stability from the Jacobian with exceptional cases handled separately.
   - Use continuation or parameter sweeps to locate bifurcations; distinguish local from global transitions.
   - Use nullclines, return maps, Poincare sections, invariant manifolds, and symmetry reductions as appropriate.
   - Estimate Lyapunov exponents only after controlling tangent evolution, transients, data length, and rescaling.
   - For observed data, compare deterministic, stochastic, and measurement-noise explanations.

3. **Verify.**
   - Repeat with smaller time steps, different integrator families, tighter tolerances, and longer transients.
   - Check boundedness, invariants, symmetries, event detection, and dependence on initial ensemble.
   - Require convergence of qualitative structures, not pointwise agreement of chaotic trajectories.
   - Cross-check chaos using multiple diagnostics such as Lyapunov behavior, return maps, and spectral or entropy measures.
   - Detect finite precision, aliasing, stiffness, interpolation, and short-data artifacts.

4. **Deliver.**
   Report equations, parameter regime, attractor and transient protocol, integrator, bifurcation or chaos evidence,
   robustness checks, uncertainty, and alternatives not ruled out.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A long or irregular trajectory alone does not establish deterministic chaos, and nearby chaotic trajectories need not agree pointwise. Stop short of a chaos claim when diagnostics fail to converge under numerical and sampling checks.

## Source basis

Original synthesis informed by Lebl's openly licensed nonlinear differential-equations chapters and numerical
analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
