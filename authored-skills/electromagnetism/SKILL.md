---
name: electromagnetism
description: "Formulate, solve, simulate, and verify electrostatics, magnetostatics, circuits, induction, electromagnetic waves, and boundary-value problems using Maxwell's equations, potentials, constitutive relations, and conservation laws."
license: MIT
---

# Electromagnetism

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Specify the regime**

1. State sources, geometry, materials, domain, boundary/initial data, frequency range, unit system,
   gauge convention, and requested fields or observables.
2. Decide whether the problem is electrostatic, magnetostatic, quasistatic, lumped-circuit,
   frequency-domain, wave, or fully time-dependent.
3. Record constitutive assumptions and whether media are linear, homogeneous, isotropic,
   dispersive, lossy, or nonlinear.
4. Use `$cx-dimensional-analysis-units`; do not mix SI and Gaussian conventions.

**Select equations**

- Begin with Maxwell's equations and charge conservation, then justify every approximation.
- Use potentials when they simplify constraints; state the gauge and observable gauge invariance.
- Use Gauss or Ampere symmetry only after proving the required field symmetry.
- Enforce interface conditions on normal and tangential field components.
- For circuits, define reference directions and derive Kirchhoff equations from the lumped approximation.
- For waves, state polarization, propagation direction, impedance, dispersion relation, and radiation condition.

**Solve**

1. Reduce by symmetry and boundary conditions before integration or discretization.
2. Use separation, images, multipoles, Green functions, Fourier methods, or numerical field solvers
   according to geometry and material complexity.
3. For numerical solutions, resolve material interfaces, singular sources, skin depth, and wavelength.
4. Compute derived quantities from fields: force, torque, energy, Poynting flux, capacitance,
   inductance, impedance, or radiation power.

**Verify**

- Check divergence/curl equations and charge continuity.
- Check boundary conditions and global integral laws independently.
- Confirm electrostatic energy positivity and power/energy balance, including losses.
- Test conductor, vacuum, static, far-field, long-wavelength, and symmetry limits.
- Compare mesh/frequency/time-step refinement and reciprocity where applicable.
- Separate numerical singularity near idealized point/line sources from a physical divergence.

**Deliver**

State regime, approximations, equations, boundary data, solution, derived observables, residuals,
conservation checks, and validity limits.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

This workflow is independently synthesized from Schnick's CC BY-SA *Calculus-Based Physics II* and
the open physics references in `../../docs/TEXTBOOK_SOURCES.md`.
