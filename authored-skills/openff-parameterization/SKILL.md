---
name: openff-parameterization
description: "Parameterize drug-like small molecules for molecular simulation with pinned OpenFF Toolkit/force fields and explicit charge, stereochemistry, and coverage checks. Use before OpenMM or GROMACS when ligands or nonstandard organic molecules need parameters."
license: MIT
---

# OpenFF Parameterization

## Gate and workflow

1. Follow `$cx-compute-environment`; ask once before installing pinned OpenFF
   packages or charge backends and before compute.
2. Require a validated, explicit ligand microstate from
   `$cx-molecular-input-preparation`. Reject undefined required stereochemistry.
3. Pin toolkit, force-field file/version, aromaticity model, charge method,
   conformer source, and backend. Record formal and net partial charge.
4. Fail explicitly on unmatched parameters or unsupported chemistry. Never
   silently substitute generic atom types.
5. Inspect bond/angle/torsion assignments, high-energy geometry, net charge, and
   topology atom mapping. Run a short vacuum or solvent minimization smoke test.
6. Export the system and an atom-map/parameter manifest under
   `artifacts/<run-id>/parameters/`; retain the original molecule.

## Boundaries

- Force-field coverage does not establish accuracy for the chemical series.
- Metals, covalent inhibitors, unusual protonation, and reactive species need a
  specialized parameterization plan and validation.
- Do not compare energies across different force fields or charge protocols as
  if they share a scale.

