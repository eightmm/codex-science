---
name: continuum-mechanics
description: "Formulate, solve, and verify continuum models for solids and fluids. Use for deformation, stress, strain, conservation laws, constitutive equations, elasticity, viscosity, boundary conditions, weak forms, and finite-element or finite-volume analysis."
license: MIT
---

# Continuum Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [continuum-evidence.md](references/continuum-evidence.md) before choosing kinematics or a constitutive law, formulating boundary/interface conditions, interpreting a continuum solution, or claiming numerical convergence. It defines claim classes, source dependence, uncertainty, controls, refinement and sensitivity checks, and model limits.

## Workflow

1. **Check scope:** identify the requested result and whether body/control volume, fields, loads, material, initial/boundary data, and regime are sufficiently specified; stop or report unresolved choices if they affect a safe formulation. Record missing inputs and defaults.
2. **Define the continuum:** state body or control volume, reference/current configurations, coordinates, scale separation, material symmetry, fields, loads, initial data, interfaces, and boundary conditions. Declare small- or finite-deformation assumptions and material or spatial description. Record the selected kinematics.
3. **Formulate balances and law:** write mass, momentum, angular-momentum, and energy balances before specializing material; define deformation gradient, strain and stress measures consistently by configuration. Select a constitutive law with objectivity, symmetry, compressibility, rate, and thermal assumptions. Separate essential/natural boundary conditions and state interface jump conditions. Record the model rationale.
4. **Choose solution method:** use a weak form for nonsmooth fields or finite elements, showing boundary terms and admissible spaces. Nondimensionalize governing ratios (such as Reynolds, Mach, Deborah, or Poisson ratios); for numerical work record spatial/temporal discretization, stabilization, nonlinear solver, constitutive update, and mesh quality. Identify likely locking, shocks, contact, or incompressibility issues before solving.
5. **Classify the claim:** label each material result exact, controlled approximation (small parameter and error order), numerical (with mesh/time convergence evidence), or heuristic estimate. Assign claim IDs, status, uncertainty, and falsifier; do not call a finite solve converged without refinement evidence.
6. **Verify balances and limits:** check frame indifference, tensor symmetry, units, conservation, and constitutive admissibility; recover rigid motion, hydrostatic, uniaxial, inviscid, or small-strain limits as applicable. Balance integrated forces, moments, mass, and energy; check boundary tractions, displacement compatibility, and interface continuity or jumps. Record expected and observed checks.
7. **Stress-test and deliver:** perform mesh and time-step refinement; distinguish discretization, iteration, and model errors. Vary constitutive model, boundary conditions, parameters, loading, and refinement choices that may affect the result; flag changes beyond the error budget or that reverse a claim. Preserve failures and limitations, record paths and hashes with `$science-provenance`, then use `$science-review` before presenting material conclusions.

## Outputs

Return `continuum-evidence-v1` with: body/control volume and normalized inputs; configuration, kinematics, fields, loads, and conditions; constitutive model and assumptions; claim identifiers and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); claim class and falsifier; balances and solution method/settings; results with units and uncertainty; source/dependency records; conservation, limiting-case, and boundary checks with outcomes; mesh/time refinement and convergence evidence; sensitivity results; applicability limits; rejected alternatives and reasons; smallest falsifiable next action; artifact paths and hashes; provenance and independent review receipts. Preserve null, failed, and unavailable results distinctly.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by open continuum-mechanics materials and Schnick's physics text; source details
are in `../../docs/TEXTBOOK_SOURCES.md`.
