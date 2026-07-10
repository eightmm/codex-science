---
name: openmm-molecular-dynamics
description: "Build, equilibrate, run, checkpoint, and analyze reproducible molecular dynamics with OpenMM. Use for proteins, nucleic acids, solvated complexes, or parameterized protein-ligand systems when local CPU/GPU simulation is requested."
license: MIT
---

# OpenMM Molecular Dynamics

## Gate

Follow `$cx-compute-environment`. Ask once before installing pinned OpenMM and
force-field packages and before GPU/long compute. State estimated system size,
hardware, wall time, and output size.

## Workflow

1. Audit structures with `$cx-molecular-input-preparation`; parameterize ligands
   with `$cx-openff-parameterization` or another explicitly validated method.
2. Record force fields, water model, ions/concentration, periodic box, constraints,
   nonbonded method/cutoff, timestep, integrator, thermostat/barostat, platform,
   precision, random seeds, and OpenMM/plugin versions.
3. Build and serialize the topology/system. Minimize, then equilibrate through
   explicit restrained stages; inspect energy, temperature, pressure, density,
   clashes, and constraint failures before production.
4. Run production in checkpointed chunks. Keep state/checkpoint, trajectory,
   logs, serialized system, and exact driver/config under
   `artifacts/<run-id>/openmm/`.
5. Analyze prespecified observables with `$cx-mdanalysis-trajectory-analysis`.
   Estimate equilibration and autocorrelation; report uncertainty from effective
   samples or independent replicas.

## Boundaries

- One short trajectory is not an equilibrium ensemble or proof of stability.
- Do not compare force-field potential energies to experimental free energies.
- Checkpoint resume must preserve system, integrator state, and random-seed
  provenance; never present concatenated incompatible stages as one trajectory.

