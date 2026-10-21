---
name: alphafold2-structure-prediction
description: "Run reproducible AlphaFold2 monomer or multimer inference with pinned code, parameters, sequence databases, template cutoff, and seeds. Use when a local AlphaFold2 installation or approved container/database setup is available; use AlphaFold DB lookup instead for an existing canonical model."
license: MIT
---

# AlphaFold2 Structure Prediction

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

Before a run, record the intended structural question and claim IDs; exact sequences and constructs; organism, chain stoichiometry, oligomeric state, modifications, and ligand state; template cutoff; and intended use. State whether the result is exploratory or decision-bearing, what structural observation would change the conclusion, and what input or model limitation would make the result inconclusive. Use `$cx-alphafold-structure-analysis` when AlphaFold DB already contains the desired canonical monomer.

## Workflow

1. Inspect and normalize sequences, chain IDs, construct boundaries, stoichiometry, modifications, and template/date assumptions. Preserve the submitted input and its hash.
2. Prefer an existing validated installation. Before installing or pulling a pinned container, downloading model parameters or sequence databases, querying remote MSA services, or using GPU compute, ask once and state that a full official setup can require hundreds of GB of downloads and several TB of disk. Never upload private sequences without explicit approval. Follow `$cx-compute-environment`.
3. Pin the AlphaFold repository/container digest, model parameters, database snapshots, model preset, template date, MSA mode, recycle count, relaxation setting, seeds, GPU, and numerical precision. Record versions actually reported by the environment; do not assume a floating tag is immutable.
4. Smoke-test the pinned environment on a tiny known input and validate expected files and nonempty structures before the real run. Run monomer or multimer inference into `artifacts/<run-id>/alphafold2/`. Retain FASTA, MSAs, template hits, ranked structures, PAE, confidence JSON, timings, logs, and failures. Keep a failure record if the process stops or produces invalid output.
5. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
6. Inspect per-residue pLDDT, PAE, pTM/ipTM where available, chain/interface uncertainty, disordered regions, template dependence, and model diversity. Compare an appropriate baseline or independent evidence when required by the claim; do not treat a second model as independent if it shares data or methods.
7. Record inputs, environment, command, outputs, failures, and hashes with `$science-provenance`. Run `$science-review` before presenting material structural conclusions.

## Outputs

Return a concise interpretation plus a machine-readable execution/evidence table with claim ID and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), input and model/database revisions, settings, output paths and hashes, observed metrics, failure/null state, and limitations. Include the intended inference level, uncertainty and applicability, template/database overlap assessment for benchmarks, and the smallest falsifiable next action. Do not equate process completion with scientific validation.

## Boundaries

Prediction confidence is not experimental validation or proof of interaction. Keep apo/holo assumptions explicit. Do not compare runs with different database snapshots as identical. Preserve failed runs and missing metrics rather than silently substituting defaults. Stop if essential entity/stoichiometry information is unresolved, an approval gate is unmet, or the pinned setup cannot represent the input; report an inconclusive or unavailable claim when evidence is insufficient.
