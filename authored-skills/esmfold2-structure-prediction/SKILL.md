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

Record the structural question, intended use, claim IDs, entities and chemistry,
expected model scope, and a falsifier before execution. Choose local inference or
the approved Biohub Platform and state the permitted inference. Keep this model
distinct from legacy ESMFold/`esmfold_v1`. A predicted structure is a model output,
not an experimental structure; pLDDT and PAE are confidence measures with
different meanings, not validation of a biological claim.

## Reference usage

Read [references/esmfold2-structure-evidence.md](references/esmfold2-structure-evidence.md)
before selecting input mode, interpreting confidence, evaluating a structure, or
making a target-specific claim. It defines confidence semantics, leakage and
source dependencies, controls, sensitivity, and applicability limits.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned Biohub
   `esm` commit/Transformers revision, downloading `biohub/ESMFold2` and ESMC
   weights, using GPU compute, or sending inputs to `https://biohub.ai`. Keep
   private sequences local unless remote transfer is explicitly approved. Resolve
   immutable revisions from authoritative `https://github.com/Biohub/esm` and
   immutable Hugging Face revisions for `biohub/ESMFold2` and its ESMC dependency
   before approval; never install `main`. Record approvals and unresolved gates.
2. Define protein/DNA entities, ligand CCDs, modifications, stoichiometry, MSA
   source, cofactors, metal ions, expected complex, intended use, and claim class.
   Validate IDs and residue/atom mappings. For ATP or another metal-dependent
   ligand, do not imply Mg-bound chemistry when Mg is absent; ask or explicitly
   model/report chosen CCD and cofactor state.
3. Record ESMFold2/ESMC weight revisions and checksums, input-builder version,
   loops, diffusion steps/samples, seed, device, precision, remote model ID when
   applicable, and whether the run uses single-sequence mode or an MSA. Record
   the training cutoff and any known overlap between target structures and model
   training data. Keep secrets and restricted weights out of provenance.
4. Smoke-test a short official example; continue only if the pinned release runs
   and its output schema validates. Run the real input into
   `artifacts/<run-id>/esmfold2/`; retain input objects, optional MSA, mmCIF,
   pLDDT/pTM/ipTM/PAE when actually present, logs, environment, timings, sampled
   structures, and failures.
5. Classify input, configuration, resource, and infrastructure failures; do not
   retry invalid inputs, bound transient retries, and preserve cancellation and
   failure logs. Check output completeness and residue/entity mapping before
   calculating downstream metrics; record the verify result.
6. Compare samples and inspect interface confidence, geometry, clashes, ligand
   state, and MSA dependence. Route structure rendering to
   `$cx-pymol-visualize` and geometry/contact annotation to
   `$cx-plip-interaction-analysis` using a prespecified pocket cutoff and atom
   map. Use an orthogonal predictor for decision-critical claims and document
   shared dependencies.
7. Use a known-structure control matched to modality and sequence/complex scope;
   report alignment and confidence behavior without treating a benchmark control
   as validation of the new target. Vary seeds, samples, single-sequence/MSA mode,
   and relevant entity/cofactor choices; downgrade if structure or interpretation
   changes materially.
8. Verify the training-cutoff and applicability limits using the reference.
   Record with `$science-provenance`; use `$science-review` before material
   conclusions. Report failures, nulls, uncertainty, and the smallest falsifiable
   experimental or computational next action.

## Outputs

Return one `esmfold2-structure-evidence-v1` record containing normalized inputs
and assumptions (`inputs`, `assumptions`), input entity mapping and hashes
(`entity_mapping`, `input_hashes`); claim identifier, class and status (`claim_id`, `claim_type`,
`status`); sequence/structure source, checkpoint, and dependency links
(`dependencies`, `source_provenance`); immutable model revisions, settings, input
mode, and cutoff (`execution`); known-structure and orthogonal controls
(`controls`); structure
paths/hashes and metrics actually emitted (`artifacts`, `metrics`); sample and
mode sensitivity with uncertainty (`sensitivity`, `uncertainty`); applicability
domain and limitations (`applicability`, `limitations`); failures/nulls
(`failures`); rejected alternatives and rationale (`alternatives`); and smallest
falsifiable next action (`next_action`). Status is `supported`, `contradicted`,
`inconclusive`, or `unavailable`. Distinguish process completion from scientific
validation and preserve unavailable metrics as unavailable. Record through
`$science-provenance`; `$science-review` is mandatory before material claims.

## Boundaries

ESMFold2 is not legacy ESMFold/`esmfold_v1`; record the exact model ID.
Confidence and lab validation reported for the model family do not validate a new
target, complex, binder, or affinity prediction. pLDDT is local residue confidence;
PAE describes predicted relative-position error between residues/entities where
provided. Neither is a calibrated probability of experimental correctness.

If the pinned local release cannot represent the requested entity or chemistry,
stop that path and route to `$cx-protenix-structure-prediction`,
`$cx-openfold3-structure-prediction`, or `$cx-boltz-structure-prediction` according
to modality and license; do not silently drop the unsupported entity. An
annotation or successful run does not validate binding or function. Respect each
tool's license and weights terms; keep private sequences local without explicit
remote-transfer approval. Follow `$cx-modeling-problem-execution` for execution.
