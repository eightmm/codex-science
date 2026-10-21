---
name: chai1-structure-prediction
description: "Run pinned Chai-1 inference for proteins, complexes, nucleic acids, ligands, covalent bonds, templates, or restraints. Use when multimolecular structure prediction needs Chai-1-specific inputs and confidence outputs."
license: MIT
---

# Chai-1 Structure Prediction

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Record the structural question, intended use, claim IDs, permitted inference, and model alternatives before execution. Define every entity and state: protein/RNA/DNA sequence, ligand SMILES/CCD, modifications, stoichiometry, covalent bonds, restraints, and templates. State what observation would change the conclusion and whether the requested output is exploratory or decision-bearing.

## Workflow

1. Ask once before installing a pinned `chai_lab` release, downloading weights, using GPU compute, or contacting public MSA/template servers. Name each remote host; never upload private sequences or structures without approval. Follow `$cx-compute-environment`.
2. Validate the input schema and all entity, residue, atom, bond, restraint, and template mappings. Preserve original and normalized inputs with hashes. Record unsupported fields rather than dropping them silently.
3. Pin Chai-1 version/commit, weight checksum, input schema, MSA/template mode, number of samples, seeds, hardware, precision, and all restraints. Record the environment and actual versions.
4. Smoke-test `chai-lab fold --help` and an upstream example. Validate expected files and structural content before the full run. Run validated FASTA/context into `artifacts/<run-id>/chai1/`; preserve inputs, MSAs, templates, restraint files, structures, scores, logs, and failures.
5. Separate model confidence, interface confidence, geometry checks, and any downstream affinity estimate. Compare samples; inspect clashes, ligand state, covalent geometry, low-confidence regions, and restraint satisfaction. Report public ColabFold-style MSA results separately from local MSA runs. Use a justified baseline for decision-critical claims.
6. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
7. Record execution and artifact hashes with `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized input/hash, model and weight revisions, MSA/template provenance, restraints, command/settings, hardware, outputs and hashes, metrics actually returned, failures/nulls, uncertainty, and limitations. Summarize sample diversity and alternative interpretations, then state the smallest falsifiable next action. Distinguish completed inference from scientific validation.

## Boundaries

Restraint satisfaction is not independent evidence when restraints were input. A plausible complex or ligand pose is not proof of binding or affinity. Do not treat confidence as calibrated probability or a model score as an experimental measurement. Stop when chemistry or mapping is unresolved, an approval gate is unmet, or the pinned release cannot represent an entity; retain an inconclusive/unavailable status and the failure record.
