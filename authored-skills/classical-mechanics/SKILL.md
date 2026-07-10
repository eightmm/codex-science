---
name: classical-mechanics
description: "Formulate, solve, simulate, and verify classical mechanics problems using Newtonian, Lagrangian, Hamiltonian, conservation-law, oscillation, rotation, and central-force methods. Use for particles, rigid bodies, constrained systems, collisions, orbital motion, and small oscillations."
license: MIT
---

# Classical Mechanics

## Define the mechanical system

1. Draw or describe the system boundary, bodies, coordinates, inertial or rotating frame,
   degrees of freedom, constraints, forces, torques, initial data, and requested observables.
2. Set sign, angle, and rotation conventions before writing equations.
3. Use `$cx-dimensional-analysis-units` to normalize units and identify characteristic scales.
4. Determine whether constraints are holonomic, time-dependent, ideal, or frictional.

## Choose a formulation

- Newton/Euler: use for explicit forces, contacts, impulses, and rigid-body balances.
- Work-energy: use when force details are secondary and path or speed is central.
- Momentum/angular momentum: use for collisions, impulses, symmetry, and central forces.
- Lagrange: use generalized coordinates for constrained multi-degree systems.
- Hamilton: use phase space, canonical structure, perturbations, and long-time dynamics.
- Linear modes: expand about a verified equilibrium and solve the generalized eigenproblem.

Write free-body diagrams or equivalent force inventories. Include fictitious forces only in a
declared non-inertial frame.

## Solve and simulate

1. Count equations, unknowns, and constraints; detect under- or over-constrained models.
2. Derive equations before substituting numbers.
3. Identify conserved quantities from symmetries, then use them to reduce the system when valid.
4. For numerical trajectories, choose an integrator matched to stiffness and long-time invariant needs.
5. Resolve impacts, friction laws, and discontinuities explicitly; do not hide them in smooth solvers.

## Verify

- Check force, torque, energy, and momentum dimensions.
- Substitute special cases: zero force, no damping, small angle, equal masses, circular orbit, or static limit.
- Track energy and momenta when the model predicts conservation.
- Check constraint violation and reaction-force consistency.
- Compare numerical trajectories across step sizes and, where useful, with a symplectic method.
- Distinguish stable equilibrium, neutral stability, instability, resonance, and chaotic sensitivity.

## Deliver

Report the model, frame, equations, solution, invariants, checks, and validity range. Do not present a
small integration residual as evidence that the force model is empirically correct.

## Source basis

The workflow is an original synthesis informed by Schnick's openly licensed *Calculus-Based Physics I*;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
