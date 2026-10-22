---
name: electromagnetism
description: "Formulate, solve, simulate, and verify electrostatics, magnetostatics, circuits, induction, electromagnetic waves, and boundary-value problems using Maxwell's equations, potentials, constitutive relations, and conservation laws."
license: MIT
---

# Electromagnetism

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [electromagnetic-claim-calibration.md](references/electromagnetic-claim-calibration.md) before classifying a result, choosing unit/gauge conventions, using a reduced electromagnetic regime, or reporting approximation error, numerical convergence, sensitivity, or applicability. It defines field and circuit controls, source dependencies, and stop conditions.

## Workflow

1. **Specify the system and regime.** State sources, geometry, materials, domain, boundary/initial data, frequency range, requested fields or observables, and whether the case is electrostatic, magnetostatic, quasistatic, lumped-circuit, frequency-domain, wave, or fully time-dependent. If essential conditions are unknown, stop or mark them unavailable. Record the system and regime.
2. **Fix conventions.** Declare unit system, signs, orientations, gauge convention, reference directions, and constitutive assumptions; use `$cx-dimensional-analysis-units` and never mix SI and Gaussian conventions. Record units, gauge, and dimensional checks.
3. **Select equations.** Begin with Maxwell's equations and charge conservation, then justify each approximation. Use potentials when they simplify constraints and state the gauge and observable gauge invariance. Use Gauss or Ampere symmetry only after establishing required field symmetry; enforce interface conditions on normal and tangential components. Record equations and method rationale.
4. **Check model applicability.** State whether media are linear, homogeneous, isotropic, dispersive, lossy, or nonlinear; for circuits justify the lumped approximation and for waves state polarization, propagation direction, impedance, dispersion relation, and radiation condition. If assumptions fail, choose a suitable model or stop. Record model properties and regime limits.
5. **Reduce and solve.** Apply symmetry and boundary conditions before integration or discretization; choose separation, images, multipoles, Green functions, Fourier methods, or numerical field solvers according to geometry and material complexity. Record the selected method, inputs, and derived field solution.
6. **Resolve scales and derived quantities.** For numerical solutions resolve material interfaces, singular sources, skin depth, and wavelength; derive force, torque, energy, Poynting flux, capacitance, inductance, impedance, or radiation power from fields. Record mesh/frequency/time-step and observable definitions.
7. **Verify.** Check divergence/curl equations and charge continuity; independently check boundary conditions and global integral laws; confirm electrostatic energy positivity and power/energy balance including losses. Test conductor, vacuum, static, far-field, long-wavelength, and symmetry limits. Compare mesh/frequency/time-step refinement and reciprocity where applicable; distinguish a numerical singularity near an ideal point/line source from physical divergence. Record each check and outcome.
8. **Deliver and hand off.** State regime, approximations with small parameter and error order where controlled, equations, boundary data, results, units, uncertainty, residuals, conservation checks, and validity limits. Preserve null, failed, and unavailable results; record artifact paths and hashes with `$science-provenance`, then require `$science-review` before presenting material conclusions. Record claim status and the smallest falsifiable next action.

## Outputs

Return schema `electromagnetism-evidence-v1` with required fields: concise summary (`summary`); normalized inputs, assumptions, unit/gauge/sign conventions, and boundary/initial data (`system_record`); stable claim IDs, status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), and falsifier (`claims`); equations, approximations, and computational settings (`method_record`); results with units and uncertainty (`results`); checks and outcomes (`verification`); limitations and applicability domain (`applicability`); rejected alternatives and reasons (`rejected_alternatives`); smallest falsifiable next action (`next_action`); artifact paths and hashes (`artifacts`). Preserve null, failed, and unavailable results distinctly. Record artifacts with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

This workflow is independently synthesized from Schnick's CC BY-SA *Calculus-Based Physics II* and
the open physics references in `../../docs/TEXTBOOK_SOURCES.md`.
