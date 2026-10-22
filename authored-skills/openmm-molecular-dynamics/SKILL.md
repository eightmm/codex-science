---
name: openmm-molecular-dynamics
description: "Build, equilibrate, run, checkpoint, and analyze reproducible molecular dynamics with OpenMM. Use for proteins, nucleic acids, solvated complexes, or parameterized protein-ligand systems when local CPU/GPU simulation is requested."
license: MIT
---

# OpenMM Molecular Dynamics

## Decision contract

State the system, scientific question, intended observables, simulation stages, evidence cutoff, baseline/control, and acceptance criteria before execution. Define claim IDs and falsifiers; a production trajectory can test only claims supported by the selected model and sampling. Missing parameter coverage, invalid structure, or unapproved compute is a stop condition. Simulation observables describe the specified model and sampled trajectory; they are not experimental facts.

## Reference usage

Read [references/openmm-evidence.md](references/openmm-evidence.md) before choosing integrator/platform settings, evaluating equilibration or convergence, or interpreting a simulated observable. It defines OpenMM-specific claim semantics, reproducibility dependencies, controls, sensitivity checks, and failure detection.

## Workflow

1. **Gate:** Follow `$cx-compute-environment`; ask once before installing pinned OpenMM or force-field packages and before GPU or long compute. State estimated system size, hardware, wall time, and output size; record approval or the stop reason.
2. Define claim IDs, observables and units, comparison baseline/control, falsifiers, evidence cutoff, and acceptance criteria; reject claims that treat simulation output as an experiment. Record the prespecified contract and read [references/openmm-evidence.md](references/openmm-evidence.md).
3. Audit structures with `$cx-molecular-input-preparation`; parameterize ligands with `$cx-openff-parameterization` or another explicitly validated method. If structure, topology, charges, periodic box, or atom mapping is invalid or unresolved, stop and record the gap.
4. Pin and record force fields, water model, ions/concentration, periodic box, constraints, nonbonded method/cutoff, timestep, integrator, thermostat/barostat, platform, precision, random seeds, and OpenMM/plugin versions; preserve model and software revisions.
5. Build and serialize topology/system; minimize and equilibrate through explicit restrained stages. Proceed to production only if declared energy, temperature, pressure, density, clash, and constraint criteria pass; record diagnostics and stop or downgrade on failure.
6. Run production in checkpointed chunks; resume only with matching system, integrator state, random-seed provenance, and configuration. Keep state/checkpoint, trajectory, logs, serialized system, and exact driver/config under `artifacts/<run-id>/openmm/`, including failed or cancelled chunks.
7. Analyze prespecified observables with `$cx-mdanalysis-trajectory-analysis`; assess equilibration, autocorrelation, block stability, and independent replicas. Estimate uncertainty appropriate to correlated samples; record claim IDs as supported, contradicted, inconclusive, or unavailable, with exclusions and limitations.
8. Save environment and artifact hashes with `$science-provenance`; require `$science-review` for material conclusions. **Verify:** reconcile hashes, stage checks, restart identity, controls, sensitivity results, and claim statuses against the frozen contract; any unmet equilibration or sampling criterion makes the conclusion inconclusive. Record the audit and next falsifiable action.

## Outputs

Return an `openmm-md-evidence-v1` record with required fields:

- System and input lineage (`system_and_input_lineage`) and model/software versions (`model_and_software_versions`).
- Simulation configuration (`simulation_configuration`) and stage execution table (`stage_execution_table`) with checks and failure states.
- Observable measurements (`observable_measurements`) with units, uncertainty, and diagnostics.
- Claim register (`claim_register`) with claim IDs and supported/contradicted/inconclusive/unavailable status.
- Controls and sensitivity (`controls_and_sensitivity`), restart lineage (`restart_lineage`), exclusions (`exclusions`), and limitations (`limitations`).
- Artifact hashes (`artifact_hashes`) and smallest falsifiable next action (`next_falsifiable_action`).

Separate process completion from scientific validation.

## Boundaries

One short trajectory is not an equilibrium ensemble or proof of stability. Do not compare force-field potential energies to experimental free energies. Checkpoint resume must preserve system, integrator state, and random-seed provenance; never present concatenated incompatible stages as one trajectory. Unmet equilibration or sampling criteria require an inconclusive result.
