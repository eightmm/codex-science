---
name: classical-mechanics
description: "Formulate, solve, simulate, and verify classical mechanics problems using Newtonian, Lagrangian, Hamiltonian, conservation-law, oscillation, rotation, and central-force methods. Use for particles, rigid bodies, constrained systems, collisions, orbital motion, and small oscillations."
license: MIT
---

# Classical Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [mechanics-claim-calibration.md](references/mechanics-claim-calibration.md) before classifying a result, selecting a model outside a standard regime, or reporting approximation error, numerical convergence, sensitivity, or applicability. It defines claim classes, mechanical controls, dependency records, and stop conditions.

## Workflow

1. **Define the system.** Draw or describe the boundary, bodies, coordinates, frame, degrees of freedom, constraints, forces, torques, initial data, and requested observables; if any essential condition is unknown, stop or label it unavailable. Record the system and unresolved inputs.
2. **Fix conventions and scales.** Set sign, angle, rotation, inertial/rotating-frame, and unit conventions before equations; use `$cx-dimensional-analysis-units` to check dimensions and characteristic scales. Record conventions, units, and scale checks.
3. **Choose a formulation.** Use Newton/Euler for explicit forces, contacts, impulses, and rigid-body balances; work-energy when path details are secondary; momentum/angular momentum for collisions, impulses, symmetry, and central forces; Lagrange for constrained generalized coordinates; Hamilton for phase space, canonical structure, perturbations, and long-time dynamics; linear modes only about a verified equilibrium. Include fictitious forces only in a declared non-inertial frame. Record the selected method and why its assumptions fit.
4. **Close the model.** Write free-body diagrams or equivalent force inventories, classify constraints as holonomic, time-dependent, ideal, or frictional, and count equations, unknowns, and constraints. If the model is under- or over-constrained, stop and expose the mismatch. Record equations and closure checks.
5. **Derive before computing.** Derive equations before substituting numbers; identify conserved quantities from symmetries and reduce the system only when the symmetry and conditions apply. Resolve impacts, friction laws, and discontinuities explicitly. Record derivation, invariants, and event treatment.
6. **Control approximations and computation.** State the small parameter and justified error order for each controlled approximation; identify the regime for linearization, perturbation, or averaging. For numerical trajectories choose an integrator matched to stiffness and long-time invariant needs, and retain solver, step, and parameter settings. Record approximation and numerical claims separately.
7. **Verify.** Check force, torque, energy, and momentum dimensions; substitute limiting cases (zero force, no damping, small angle, equal masses, circular orbit, static limit); check predicted energy and momentum conservation, constraint violation, and reaction-force consistency. Compare numerical trajectories across step sizes and, where useful, with a symplectic method. Distinguish stable equilibrium, neutral stability, instability, resonance, and chaotic sensitivity. Record each check, outcome, and failed check.
8. **Deliver and hand off.** Report model, frame, equations, solution, invariants, uncertainty, checks, and validity range; mathematical consistency, solver convergence, and process success do not establish empirical force-model validity. Preserve null, failed, and unavailable results; record artifact paths and hashes with `$science-provenance`, then require `$science-review` before presenting material conclusions. Record claim status and the smallest falsifiable next action.

## Outputs

Return schema `mechanics-evidence-v1` with required fields: concise summary (`summary`); normalized inputs, assumptions, conventions, and boundary/initial conditions (`system_record`); stable claim IDs, status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), and falsifier (`claims`); method, equations, approximations, and computational settings (`method_record`); results with units and uncertainty (`results`); checks and outcomes (`verification`); limitations and applicability domain (`applicability`); rejected alternatives and reasons (`rejected_alternatives`); smallest falsifiable next action (`next_action`); artifact paths and hashes (`artifacts`). Preserve null, failed, and unavailable results distinctly. Record artifacts with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

The workflow is an original synthesis informed by Schnick's openly licensed *Calculus-Based Physics I*;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
