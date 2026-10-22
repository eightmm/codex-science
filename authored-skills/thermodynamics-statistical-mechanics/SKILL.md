---
name: thermodynamics-statistical-mechanics
description: "Solve and verify equilibrium thermodynamics and statistical mechanics problems using explicit systems, sign conventions, equations of state, thermodynamic potentials, ensembles, partition functions, fluctuations, and phase-equilibrium conditions."
license: MIT
---

# Thermodynamics and Statistical Mechanics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [thermodynamic-evidence.md](references/thermodynamic-evidence.md) before choosing a potential or ensemble, evaluating equilibrium or a cycle, using an approximation, or making a thermodynamic/statistical claim. It defines claim classes, source dependence, uncertainty, domain controls, sensitivity checks, and validity limits.

## Workflow

1. **Check scope:** identify the requested result and whether the system, boundary/initial conditions, regime, and evidence needed to solve it are specified; if an essential item is ambiguous, stop or state the unresolved choice. Record the question, missing inputs, and any safe defaults.
2. **Define the system:** classify it as open, closed, or isolated; list phases, components, constraints, reservoirs, state variables, equation of state, process path, and equilibrium assumptions. Distinguish state functions from path functions. Record the system boundary and assumptions.
3. **Fix conventions and route:** declare heat/work signs, coherent units, absolute temperature, and whether a macroscopic or microscopic description fits the question; use `$cx-dimensional-analysis-units` when scales vary. Select internal energy, enthalpy, Helmholtz free energy, or Gibbs free energy from the controlled variables, and record the selection rationale.
4. **Derive the result:** apply the first law with matter flow and non-`pV` work as applicable, then the entropy balance with reversible equality distinguished from irreversible inequality. Use exact differentials and Maxwell relations only for well-defined equilibrium state functions; for phase/reaction equilibrium enforce temperature, pressure, and chemical-potential conditions. For statistical work, define microstates, spectrum, degeneracy, conserved quantities, classical/quantum and distinguishability assumptions, ensemble, and normalized partition function or probability law; derive observables and fluctuations from that same convention and record derivation assumptions.
5. **Classify the claim:** label each material result exact, controlled approximation (name the small parameter and error order), numerical (include convergence evidence), or heuristic estimate. Decide whether the derivation and evidence satisfy that class; record claim IDs, support status, uncertainty, and falsifier.
6. **Run domain checks:** verify units, signs, probability normalization, stability and positivity conditions, entropy production, extensivity/Euler homogeneity, fluctuation-response relations, and phase/reaction equilibrium conditions where applicable. Test relevant ideal-gas, dilute, noninteracting, zero-coupling, and large-system limits; check thermodynamic-limit and low/high-temperature approximations before use. For cycles check energy conservation and the Clausius inequality. Record each check and outcome.
7. **Stress-test and deliver:** vary approximations, ensemble or equation-of-state choices, boundary conditions, and uncertain parameters that could change the conclusion; flag changes that reverse the claim or exceed its error order. Separate equilibrium predictions from kinetics and finite-time transport, retain null/failed/unavailable results, record rejected alternatives, paths and hashes with `$science-provenance`, then use `$science-review` before presenting material conclusions.

## Outputs

Return `thermodynamic-evidence-v1` with: system and normalized inputs; boundary/initial conditions and assumptions; conventions, ensemble and selected potential with rationale; claim identifiers and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); claim class and falsifier; method/equations or computational settings; results with units and uncertainty; source and dependency records; checks and outcomes; sensitivity results; applicability limits; rejected alternatives and reasons; smallest falsifiable next action; artifact paths and hashes; and provenance and independent review receipts. Preserve null, failed, and unavailable results distinctly.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Do not infer a microscopic mechanism from a successful equation-of-state fit. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

The workflow is an original synthesis informed by the thermodynamics and probability treatment in
Crowell's CC BY-SA *Modern Physics*; provenance is in `../../docs/TEXTBOOK_SOURCES.md`.
