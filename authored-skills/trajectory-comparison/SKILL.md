---
name: trajectory-comparison
description: "Compare existing molecular trajectories or exported observable series with frozen topology, atom selection, units and PBC handling, independent replica statistics, block uncertainty and drift diagnostics. No simulation launch."
license: MIT
---

# Trajectory Comparison

## Decision contract

Freeze the ordered conditions, observable, topology/atom identity, processing
window, units, independent replica unit, controls and diagnostic thresholds.
The decision is a qualified comparison of supplied data, with physical validity
and convergence assessed separately.

## Reference usage

Use after explicit invocation through the active Codex Science coordinator. This conductor operates on existing trajectories or exported series; it does not authorize a new simulation. Load [stages](references/stages.md) before intake and [method discovery](references/method-discovery.md) before choosing an analyzer. Load [method seeds](references/methods.json) only when selecting a method and [plan](references/plan.json) for checkpoint initialization.

## Workflow

1. **Intake:** freeze question, ordered conditions, topology/atom identity, trajectory/segment ancestry, independent replicas, producer engine and force-field identity. Preserve raw files and hashes.
2. **Plan:** choose analyzer and frozen observable, units, selections, alignment, PBC transformations, time/discard/stride window, block lengths, controls, drift thresholds and contrast. Record method references and code/environment hashes.
3. **Validate:** verify topology and frame identity, expected time grid, missing frames, finite values, boxes and PBC. Unresolved mappings or units stop comparison; do not guess conversions.
4. **Measure:** use `$cx-mdanalysis-trajectory-analysis` for approved existing trajectories, or the stdlib helper for small exported series. Preserve derived series and raw/derived lineage. Read upstream skill boundaries first.
5. **Diagnose:** retain per-replica means, blocks, block-size sensitivity, time traces, half-window drift and sampling gaps. Frames and restart segments are not replicas.
6. **Compare:** equal-weight independent replica means; report ordered contrast and between-replica SE. Failed controls, drift or inadequate sampling require exploratory/inconclusive conclusions. Never infer convergence from stable RMSD.
7. **Review:** save ordinary hashed artifacts in the existing checkpoint/manifest, link qualified claims separately, use `$science-provenance` and independent `$science-review`, and state the smallest falsifiable next action.

## Outputs

Return `trajectory-comparison-result-v1`, per-replica and block statistics,
condition summaries, ordered contrast, diagnostic reasons and limitations. Save
raw/derived hashes, method/processing identities and command/environment records
as ordinary manifest artifacts. Obtain the existing independent review receipt
before treating a comparison as reviewed.

## Boundaries

No new checkpoint state, global schema or model backend. Any installation, new simulation, GPU/remote or heavy work requires its existing approval route through `$cx-openmm-molecular-dynamics` or `$cx-gromacs-molecular-dynamics`. Analyzer choice does not choose a force field. An offline fixture pass proves analysis contract behavior only, not physical validity, binding, affinity or biological efficacy.
