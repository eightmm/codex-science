---
name: condensed-matter-solid-state
description: "Analyze condensed-matter and solid-state models and computations. Use for crystal symmetry, reciprocal space, electronic bands, density of states, Fermi surfaces, phonons, transport, magnetism, superconductivity, defects, and phase behavior."
license: MIT
---

# Condensed Matter and Solid State

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [solid-state-evidence.md](references/solid-state-evidence.md) before choosing a cell or Brillouin-zone convention, reporting electronic or magnetic structure, making a convergence claim, or comparing a calculation with experiment. It defines claim classes, control calculations, convergence and sensitivity checks, dependence tracking, and applicability limits.

## Workflow

1. [step-1] Define composition, structure, dimensionality, symmetry, boundary conditions, thermodynamic state, charge, disorder, interactions, and the requested observable; distinguish a finite cluster, periodic crystal, continuum model, and measured sample, stop and clarify any missing choice that changes the model, and record the normalized system and evidence cutoff.
2. [step-2] Fix units, lattice vectors, primitive or conventional cell, reciprocal basis, Brillouin zone, symmetry operations, and spin convention; verify the cell-volume and reciprocal-vector conventions, and record the transformations and software versions.
3. [step-3] Use symmetry and reciprocal space before brute-force band, phonon, or scattering calculations; select and declare the Hamiltonian and independent-particle, tight-binding, mean-field, quasiparticle, harmonic, or continuum approximation appropriate to the regime, state omitted physics and a falsifier, and record the method and rejected alternatives.
4. [step-4] Establish a minimal control against an analytic or limiting case, charge counting, symmetry, degeneracies, sum rules, or a known reference material as applicable; investigate mismatches before production calculations, and preserve the control result.
5. [step-5] Converge basis and energy cutoff, cell or supercell size, k-point mesh, smearing, temperature, and solver tolerance independently; accept a setting only when the target observable changes less than its predeclared tolerance across further refinement, and record every series including failures.
6. [step-6] For magnetic or broken-symmetry claims, compare plausible spin orders, initializations, and symmetry constraints at matched numerical precision; specify the order parameter, symmetry breaking, thermodynamic-limit or finite-size criterion for phase claims, treat metastability or initialization dependence as unresolved, and record energies, moments, and convergence per state.
7. [step-7] Vary consequential model choices and uncertain inputs, including functional, spin-orbit treatment, defect concentration, finite-size and periodic-image separation; downgrade a claim when conclusions change beyond the stated decision threshold, and record the sensitivity range.
8. [step-8] Relate bands and density of states to occupations, Fermi level, response, and the measured signal; match the calculation to the experimental observable, state, and resolution rather than comparing unlike quantities, reconcile uncertainties and dependencies, classify each claim, and record the applicability domain, limitations, and falsifiable next check.

## Outputs

Return a concise summary and a machine-readable `solid-state-evidence-v1` record with required fields: `system`, `observable`, `assumptions`, `claim_id`, `claim_type`, `status` (`supported`, `contradicted`, `inconclusive`, or `unavailable`), `method`, `equations_or_hamiltonian`, `settings`, `controls`, `checks_and_outcomes`, `convergence`, `sensitivity`, `result`, `units`, `uncertainty`, `dependencies`, `applicability_domain`, `limitations`, `rejected_alternatives_with_reasons`, `next_action`, and `artifacts` (paths and hashes). Preserve null, failed, and unavailable results distinctly. Record artifacts with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result. Do not infer a measured band gap directly from a semilocal Kohn-Sham gap, a bulk property from an unconverged finite cell, or a ground state from one magnetic initialization.

## Source basis

Original synthesis informed by Crowell's openly licensed *Modern Physics* and open computational-physics
validation guidance recorded in `../../docs/TEXTBOOK_SOURCES.md`.
