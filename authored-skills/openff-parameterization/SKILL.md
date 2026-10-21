---
name: openff-parameterization
description: "Parameterize drug-like small molecules for molecular simulation with pinned OpenFF Toolkit/force fields and explicit charge, stereochemistry, and coverage checks. Use before OpenMM or GROMACS when ligands or nonstandard organic molecules need parameters."
license: MIT
---

# OpenFF Parameterization

## Decision contract

Specify the simulation system and ligand microstate to parameterize, intended engine/use, required chemical domain, and acceptance checks. Record claim IDs only for parameter coverage/representation claims; parameter assignment is not evidence that a force field is accurate for a series. Undefined required stereochemistry or a chemically unsupported state is a stop condition.

## Workflow

1. Follow `$cx-compute-environment`; ask once before installing pinned OpenFF packages or charge backends and before compute.
2. Require a validated, explicit ligand microstate from `$cx-molecular-input-preparation`. Validate atom identity, bond order, stereochemistry, valence, and formal charge; preserve the original molecule and mapping.
3. Pin toolkit, force-field file/version, aromaticity model, charge method, conformer source, and backend. Record formal and net partial charge and the source for each choice.
4. Fail explicitly on unmatched parameters or unsupported chemistry. Never silently substitute generic atom types. Inspect bond/angle/torsion assignments, high-energy geometry, net charge, and topology atom mapping.
5. Run a short vacuum or solvent minimization smoke test using the intended downstream engine when available. Check finite energies, geometry, charge consistency, atom count, and successful serialization. Keep failures and bounded remediation attempts explicit.
6. Export the system and an atom-map/parameter manifest under `artifacts/<run-id>/parameters/`; retain the original molecule. Record command, environment, checksums, and limitations with `$science-provenance`; obtain `$science-review` before using parameters for material claims.

## Outputs

Return normalized ligand state, assumptions, parameter coverage table by atom/type, charge and mapping checks, smoke-test result, exclusions/failures, tool and force-field identity, claim IDs with supported/contradicted/inconclusive/unavailable status, uncertainty, limitations, and smallest falsifiable next action. Process success is not scientific validation.

## Boundaries

Force-field coverage does not establish accuracy for the chemical series. Metals, covalent inhibitors, unusual protonation, and reactive species need a specialized parameterization plan and validation. Do not compare energies across different force fields or charge protocols as if they share a scale. No silent chemistry repair or generic atom typing is allowed.
