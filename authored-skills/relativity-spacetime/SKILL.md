---
name: relativity-spacetime
description: "Formulate and verify special- and general-relativity problems. Use for Lorentz transformations, four-vectors, relativistic kinematics, metrics, geodesics, curvature, gravitational fields, horizons, and stress-energy dynamics."
license: MIT
---

# Relativity and Spacetime

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Fix conventions**

Define events, observers, coordinates, units for `c` and `G`, metric signature, index placement, orientation,
curvature convention, and approximation regime. Separate coordinate quantities from locally measured
observables. Identify timelike, null, and spacelike intervals before manipulating velocities or paths.
For a purely Riemannian manifold with no spacetime interpretation, mark causal and `c`, `G` conventions as
not applicable and use `$cx-tensor-calculus-differential-geometry` as the primary workflow.

**Select the model**

- In special relativity, use Lorentz transformations, invariant intervals, four-velocity, and four-momentum.
- For collisions or decays, conserve four-momentum and use invariant masses before choosing a frame.
- In general relativity, state the metric and symmetries, then derive connections, geodesics, and curvature.
- Relate geometry to matter with an explicit stress-energy tensor and field-equation convention.
- Use weak-field, slow-motion, or post-Newtonian approximations only after declaring their dimensionless limits.

**Verify**

- Check invariant intervals, four-vector norms, index contractions, tensor transformation, and dimensions.
- Recover Newtonian or special-relativistic behavior in the appropriate limit.
- Verify metric compatibility, geodesic normalization, conserved quantities from Killing symmetries, and constraints.
- Distinguish coordinate singularities from curvature singularities using invariants or regular coordinates.
- Cross-check symbolic results numerically at nonsingular points and test causal character along trajectories.

**Deliver**

Report conventions, geometry or frame, equations, invariant observables, approximation order, checks, and
domains excluded by coordinates or model assumptions.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Crowell's openly licensed *General Relativity* and *Modern Physics*; source
details are in `../../docs/TEXTBOOK_SOURCES.md`.
