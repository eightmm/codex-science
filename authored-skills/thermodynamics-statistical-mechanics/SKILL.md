---
name: thermodynamics-statistical-mechanics
description: "Solve and verify equilibrium thermodynamics and statistical mechanics problems using explicit systems, sign conventions, equations of state, thermodynamic potentials, ensembles, partition functions, fluctuations, and phase-equilibrium conditions."
license: MIT
---

# Thermodynamics and Statistical Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Define the system**

1. State boundary, open/closed/isolated status, phases, components, constraints, reservoirs,
   state variables, equation of state, process path, and equilibrium assumptions.
2. Declare heat/work sign conventions and distinguish state functions from path functions.
3. Use absolute temperature and coherent units. Use `$cx-dimensional-analysis-units` when scales vary.
4. Decide whether a macroscopic thermodynamic or microscopic ensemble description is appropriate.

**Thermodynamic route**

1. Apply the first law to the declared system, including matter flow and non-`pV` work when present.
2. Apply the second law through entropy balance; separate reversible equality from irreversible inequality.
3. Select the natural potential for controlled variables: internal energy, enthalpy, Helmholtz,
   or Gibbs free energy.
4. Use exact differentials and Maxwell relations only for well-defined equilibrium state functions.
5. For phase or reaction equilibrium, enforce temperature, pressure, and chemical-potential conditions.

**Statistical route**

1. Define microstates, energy spectrum, degeneracy, conserved quantities, and selected ensemble.
2. Construct and normalize the partition function or probability distribution.
3. Derive observables and fluctuations from the same convention; state classical/quantum and
   distinguishable/indistinguishable assumptions.
4. Check thermodynamic-limit and low/high-temperature approximations before using them.

**Verify**

- Check extensivity/intensivity and Euler homogeneity where applicable.
- Check units, positivity of temperature/heat capacity assumptions, entropy production, and stability.
- Recover ideal-gas, dilute, noninteracting, zero-coupling, and large-system limits.
- Confirm probability normalization and fluctuation-response relations.
- Test that cycles satisfy energy conservation and the Clausius inequality.
- Distinguish equilibrium predictions from kinetics and finite-time transport.

**Deliver**

Report system definition, conventions, ensemble or potential, derivation, equilibrium/stability result,
checks, and applicability range. Do not infer microscopic mechanism from a successful equation-of-state fit.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

The workflow is an original synthesis informed by the thermodynamics and probability treatment in
Crowell's CC BY-SA *Modern Physics*; provenance is in `../../docs/TEXTBOOK_SOURCES.md`.
