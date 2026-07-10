---
name: chaos-nonlinear-dynamics
description: "Analyze nonlinear dynamical systems, bifurcations, and deterministic chaos. Use for flows and maps, phase portraits, fixed points, limit cycles, Lyapunov exponents, Poincare sections, attractors, continuation, and distinguishing chaos from noise or numerical artifacts."
license: MIT
---

# Chaos and Nonlinear Dynamics

## Define the dynamics

State the autonomous or forced equations or map, state space, parameters, time scale, initial ensemble,
constraints, observables, and continuous- or discrete-time convention. Identify equilibria and invariant sets
before interpreting a trajectory. Nondimensionalize and declare transients and sampling intervals.

## Analyze structure

- Linearize at equilibria and classify local stability from the Jacobian with exceptional cases handled separately.
- Use continuation or parameter sweeps to locate bifurcations; distinguish local from global transitions.
- Use nullclines, return maps, Poincare sections, invariant manifolds, and symmetry reductions as appropriate.
- Estimate Lyapunov exponents only after controlling tangent evolution, transients, data length, and rescaling.
- For observed data, compare deterministic, stochastic, and measurement-noise explanations.

## Verify

- Repeat with smaller time steps, different integrator families, tighter tolerances, and longer transients.
- Check boundedness, invariants, symmetries, event detection, and dependence on initial ensemble.
- Require convergence of qualitative structures, not pointwise agreement of chaotic trajectories.
- Cross-check chaos using multiple diagnostics such as Lyapunov behavior, return maps, and spectral or entropy measures.
- Detect finite precision, aliasing, stiffness, interpolation, and short-data artifacts.

## Deliver

Report equations, parameter regime, attractor and transient protocol, integrator, bifurcation or chaos evidence,
robustness checks, uncertainty, and alternatives not ruled out.

## Source basis

Original synthesis informed by Lebl's openly licensed nonlinear differential-equations chapters and numerical
analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
