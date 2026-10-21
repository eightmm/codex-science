---
name: openfold3-structure-prediction
description: "Run pinned OpenFold3 preview inference for proteins, nucleic acids, noncanonical residues, and small-molecule complexes. Use when an open AlphaFold3-style workflow is wanted and preview-status limitations are acceptable."
license: MIT
---

# OpenFold3 Structure Prediction

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Record the structural question, intended use, claim IDs, entity/chemical state, and what would falsify the interpretation. State that OpenFold3 is a preview and define the acceptable inference level. Keep model prediction separate from experimental evidence.

## Workflow

1. Ask once before installing a pinned OpenFold3 preview release, running setup, downloading parameters/databases, contacting an MSA server, or using GPU/remote compute. Never send private sequences to public services without approval. Follow `$cx-compute-environment`.
2. Define query JSON entities, sequences, ligand states, modifications, stoichiometry, templates, MSAs, and covalent relationships. Validate IDs and atom/residue mappings; preserve/hash input and record unsupported fields instead of silently dropping them.
3. Pin preview release/commit, parameter checksum, setup version, database snapshots, kernel versions, MSA/template mode, seeds, samples, and hardware. Record actual environment and versions.
4. Smoke-test the official example and validate expected structure and confidence outputs. Run `run_openfold predict` into `artifacts/<run-id>/openfold3/`; retain query JSON, feature inputs, structures, confidence outputs, environment, exact command, logs, and failures.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Check chemistry, atom mapping, clashes, chain/interface confidence, PAE-like uncertainty, sample diversity, and template dependence. Compare an appropriate independent model for decision-critical claims and report shared data/method dependencies.
7. Record with `$science-provenance`; run `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized input/hash, preview code and parameter/database revisions, settings, hardware, artifact paths/hashes, observed metrics, failures/nulls, uncertainty, and limitations. Summarize plausible alternatives and the smallest falsifiable next action. State process completion separately from scientific validation.

## Boundaries

Label the software and results as OpenFold3 preview; do not claim final-model parity or full AlphaFold3 modality parity. Predicted ligand poses and interfaces do not establish binding or affinity. Do not treat preview output as experimental truth. Stop if required chemistry is unsupported, input mapping is unresolved, or approval is unmet; retain the failure and report the claim as inconclusive or unavailable.
