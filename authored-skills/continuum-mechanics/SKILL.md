---
name: continuum-mechanics
description: "Formulate, solve, and verify continuum models for solids and fluids. Use for deformation, stress, strain, conservation laws, constitutive equations, elasticity, viscosity, boundary conditions, weak forms, and finite-element or finite-volume analysis."
license: MIT
---

# Continuum Mechanics

## Define the continuum

State the body or control volume, reference and current configurations, coordinates, scale separation,
material symmetry, fields, loads, initial data, interfaces, and boundary conditions. Declare small- or
finite-deformation assumptions and whether the description is material or spatial.

## Formulate the model

- Write mass, momentum, angular-momentum, and energy balances before specializing the material.
- Define deformation gradient, strain measure, stress measure, and their configuration consistently.
- Choose a constitutive law with declared objectivity, symmetry, compressibility, rate, and thermal assumptions.
- Separate essential from natural boundary conditions and enforce interface jump conditions.
- Use a weak form for nonsmooth fields or finite elements; show boundary terms and admissible spaces.

## Solve

Nondimensionalize to expose Reynolds, Mach, Deborah, Poisson, or other governing ratios. For numerical work,
state spatial and temporal discretization, stabilization, nonlinear solver, constitutive update, and mesh quality.
Do not hide locking, shocks, contact, or incompressibility behind default solver tolerances.

## Verify

- Check frame indifference, tensor symmetry, units, conservation, and constitutive admissibility.
- Recover rigid motion, hydrostatic, uniaxial, inviscid, or small-strain limits as appropriate.
- Balance integrated forces, moments, mass, and energy over the domain.
- Perform mesh and time refinement; distinguish discretization, iteration, and model errors.
- Check boundary tractions, displacement compatibility, and interface continuity or jumps.

## Deliver

Report kinematics, balances, constitutive law, conditions, solution method, convergence evidence, conserved
quantities, and applicability limits.

## Source basis

Original synthesis informed by open continuum-mechanics materials and Schnick's physics text; source details
are in `../../docs/TEXTBOOK_SOURCES.md`.
