---
name: esmfold2-structure-prediction
description: "Run Biohub ESMFold2 locally from the released Hugging Face weights or through the approved Biohub Platform. Use for all-atom prediction of proteins, complexes, DNA, modifications, and ligands with optional MSA input and diffusion sampling; distinct from the legacy ESMFold v1 model."
license: MIT
---

# ESMFold2 Structure Prediction

For a concrete input, follow `$cx-modeling-problem-execution` and continue through
execution rather than returning setup instructions.

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Record the structural question, intended use, claim IDs, entities and chemistry, expected model scope, and a falsifier before execution. Choose local inference or the approved Biohub Platform and state the permitted inference. Keep this model distinct from legacy ESMFold/`esmfold_v1`.

## Workflow

1. Ask once before installing a pinned Biohub `esm` commit/Transformers revision, downloading `biohub/ESMFold2` and ESMC weights, using GPU compute, or sending inputs to `https://biohub.ai`. Keep private sequences local unless remote transfer is explicitly approved. Resolve an immutable commit from authoritative `https://github.com/Biohub/esm` and immutable Hugging Face revisions for `biohub/ESMFold2` and its ESMC dependency before approval; never install `main`.
2. Define protein/DNA entities, ligand CCDs, modifications, stoichiometry, MSA source, cofactors, metal ions, and expected complex. Validate IDs and residue/atom mappings. For ATP or another metal-dependent ligand, do not imply Mg-bound chemistry when Mg is absent; ask or explicitly model/report chosen CCD and cofactor state.
3. Record ESMFold2/ESMC weight revisions and checksums, input-builder version, loops, diffusion steps/samples, seed, device, precision, and remote model ID when applicable. Keep secrets and restricted weights out of provenance.
4. Smoke-test a short official example and validate the installed release's output schema before naming metrics. Run the real input into `artifacts/<run-id>/esmfold2/`; retain input objects, optional MSA, mmCIF, pLDDT/pTM/ipTM when actually present, logs, environment, timings, sampled structures, and failures.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Compare samples and inspect interface confidence, geometry, clashes, ligand state, and MSA dependence. Route structure rendering to `$cx-pymol-visualize` and geometry/contact annotation to `$cx-plip-interaction-analysis` using a prespecified pocket cutoff and atom map. Use an orthogonal predictor for decision-critical claims and document shared dependencies.
7. Record with `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), input entity mapping/hash, immutable model and dependency revisions, settings, MSA/remote provenance, output paths/hashes, metrics actually emitted, failures/nulls, uncertainty, and limitations. Include sample variation, interpretation, and the smallest falsifiable next action. Distinguish process completion from scientific validation.

## Boundaries

ESMFold2 is not legacy ESMFold/`esmfold_v1`; record the exact model ID. Confidence and lab validation reported for the model family do not validate a new target, complex, binder, or affinity prediction. If the pinned local release cannot represent the requested entity or chemistry, stop that path and route to `$cx-protenix-structure-prediction`, `$cx-openfold3-structure-prediction`, or `$cx-boltz-structure-prediction` according to modality and license; do not silently drop the unsupported entity. An annotation or successful run does not validate binding or function.
