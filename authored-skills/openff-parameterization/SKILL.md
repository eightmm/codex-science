---
name: openff-parameterization
description: "Parameterize drug-like small molecules for molecular simulation with pinned OpenFF Toolkit/force fields and explicit charge, stereochemistry, and coverage checks. Use before OpenMM or GROMACS when ligands or nonstandard organic molecules need parameters."
license: MIT
---

# OpenFF Parameterization

## Decision contract

Specify the simulation system and ligand microstate to parameterize, intended engine/use, required chemical domain, and acceptance checks. Record claim IDs only for parameter coverage/representation claims; parameter assignment is not evidence that a force field accurately predicts physical behavior for a molecule or series. Undefined required stereochemistry or a chemically unsupported state is a stop condition. Use the status vocabulary `supported`, `contradicted`, `inconclusive`, and `unavailable` for each claim.

## Reference usage

- Read [references/parameterization-evidence.md](references/parameterization-evidence.md) before assigning material claims about force-field coverage, charges, or transferability; it defines claim classes, dependence, controls, sensitivity, and limits.
- Record precise toolkit, Sage release, charge backend, and force-field identity from the installed release metadata and generated parameter files; the reference does not replace version-specific tool documentation.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing pinned OpenFF packages or charge backends and before compute; continue only after the user approves the proposed versions, environment, and compute scope. Record the approval or the gated status.
2. Follow `$cx-compute-environment` and `$cx-molecular-input-preparation`; require a validated explicit ligand microstate. If atom identity, bond order, stereochemistry, valence, or formal charge is unresolved, stop; record the input hash, atom mapping, unresolved fields, and status.
3. Pin toolkit, Sage force-field release, force-field file/version, aromaticity model, charge method/backend, conformer source, and intended engine. If a required identity cannot be pinned, stop before assignment; record selected versions, the source for each choice, and rationale.
4. Assign parameters and check atom/type, bond, angle, and torsion coverage, generic or unassigned terms, formal/net partial charge, topology mapping, and high-energy geometry. Continue only with complete supported assignments or explicit exclusions; record per-atom/type coverage and every failure without silent substitution.
5. Run the smallest intended-engine vacuum or solvent minimization smoke test when authorized and available. Require finite energies, plausible geometry, charge consistency, atom count, and successful serialization; preserve failed attempts and bounded remediation. Record checks and deviations.
6. Vary charge method and conformer choice when claims depend on them, then compare assignment/geometry or energies only within a declared common protocol. Export the system and atom-map/parameter manifest under `artifacts/<run-id>/parameters/`, retaining the original molecule. State whether results are assignment evidence or validated physical behavior; preserve uncertainty, exclusions, command, environment, and checksums with `$science-provenance`, and obtain `$science-review` before material claims.

## Outputs

Return `openff-parameterization-evidence-v1` with: normalized ligand state; assumptions; claim identifier (`claim_id`) and claim status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); parameter coverage table by atom/type; charge and atom-mapping checks; smoke-test result; exclusions and failures; tool, toolkit, force-field release and file identity, charge method and conformer source; uncertainty; limitations and applicability domain; artifact paths and hashes; and smallest falsifiable next action. Process success is not scientific validation.

## Boundaries

Force-field coverage does not establish accuracy for the chemical series. Metals, covalent inhibitors, unusual protonation, and reactive species need a specialized parameterization plan and validation. Do not compare energies across different force fields or charge protocols as if they share a scale. Do not silently repair chemistry or use generic atom typing. A favorable minimization is a sanity check, not experimental validation.
