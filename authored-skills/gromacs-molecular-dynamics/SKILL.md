---
name: gromacs-molecular-dynamics
description: "Prepare and run staged, checkpointed molecular dynamics with a pinned GROMACS build. Use when GROMACS workflows, HPC execution, established .mdp protocols, or interoperability with GROMACS topology/trajectory formats is required."
license: MIT
---

# GROMACS Molecular Dynamics

## Decision contract

Define system, scientific question, intended observables, protocol, controls/baseline, and acceptance criteria before execution. Record the permitted claim types, evidence cutoff, and what result would falsify each claim. Inadequate parameter coverage, unresolved topology warnings, or unapproved long/cluster compute stops execution.

## Workflow

1. Ask once before installing/using a pinned GROMACS build and before long, GPU, or cluster compute. State resources, wall time, storage, and scheduler plan. Use the available cluster workflow skill for Slurm rather than launching untracked jobs.
2. Audit inputs and ligand parameters as in `$cx-openmm-molecular-dynamics`; preserve structure and atom mapping. Record GROMACS version/build flags, force fields, water/ions, topology include files, every `.mdp`, index groups, restraints, seeds, and hardware mapping.
3. Validate topology generation with `gmx grompp` and warnings treated as failures; do not use `-maxwarn` merely to continue. Explain and record any scientifically justified exception. Preserve the exact command and outputs.
4. Minimize and equilibrate in explicit NVT/NPT stages. Inspect energies, temperature, pressure, density, box, constraints, and periodic artifacts against prespecified criteria before production.
5. Run production with checkpoints and append safely only when inputs match. Preserve TPR, CPT, logs, energies, trajectory, topology, commands, and checksums under `artifacts/<run-id>/gromacs/`. Record failed, cancelled, and incomplete runs.
6. Analyze with `$cx-mdanalysis-trajectory-analysis`; use independent replicas and uncertainty appropriate to autocorrelated trajectories. Save configuration and hashes with `$science-provenance`; require `$science-review` before material conclusions.

## Outputs

Return normalized system/protocol, a stage execution table with versions, parameters, acceptance checks and failure states, observable measurements with units and uncertainty, claim IDs marked supported/contradicted/inconclusive/unavailable, exclusions, limitations, and smallest falsifiable next action. A completed job is not scientific validation.

## Boundaries

Never change timestep, constraints, coupling, or force-field settings silently. A completed job is not evidence of physical equilibration or convergence. Remove periodic jumps/align frames only on derived trajectories; retain raw data. Missing controls, incompatible checkpoints, or unmet equilibration criteria leave the scientific conclusion inconclusive.
