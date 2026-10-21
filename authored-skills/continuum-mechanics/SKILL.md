---
name: continuum-mechanics
description: "Formulate, solve, and verify continuum models for solids and fluids. Use for deformation, stress, strain, conservation laws, constitutive equations, elasticity, viscosity, boundary conditions, weak forms, and finite-element or finite-volume analysis."
license: MIT
---

# Continuum Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Define the continuum**

State the body or control volume, reference and current configurations, coordinates, scale separation,
material symmetry, fields, loads, initial data, interfaces, and boundary conditions. Declare small- or
finite-deformation assumptions and whether the description is material or spatial.

**Formulate the model**

- Write mass, momentum, angular-momentum, and energy balances before specializing the material.
- Define deformation gradient, strain measure, stress measure, and their configuration consistently.
- Choose a constitutive law with declared objectivity, symmetry, compressibility, rate, and thermal assumptions.
- Separate essential from natural boundary conditions and enforce interface jump conditions.
- Use a weak form for nonsmooth fields or finite elements; show boundary terms and admissible spaces.

**Solve**

Nondimensionalize to expose Reynolds, Mach, Deborah, Poisson, or other governing ratios. For numerical work,
state spatial and temporal discretization, stabilization, nonlinear solver, constitutive update, and mesh quality.
Do not hide locking, shocks, contact, or incompressibility behind default solver tolerances.

**Verify**

- Check frame indifference, tensor symmetry, units, conservation, and constitutive admissibility.
- Recover rigid motion, hydrostatic, uniaxial, inviscid, or small-strain limits as appropriate.
- Balance integrated forces, moments, mass, and energy over the domain.
- Perform mesh and time refinement; distinguish discretization, iteration, and model errors.
- Check boundary tractions, displacement compatibility, and interface continuity or jumps.

**Deliver**

Report kinematics, balances, constitutive law, conditions, solution method, convergence evidence, conserved
quantities, and applicability limits.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by open continuum-mechanics materials and Schnick's physics text; source details
are in `../../docs/TEXTBOOK_SOURCES.md`.
