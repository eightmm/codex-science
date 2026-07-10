---
name: electromagnetism
description: "Formulate, solve, simulate, and verify electrostatics, magnetostatics, circuits, induction, electromagnetic waves, and boundary-value problems using Maxwell's equations, potentials, constitutive relations, and conservation laws."
license: MIT
---

# Electromagnetism

## Specify the regime

1. State sources, geometry, materials, domain, boundary/initial data, frequency range, unit system,
   gauge convention, and requested fields or observables.
2. Decide whether the problem is electrostatic, magnetostatic, quasistatic, lumped-circuit,
   frequency-domain, wave, or fully time-dependent.
3. Record constitutive assumptions and whether media are linear, homogeneous, isotropic,
   dispersive, lossy, or nonlinear.
4. Use `$cx-dimensional-analysis-units`; do not mix SI and Gaussian conventions.

## Select equations

- Begin with Maxwell's equations and charge conservation, then justify every approximation.
- Use potentials when they simplify constraints; state the gauge and observable gauge invariance.
- Use Gauss or Ampere symmetry only after proving the required field symmetry.
- Enforce interface conditions on normal and tangential field components.
- For circuits, define reference directions and derive Kirchhoff equations from the lumped approximation.
- For waves, state polarization, propagation direction, impedance, dispersion relation, and radiation condition.

## Solve

1. Reduce by symmetry and boundary conditions before integration or discretization.
2. Use separation, images, multipoles, Green functions, Fourier methods, or numerical field solvers
   according to geometry and material complexity.
3. For numerical solutions, resolve material interfaces, singular sources, skin depth, and wavelength.
4. Compute derived quantities from fields: force, torque, energy, Poynting flux, capacitance,
   inductance, impedance, or radiation power.

## Verify

- Check divergence/curl equations and charge continuity.
- Check boundary conditions and global integral laws independently.
- Confirm electrostatic energy positivity and power/energy balance, including losses.
- Test conductor, vacuum, static, far-field, long-wavelength, and symmetry limits.
- Compare mesh/frequency/time-step refinement and reciprocity where applicable.
- Separate numerical singularity near idealized point/line sources from a physical divergence.

## Deliver

State regime, approximations, equations, boundary data, solution, derived observables, residuals,
conservation checks, and validity limits.

## Source basis

This workflow is independently synthesized from Schnick's CC BY-SA *Calculus-Based Physics II* and
the open physics references in `../../docs/TEXTBOOK_SOURCES.md`.
