---
name: gromacs-molecular-dynamics
description: "Prepare and run staged, checkpointed molecular dynamics with a pinned GROMACS build. Use when GROMACS workflows, HPC execution, established .mdp protocols, or interoperability with GROMACS topology/trajectory formats is required."
license: MIT
---

# GROMACS Molecular Dynamics

## Gate and preflight

Ask once before installing/using a pinned GROMACS build and before long, GPU, or
cluster compute. State resources, wall time, storage, and scheduler plan. Use the
available cluster workflow skill for Slurm rather than launching untracked jobs.

## Workflow

1. Audit inputs and ligand parameters as in `$cx-openmm-molecular-dynamics`.
2. Record GROMACS version/build flags, force fields, water/ions, topology include
   files, every `.mdp`, index groups, restraints, seeds, and hardware mapping.
3. Run `gmx grompp` with warnings treated as failures; do not use `-maxwarn`
   merely to continue. Explain and record any scientifically justified exception.
4. Minimize and equilibrate in explicit NVT/NPT stages. Inspect energies,
   temperature, pressure, density, box, constraints, and periodic artifacts.
5. Run production with checkpoints and append safely only when inputs match.
   Preserve TPR, CPT, logs, energies, trajectory, topology, commands, and checksums
   under `artifacts/<run-id>/gromacs/`.
6. Analyze with `$cx-mdanalysis-trajectory-analysis`; use independent replicas
   and uncertainty appropriate to autocorrelated trajectories.

## Boundaries

- Never change timestep, constraints, coupling, or force-field settings silently.
- A completed job is not evidence of physical equilibration or convergence.
- Remove periodic jumps/align frames only on derived trajectories; retain raw data.

