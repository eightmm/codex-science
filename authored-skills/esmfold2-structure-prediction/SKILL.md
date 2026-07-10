---
name: esmfold2-structure-prediction
description: "Run Biohub ESMFold2 locally from the released Hugging Face weights or through the approved Biohub Platform. Use for all-atom prediction of proteins, complexes, DNA, modifications, and ligands with optional MSA input and diffusion sampling; distinct from the legacy ESMFold v1 model."
license: MIT
---

# ESMFold2 Structure Prediction

For a concrete input, follow `$cx-modeling-problem-execution` and continue through
execution rather than returning setup instructions.

## Gate and setup

Ask once before installing a pinned Biohub `esm` commit/Transformers revision,
downloading `biohub/ESMFold2` and ESMC weights, using GPU compute, or sending
inputs to `https://biohub.ai`. Keep private sequences local unless remote transfer
is explicitly approved. Resolve an immutable commit from the authoritative
`https://github.com/Biohub/esm` repository and immutable Hugging Face revisions
for `biohub/ESMFold2` and its ESMC dependency before approval; never install `main`.

## Workflow

1. Define protein/DNA entities, ligand CCDs, modifications, stoichiometry, MSA
   source, cofactors, metal ions, and expected complex. Validate IDs and
   residue/atom mappings. For ATP or another metal-dependent ligand, do not imply
   Mg-bound chemistry when Mg is absent; ask or explicitly model/report the
   chosen CCD and cofactor state.
2. Record ESMFold2/ESMC weight revisions and checksums, input builder version,
   loops, diffusion steps/samples, seed, device, precision, and remote model ID
   when applicable.
3. Smoke-test a short official example. Run the real input into
   `artifacts/<run-id>/esmfold2/`; retain input objects, optional MSA, mmCIF,
   pLDDT/pTM/ipTM, logs, environment, timings, and all sampled structures.
4. Validate the installed release's actual output schema before naming metrics.
   Compare samples and inspect interface confidence, geometry, clashes, ligand
   state, and MSA dependence. Route structure rendering to
   `$cx-pymol-visualize` and geometry/contact annotation to
   `$cx-plip-interaction-analysis` using a prespecified pocket cutoff and atom map.
   Use an orthogonal predictor for decision-critical claims.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- ESMFold2 is not legacy ESMFold/`esmfold_v1`; record the exact model ID.
- Confidence and lab validation reported for the model family do not validate a
  new target, complex, binder, or affinity prediction.
- If the pinned local release cannot represent the requested entity or chemistry,
  stop that path and route to `$cx-protenix-structure-prediction`,
  `$cx-openfold3-structure-prediction`, or `$cx-boltz-structure-prediction`
  according to modality and license; do not silently drop the unsupported entity.
