---
name: quantum-mechanics
description: "Formulate, solve, simulate, and verify nonrelativistic quantum mechanics problems using states, operators, boundary conditions, symmetries, stationary and time-dependent evolution, approximation methods, measurement, and open-system dynamics."
license: MIT
---

# Quantum Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [quantum-claim-calibration.md](references/quantum-claim-calibration.md) before classifying a result, selecting a truncation or open-system model, or reporting approximation error, numerical convergence, sensitivity, or applicability. It defines state/operator controls, source dependencies, and stop conditions.

## Workflow

1. **Define the quantum model.** State Hilbert space, degrees of freedom, Hamiltonian, domain and boundary conditions, units, initial state or density operator, observables, and requested probabilities or expectation values. If essential inputs are unknown, stop or mark them unavailable. Record the model and requested claims.
2. **Declare conventions and approximations.** Specify nonrelativistic, single-particle, Born-Oppenheimer, spinless, finite-basis, rotating-wave, Markovian, or other truncations; nondimensionalize or choose natural units explicitly and never silently set constants to one. Record conventions, approximation parameters, and validity regime.
3. **Validate the operator model.** Check operator domains and that claimed observables are Hermitian/self-adjoint under selected boundary conditions; state whether the system is closed or open and justify its generator. If assumptions fail, revise the model or stop. Record operator and dynamical checks.
4. **Choose a route.** For stationary states solve the spectral problem with normalizability and boundary conditions; for closed time evolution use unitary propagation and for open evolution state the master equation; use compatible symmetry quantum numbers and conserved quantities; use perturbative, variational, semiclassical, adiabatic, or finite-basis methods only with a stated small parameter or variational space. For few-level/open-system computation, load `kdense-qutip` while retaining this physics validation contract. Record method and selection criterion.
5. **Compute observables.** Normalize states and distinguish global from relative phase; preserve complex conjugation, operator order, and tensor-product structure; resolve degeneracy before nondegenerate perturbation formulas. For measurement distinguish amplitudes, probabilities, expectation values, and post-measurement states. Record definitions and results with units.
6. **Control numerical truncation.** Demonstrate basis and cutoff convergence for discretized or truncated calculations; compare analytic and numerical spectra and show grid/basis/time-step convergence. If the reported conclusion changes under adequate refinement, label it fragile or inconclusive. Record truncations, refinements, and changes.
7. **Verify.** Check normalization, density-operator positivity and unit trace, probability bounds, Hermiticity, commutators, orthogonality, completeness within the retained space, and units. For closed evolution check norm/energy conservation and unitarity; for open evolution check trace preservation and complete-positivity assumptions of the generator. Substitute eigenfunctions into the operator and boundary conditions; test free-particle, zero-coupling, classical/semiclassical, symmetry, and short-time limits. Record each check and outcome.
8. **Deliver and hand off.** Report model, approximations with small parameter and justified error order where controlled, state/operator definitions, result, uncertainty, convergence checks, interpretation, and validity range. Do not treat an unnormalized wavefunction or an arbitrary finite-basis eigenpair as a physical prediction. Preserve null, failed, and unavailable results; record artifact paths and hashes with `$science-provenance`, then require `$science-review` before presenting material conclusions. Record claim status and the smallest falsifiable next action.

## Outputs

Return schema `quantum-evidence-v1` with required fields: concise summary (`summary`); normalized inputs, state, operator, boundary conditions, and assumptions (`system_record`); stable claim IDs, status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), and falsifier (`claims`); equations, approximation parameters, and computational settings (`method_record`); results with units and uncertainty (`results`); checks and outcomes (`verification`); limitations and applicability domain (`applicability`); rejected alternatives and reasons (`rejected_alternatives`); smallest falsifiable next action (`next_action`); artifact paths and hashes (`artifacts`). Preserve null, failed, and unavailable results distinctly. Record artifacts with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

This workflow is independently synthesized from Crowell's openly licensed *Modern Physics* and the
existing QuTiP workflow; source provenance is recorded in `../../docs/TEXTBOOK_SOURCES.md`.
