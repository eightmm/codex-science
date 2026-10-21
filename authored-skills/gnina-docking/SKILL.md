---
name: gnina-docking
description: "Run reproducible local GNINA docking or CNN rescoring on protein-ligand systems. Use when GPU-assisted pose generation, refinement, or CNN reranking is wanted; keep CNN pose score, predicted affinity, and experimental affinity as distinct quantities."
license: MIT
---

# GNINA Docking

## Decision contract

Declare whether the goal is pose generation, redocking, or comparative ranking; specify target/receptor state, ligand microstates, pocket definition, evaluation split, and acceptance criterion. Assign claim IDs and define a control or observation that could falsify each material conclusion. Stop if receptor/ligand mapping, pocket, or split provenance is not adequate to preserve the intended question.

## Workflow

1. Follow `$cx-compute-environment`; ask once for the pinned GNINA binary/container, model download, GPU compute, and any structure download. Require prepared inputs from `$cx-molecular-input-preparation`. Prefer the official release binary or a digest-pinned container over a source build.
2. Validate receptor and ligand atom mapping, stereochemistry, protonation, and box coordinates. Record GNINA release, binary checksum/container digest, CUDA/GPU, CNN model, empirical scoring function, `cnn_scoring` mode, box/autobox source, seed, exhaustiveness, and number of modes.
3. Smoke-test the binary and one control complex. Use an experimental reference ligand for autoboxing only when legitimate for the evaluation split.
4. Run docking; retain SDF properties, raw log, receptor, reference ligand, exact command, and failures under `artifacts/<run-id>/gnina/`. Keep empirical energy, CNN pose score, and CNN affinity output in separate columns; do not select whichever score makes the result look best.
5. Validate redocking and ranking with `$cx-docking-validation`; compare against prespecified controls/baselines and retain exclusions. Record environment and artifact hashes with `$science-provenance`; use `$science-review` before material claims.

## Outputs

Return normalized inputs and assumptions, a machine-readable per-complex table with each score in its own field, pose metric, control status, failures/exclusions, and execution identity; claim IDs with supported/contradicted/inconclusive/unavailable status; uncertainty, applicability, limitations, and smallest falsifiable next action. A successful process does not validate the model scientifically.

## Boundaries

CNN confidence/score is not experimental affinity and is not calibrated across arbitrary targets or model versions. Blind whole-protein docking needs stronger controls and higher search effort; label it exploratory. Flexible-sidechain docking requires a justified residue set and separate validation; more flexibility does not guarantee realism. Failed controls or unresolved atom mapping prohibit a success claim.
