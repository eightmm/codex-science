---
name: bindcraft-binder-design
description: "Run a pinned BindCraft campaign for de novo protein binders using AlphaFold2 optimization, ProteinMPNN, PyRosetta, and configurable filters. Use only when the target structure, hotspot strategy, candidate budget, dependency licenses, and experimental handoff are explicit."
license: MIT
---

# BindCraft Binder Design

Use `$cx-modeling-problem-execution` for a concrete target and continue through
pilot, campaign, filtering, orthogonal validation, and review.

## License and gate

Ask once before running the installer, using conda/mamba, downloading AlphaFold2
weights, accepting PyRosetta terms, and launching GPU/Slurm compute. Pin BindCraft
release/commit and every dependency; state target, candidate/final-design budget,
wall time, storage, and experimental non-goals.

## Workflow

1. Audit target structure/assembly/chains, missing regions, ligands, hotspot
   residues and numbering, binder length, off-targets, and desired specificity.
2. Pin settings, filter and advanced JSON, algorithm, seeds, AF2/MPNN/PyRosetta
   versions, stop criteria, ranking rule, and compute resources.
3. Smoke-test an official example and a small target-specific pilot. If viable,
   run the approved campaign into `artifacts/<run-id>/bindcraft/`; preserve all
   trajectories, sequences, structures, metrics, configs, logs, and rejects.
4. Report the full funnel, diversity, novelty, interface geometry, clashes,
   predicted confidence, filter sensitivity, and failure reasons. Re-score with
   an orthogonal structure model and evaluate off-target/specificity hypotheses.
5. Record with `$science-provenance`; run `$science-review` before candidate selection.

## Boundaries

- ipTM and in-silico filters are not affinity or experimental validation.
- Do not auto-order or synthesize candidates. PyRosetta and model assets have
  separate terms; this skill does not grant commercial rights.

