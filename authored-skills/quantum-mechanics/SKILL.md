---
name: quantum-mechanics
description: "Formulate, solve, simulate, and verify nonrelativistic quantum mechanics problems using states, operators, boundary conditions, symmetries, stationary and time-dependent evolution, approximation methods, measurement, and open-system dynamics."
license: MIT
---

# Quantum Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Define the quantum model**

1. State Hilbert space, degrees of freedom, Hamiltonian, domain and boundary conditions, units,
   initial state or density operator, observables, and requested probabilities or expectation values.
2. Declare approximations: nonrelativistic, single-particle, Born-Oppenheimer, spinless,
   finite basis, rotating-wave, Markovian, or other truncations.
3. Check that operators have appropriate domains and that claimed observables are Hermitian/self-adjoint
   under the chosen boundary conditions.
4. Nondimensionalize or choose natural units explicitly; never silently set constants to one.

**Choose a route**

- Stationary states: solve the spectral problem and enforce normalizability and boundary conditions.
- Time evolution: use unitary propagation for closed systems and a declared master equation for open systems.
- Symmetry: identify commuting operators, conserved quantities, degeneracy, and compatible quantum numbers.
- Approximation: use perturbation, variational, semiclassical, adiabatic, or finite-basis methods only
  with a stated small parameter or variational space.
- Few-level/open systems: load `kdense-qutip` for computation, while retaining this physics validation contract.

**Compute**

1. Normalize states and keep global phase distinct from relative phase.
2. Preserve complex conjugation, operator order, and tensor-product structure.
3. Resolve degeneracy before applying nondegenerate perturbation formulas.
4. Demonstrate basis and cutoff convergence for discretized or truncated calculations.
5. For measurement, distinguish amplitudes, probabilities, expectation values, and post-measurement states.

**Verify**

- Check normalization, positivity and unit trace of density operators, and probability bounds.
- Check Hermiticity, commutators, orthogonality, completeness within the retained space, and units.
- For closed evolution, check norm/energy conservation and unitarity; for open evolution, check trace
  preservation and complete-positivity assumptions of the generator.
- Substitute eigenfunctions into the operator and boundary conditions.
- Test free-particle, zero-coupling, classical/semiclassical, symmetry, and short-time limits.
- Compare analytic and numerical spectra and show grid/basis/time-step convergence.

**Deliver**

Report model and approximations, state/operator definitions, result, probabilities or observables,
convergence checks, and physical interpretation. Do not treat an unnormalized wavefunction or an
arbitrary finite-basis eigenpair as a physical prediction.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

This workflow is independently synthesized from Crowell's openly licensed *Modern Physics* and the
existing QuTiP workflow; source provenance is recorded in `../../docs/TEXTBOOK_SOURCES.md`.
