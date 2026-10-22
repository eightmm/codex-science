---
name: gromacs-molecular-dynamics
description: "Prepare and run staged, checkpointed molecular dynamics with a pinned GROMACS build. Use when GROMACS workflows, HPC execution, established .mdp protocols, or interoperability with GROMACS topology/trajectory formats is required."
license: MIT
---

# GROMACS Molecular Dynamics

## Decision contract

Define the system, scientific question, intended observables, protocol, controls/baseline, and acceptance criteria before execution. Record the permitted claim types, evidence cutoff, and what result would falsify each claim. Inadequate parameter coverage, unresolved topology warnings, or unapproved long/cluster compute stops execution. Treat simulation observables as properties of the specified model and sampled trajectory; they do not establish experimental facts without independent experimental evidence.

## Reference usage

Read [references/gromacs-evidence.md](references/gromacs-evidence.md) before selecting or interpreting a production protocol, adjudicating equilibration/convergence, or making a claim from an observable. It defines simulation claim classes, uncertainty, control design, sensitivity checks, applicability, and GROMACS-specific failure detection.

## Workflow

1. **Gate:** Before installing or using a pinned GROMACS build, or starting long, GPU, or cluster compute, ask once for approval and state resources, wall time, storage, and scheduler plan; use the available cluster workflow skill for Slurm rather than launching untracked jobs. Record approval or the stop reason.
2. Define each claim, observable and units, baseline/control, falsifier, evidence cutoff, and acceptance threshold; reject claims that treat model output as experimental fact. Record the prespecified decision contract and read [references/gromacs-evidence.md](references/gromacs-evidence.md).
3. Audit inputs and ligand parameters as in `$cx-openmm-molecular-dynamics` input audit; preserve the original structure and atom mapping. If any parameter or mapping is unresolved, stop before simulation. Record input identities, force field, water/ions, topology include files, index groups, and warnings.
4. Pin GROMACS version/build flags and capture every `.mdp`, command, seed, hardware mapping, and environment; require restart inputs to match before resuming. Record hashes and execution configuration.
5. Generate the topology with `gmx grompp`; treat warnings as failures unless a documented scientific justification addresses each warning, and never use `-maxwarn` just to continue. Record exact command, output, resolved warning decisions, and topology artifact.
6. Minimize and equilibrate in explicit NVT/NPT stages; continue only when prespecified energy, temperature, pressure, density, box, constraint, and periodic-artifact criteria pass. Record stage diagnostics and failed criteria; otherwise stop or report inconclusive.
7. Run production in checkpointed chunks; append only when checkpoint and all simulation inputs match, and retain failed, cancelled, and incomplete runs. Store TPR, CPT, logs, energies, trajectory, topology, commands, and checksums under `artifacts/<run-id>/gromacs/`.
8. Analyze prespecified observables with `$cx-mdanalysis-trajectory-analysis`; require equilibration/convergence diagnostics, independent replicas where needed, autocorrelation-aware uncertainty, and applicable controls. Record claim IDs as supported, contradicted, inconclusive, or unavailable, exclusions, limitations, and the smallest falsifiable next action; save provenance with `$science-provenance` and require `$science-review` before material conclusions.
9. **Verify:** Reconcile artifact hashes, stage acceptance checks, failed-run records, and claim statuses against the frozen contract; any missing control, incompatible checkpoint, or unmet equilibration criterion makes the scientific conclusion inconclusive. Record the audit result and unresolved gaps.

## Outputs

Return a `gromacs-md-evidence-v1` record with required fields:

- System and input lineage (`system_and_input_lineage`).
- Protocol and software versions (`protocol_and_software_versions`).
- Stage execution table (`stage_execution_table`) with parameters, acceptance checks, and failure states.
- Observable measurements (`observable_measurements`) with units, uncertainty, and diagnostics.
- Claim register (`claim_register`) with claim IDs and supported/contradicted/inconclusive/unavailable status.
- Controls and sensitivity (`controls_and_sensitivity`), exclusions (`exclusions`), and limitations (`limitations`).
- Artifact hashes (`artifact_hashes`) and smallest falsifiable next action (`next_falsifiable_action`).

A completed job is not scientific validation.

## Boundaries

Never change timestep, constraints, coupling, or force-field settings silently. A completed job is not evidence of physical equilibration or convergence. Remove periodic jumps or align frames only on derived trajectories; retain raw data. Missing controls, incompatible checkpoints, or unmet equilibration criteria leave the scientific conclusion inconclusive.
