---
name: mdanalysis-trajectory-analysis
description: "Analyze OpenMM, GROMACS, and other molecular dynamics trajectories with MDAnalysis using topology-aware selections, periodic-boundary handling, prespecified observables, convergence checks, and uncertainty estimates."
license: MIT
---

# MDAnalysis Trajectory Analysis

## Decision contract

Define the system and claim, observable(s), units, comparison/baseline, analysis window, and acceptance or falsification criterion before inspecting comparisons. State the population of replicas/trajectories and evidence cutoff. If topology, atom order, units, or frame times cannot be reconciled without guessing, stop and report the input gap. Computed trajectory quantities describe simulation records, not experimental facts.

## Reference usage

Read [references/trajectory-evidence.md](references/trajectory-evidence.md) before choosing transformations/selections, assessing equilibration or convergence, or interpreting an observable. It defines analysis claim semantics, trajectory lineage and dependence, uncertainty, controls, sensitivity, applicability, and common MDAnalysis errors.

## Workflow

1. **Gate:** Follow `$cx-compute-environment`; ask once before installing a pinned MDAnalysis stack or processing a large trajectory. Record approval, estimated resources, or the stop reason.
2. Define claim IDs, observables and units, comparison/baseline, analysis window, replica population, falsifier, and acceptance criterion before inspecting comparisons; read [references/trajectory-evidence.md](references/trajectory-evidence.md). Record the frozen analysis contract.
3. Verify topology/trajectory compatibility, atom ordering, units, frame times, periodic box, stage boundaries, and missing/corrupt frames; if reconciliation requires guessing, stop. Preserve raw files and record checksums, exclusions, versions, and input provenance.
4. Prespecify selections, alignment reference, PBC transformations, equilibration discard, stride, observables, and success criteria before comparison; save exact commands/configuration and software version.
5. Compute only relevant observables (for example RMSD/RMSF, distances, contacts, hydrogen bonds, secondary structure, radius of gyration, SASA, clustering, or dimensionality reduction); save scripts and derived data without replacing raw trajectories.
6. Assess equilibration and convergence with time series, block averages, autocorrelation/effective samples, and independent replicas where available; show per-replica and aggregate results. Estimate uncertainty from correlated samples and record diagnostics.
7. Test material sensitivity to alignment, selections, PBC handling, windows, stride, and transformations; where upstream simulation settings can affect the conclusion, report that dependency and hand the required rerun to the simulation workflow. Record variants and changes in interpretation.
8. Store versions, commands, selections, transformations, source and derived checksums under `artifacts/<run-id>/analysis/`; record claims as supported, contradicted, inconclusive, or unavailable, alongside alternative interpretations, exclusions, limitations, and the smallest falsifiable next action. Handoff with `$science-provenance` and review with `$science-review`.
9. **Verify:** Reconcile every reported value to the declared selection, units, window, transformation, and source frames; check raw/derived separation and uncertainty diagnostics. If atom mapping, convergence, controls, or lineage is unresolved, report the claim as inconclusive or unavailable and record the gap.

## Outputs

Return a `mdanalysis-trajectory-evidence-v1` record with required fields:

- Input lineage (`input_lineage`), software versions (`software_versions`), and frozen analysis contract (`analysis_contract`).
- Measurements (`measurements`) with observable, unit, window, replica, estimate, uncertainty, and diagnostics.
- Claim register (`claim_register`) with claim IDs and supported/contradicted/inconclusive/unavailable status.
- Controls and sensitivity (`controls_and_sensitivity`), transformations (`transformations`), exclusions (`exclusions`), alternative interpretations (`alternative_interpretations`), and limitations (`limitations`).
- Artifact hashes (`artifact_hashes`) and smallest falsifiable next action (`next_falsifiable_action`).

Keep raw and transformed data distinct.

## Boundaries

Alignment can hide domain motion; state the fitted atoms and show alternatives when conclusions depend on them. Frames are autocorrelated, not independent replicates. RMSD plateau alone does not establish equilibrium, convergence, or binding. Results outside the sampled system, timescale, or force-field applicability remain exploratory.
