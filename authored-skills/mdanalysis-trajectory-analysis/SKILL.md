---
name: mdanalysis-trajectory-analysis
description: "Analyze OpenMM, GROMACS, and other molecular dynamics trajectories with MDAnalysis using topology-aware selections, periodic-boundary handling, prespecified observables, convergence checks, and uncertainty estimates."
license: MIT
---

# MDAnalysis Trajectory Analysis

## Workflow

1. Follow `$cx-compute-environment`; ask once before installing a pinned
   MDAnalysis stack or processing a large trajectory.
2. Verify topology/trajectory compatibility, atom ordering, units, frame times,
   periodic box, stage boundaries, and missing/corrupt frames. Preserve raw files.
3. Prespecify selections, alignment reference, PBC transformations, equilibration
   discard, stride, observables, and success criteria before viewing comparisons.
4. Compute only scientifically relevant observables: RMSD/RMSF, distances,
   contacts, hydrogen bonds, secondary structure, radius of gyration, SASA,
   clustering, or dimensionality reduction. Save scripts/configs and derived data.
5. Estimate autocorrelation/effective samples; use block bootstrap or independent
   replicas for uncertainty. Plot time series as well as aggregate distributions.
6. Record versions, commands, selections, transformations, and checksums under
   `artifacts/<run-id>/analysis/` and review with `$science-review`.

## Boundaries

- Alignment can hide domain motion; state the fitted atoms and show alternatives
  when conclusions depend on them.
- Frames are autocorrelated, not independent replicates.
- RMSD plateau alone does not establish equilibrium, convergence, or binding.

