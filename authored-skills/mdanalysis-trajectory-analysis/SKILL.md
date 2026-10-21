---
name: mdanalysis-trajectory-analysis
description: "Analyze OpenMM, GROMACS, and other molecular dynamics trajectories with MDAnalysis using topology-aware selections, periodic-boundary handling, prespecified observables, convergence checks, and uncertainty estimates."
license: MIT
---

# MDAnalysis Trajectory Analysis

## Decision contract

Define the system and claim, observable(s), units, comparison/baseline, analysis window, and acceptance or falsification criterion before inspecting comparisons. State the population of replicas/trajectories and evidence cutoff. If topology, atom order, units, or frame times cannot be reconciled without guessing, stop and report the input gap.

## Workflow

1. Follow `$cx-compute-environment`; ask once before installing a pinned MDAnalysis stack or processing a large trajectory.
2. Verify topology/trajectory compatibility, atom ordering, units, frame times, periodic box, stage boundaries, and missing/corrupt frames. Preserve raw files; never silently repair or discard frames.
3. Prespecify selections, alignment reference, PBC transformations, equilibration discard, stride, observables, and success criteria before viewing comparisons. Record software version and exact commands/configuration.
4. Compute only relevant observables: RMSD/RMSF, distances, contacts, hydrogen bonds, secondary structure, radius of gyration, SASA, clustering, or dimensionality reduction. Save scripts/configs and derived data.
5. Estimate autocorrelation/effective samples; use block bootstrap or independent replicas for uncertainty. Plot time series as well as aggregate distributions; report sensitivity to alignment, windows, and other material analysis choices.
6. Record versions, commands, selections, transformations, source and derived checksums under `artifacts/<run-id>/analysis/`; hand off with `$science-provenance` and review with `$science-review`.

## Outputs

Return input lineage and normalized analysis settings, a machine-readable measurement table with observable, unit, window, replica, estimate, uncertainty, diagnostics, and exclusions; claim IDs with supported/contradicted/inconclusive/unavailable status; alternative interpretations, limitations, and smallest falsifiable next action. Keep raw and transformed data distinct.

## Boundaries

Alignment can hide domain motion; state the fitted atoms and show alternatives when conclusions depend on them. Frames are autocorrelated, not independent replicates. RMSD plateau alone does not establish equilibrium, convergence, or binding. Results outside the sampled system, timescale, or force-field applicability remain exploratory.
