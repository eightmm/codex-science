---
name: condensed-matter-solid-state
description: "Analyze condensed-matter and solid-state models and computations. Use for crystal symmetry, reciprocal space, electronic bands, density of states, Fermi surfaces, phonons, transport, magnetism, superconductivity, defects, and phase behavior."
license: MIT
---

# Condensed Matter and Solid State

## Define the material model

State composition, structure, dimensionality, symmetry, boundary conditions, temperature, pressure, charge
state, disorder, interactions, and observables. Distinguish a finite cluster, periodic crystal, continuum model,
and measured sample. Record lattice, reciprocal-lattice, Brillouin-zone, spin, and unit conventions.

## Choose the representation

- Use symmetry and reciprocal space before brute-force band, phonon, or scattering calculations.
- Declare independent-particle, tight-binding, mean-field, quasiparticle, harmonic, or continuum approximations.
- Relate bands and density of states to occupations, Fermi level, response, and experimentally accessible signals.
- Treat defects, disorder, surfaces, and finite size as model changes, not minor plotting details.
- For phase claims, specify order parameter, thermodynamic limit, symmetry breaking, and finite-size evidence.

## Verify

- Check space-group or lattice symmetries, degeneracies, charge count, sum rules, and units.
- Converge basis, cell size, k-point mesh, energy cutoff, broadening, temperature, and solver tolerance separately.
- Recover atomic, free-electron, long-wavelength, or high-temperature limits where appropriate.
- Compare total-energy differences only after matching convergence and reference states.
- Separate numerical gaps or order from finite-size, smearing, and model artifacts; compare with experimental uncertainty.

## Deliver

Report structure, Hamiltonian or free energy, approximations, numerical settings, convergence, symmetry checks,
observables, and the distinction between model prediction and material-specific evidence.

## Source basis

Original synthesis informed by Crowell's openly licensed *Modern Physics* and open computational-physics
validation guidance recorded in `../../docs/TEXTBOOK_SOURCES.md`.
