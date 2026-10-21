---
name: openmm-molecular-dynamics
description: "Build, equilibrate, run, checkpoint, and analyze reproducible molecular dynamics with OpenMM. Use for proteins, nucleic acids, solvated complexes, or parameterized protein-ligand systems when local CPU/GPU simulation is requested."
license: MIT
---

# OpenMM Molecular Dynamics

## Decision contract

State the system, scientific question, intended observables, simulation stages, evidence cutoff, baseline/control, and acceptance criteria before execution. Define claim IDs and falsifiers; a production trajectory can test only claims supported by the selected model and sampling. Missing parameter coverage, invalid structure, or unapproved compute is a stop condition.

## Workflow

1. Follow `$cx-compute-environment`. Ask once before installing pinned OpenMM and force-field packages and before GPU/long compute. State estimated system size, hardware, wall time, and output size.
2. Audit structures with `$cx-molecular-input-preparation`; parameterize ligands with `$cx-openff-parameterization` or another explicitly validated method. Validate topology, charges, periodic box, and atom mapping.
3. Record force fields, water model, ions/concentration, periodic box, constraints, nonbonded method/cutoff, timestep, integrator, thermostat/barostat, platform, precision, random seeds, and OpenMM/plugin versions. Preserve model and software revisions.
4. Build and serialize the topology/system. Minimize, then equilibrate through explicit restrained stages; inspect energy, temperature, pressure, density, clashes, and constraint failures against declared criteria before production.
5. Run production in checkpointed chunks. Keep state/checkpoint, trajectory, logs, serialized system, and exact driver/config under `artifacts/<run-id>/openmm/`. Verify restart identity and preserve failed/cancelled chunks.
6. Analyze prespecified observables with `$cx-mdanalysis-trajectory-analysis`. Estimate equilibration and autocorrelation; report uncertainty from effective samples or independent replicas. Save environment and artifact hashes with `$science-provenance`; require `$science-review` for material conclusions.

## Outputs

Return normalized system and parameter inputs, an execution/stage table with configuration, checks, completion/failure state, observable values with units and uncertainty, claim IDs and status (supported, contradicted, inconclusive, unavailable), exclusions, limitations, and smallest falsifiable next action. Separate process completion from scientific validation.

## Boundaries

One short trajectory is not an equilibrium ensemble or proof of stability. Do not compare force-field potential energies to experimental free energies. Checkpoint resume must preserve system, integrator state, and random-seed provenance; never present concatenated incompatible stages as one trajectory. Unmet equilibration or sampling criteria require an inconclusive result.
