---
name: gnina-docking
description: "Run reproducible local GNINA docking or CNN rescoring on protein-ligand systems. Use when GPU-assisted pose generation, refinement, or CNN reranking is wanted; keep CNN pose score, predicted affinity, and experimental affinity as distinct quantities."
license: MIT
---

# GNINA Docking

## Gate and preflight

Follow `$cx-compute-environment`; ask once for the pinned GNINA binary/container,
model download, GPU compute, and any structure download. Require prepared inputs
from `$cx-molecular-input-preparation`. Prefer the official release binary or a
digest-pinned container over a source build.

## Workflow

1. Record GNINA release, binary checksum/container digest, CUDA/GPU, CNN model,
   empirical scoring function, `cnn_scoring` mode, box/autobox source, seed,
   exhaustiveness, and number of modes.
2. Smoke-test the binary and one control complex. Use an experimental reference
   ligand for autoboxing only when it is legitimate for the evaluation split.
3. Run docking; retain SDF properties, raw log, receptor, reference ligand, and
   exact command under `artifacts/<run-id>/gnina/`.
4. Keep empirical energy, CNN pose score, and CNN affinity output in separate
   columns. Do not select whichever score makes the result look best.
5. Validate redocking and ranking with `$cx-docking-validation`.

## Boundaries

- CNN confidence/score is not experimental affinity and is not calibrated across
  arbitrary targets or model versions.
- Blind whole-protein docking needs stronger controls and higher search effort;
  label it exploratory.
- Flexible-sidechain docking requires a justified residue set and separate
  validation; more flexibility does not guarantee realism.

