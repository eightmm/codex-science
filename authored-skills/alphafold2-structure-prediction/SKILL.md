---
name: alphafold2-structure-prediction
description: "Run reproducible AlphaFold2 monomer or multimer inference with pinned code, parameters, sequence databases, template cutoff, and seeds. Use when a local AlphaFold2 installation or approved container/database setup is available; use AlphaFold DB lookup instead for an existing canonical model."
license: MIT
---

# AlphaFold2 Structure Prediction

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

Before a run, record the intended structural question and claim IDs; exact sequences and constructs; organism, chain stoichiometry, oligomeric state, modifications, and ligand state; template cutoff; and intended use. State whether the result is exploratory or decision-bearing, what structural observation would change the conclusion, and what input or model limitation would make the result inconclusive. Use `$cx-alphafold-structure-analysis` when AlphaFold DB already contains the desired canonical monomer.

## Reference usage

- Read [references/alphafold2-evidence.md](references/alphafold2-evidence.md) before assigning a structural claim, interpreting confidence, selecting controls, comparing samples, setting a benchmark cutoff, or assessing MSA/template/PDB overlap and database sensitivity.

## Workflow

1. **Gates (ask before proceeding).** Prefer an existing validated installation. Before installing or pulling a pinned container, downloading model parameters or sequence databases, querying remote MSA services, or using GPU compute, ask once and state that a full official setup can require hundreds of GB of downloads and several TB of disk. Never upload private sequences without explicit approval. Follow `$cx-compute-environment`; record approval, destination, and any declined or unavailable resource. Use AlphaFold DB lookup via `$cx-alphafold-structure-analysis` for an existing canonical model.
2. Normalize exact sequences, constructs, chain IDs, stoichiometry, modifications, oligomeric state, and apo/holo or ligand assumptions; record the intended use, claim IDs, falsifier, input hash, and any unresolved representation issue. Stop as inconclusive when essential entity or stoichiometry is unresolved.
3. Pin the AlphaFold repository or container digest, parameter version/checksum, sequence database snapshots, model preset, template date, MSA mode, recycle count, relaxation setting, seeds, GPU, and numerical precision; record actual environment-reported versions, never assume a floating tag is immutable, and mark unknown training-data cutoffs unknown.
4. Inspect available MSA depth, paired-chain coverage, template hits, and likely PDB or training-set overlap; decide whether those inputs permit the claim and record their provenance, shared dependencies, and limitations.
5. Smoke-test the pinned environment on a tiny known input; proceed only if expected files and a nonempty valid structure are present. Run monomer or multimer inference into `artifacts/<run-id>/alphafold2/`; retain FASTA, MSAs, template hits, ranked structures, PAE, confidence JSON, timings, logs, and failures.
6. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Record each failed, null, or unavailable output without substituting a default.
7. Evaluate pLDDT, PAE, pTM/ipTM where available, ranking confidence, interface/domain consistency, disorder, template/MSA dependence, and seed/sample diversity under the criteria in the reference; report uncertainty and claim status with metric-specific limits.
8. Compare against a suitable positive control and a negative or sanity control, and compare an appropriate baseline or independent evidence when the claim requires it; document shared data or methods rather than treating a second model as independent. For benchmark claims prefer targets released after the documented training cutoff and assess homolog/template overlap. Vary MSA source/depth, template use/date, recycle count, and seeds; label a conclusion fragile when plausible settings change the claim or relevant structure beyond the prespecified criterion.
9. Record inputs, environment, command, outputs, failures, and hashes with `$science-provenance`; run `$science-review` before presenting material structural conclusions. Report the smallest falsifiable next action and keep prediction separate from experimental evidence.

## Outputs

Return a concise interpretation plus a machine-readable `alphafold2-structure-evidence-v1` record with these required fields: claim identifier (`claim_id`); evidence status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized sequences, constructs, and other inputs (`input`); input hash (`input_hash`); entity and chain mapping (`entity_mapping`); AF2 code or container revision (`code_version`); parameter/model revision and checksum (`parameter_version`, `parameter_checksum`); database snapshots (`database_versions`); execution command (`command`); inference configuration (`settings`); output artifact paths and hashes (`output_paths`, `output_hashes`); emitted metrics and their domain-specific interpretation (`metrics`, `metric_interpretations`); MSA, template, PDB, and training-overlap assessment (`msa_template_overlap`); shared data and method dependencies (`dependencies`); controls and their outcomes (`controls`); varied settings, results, and fragility (`sensitivity`); uncertainty (`uncertainty`); execution and validation failures (`failures`); missing and null fields (`missingness`); applicability domain (`applicability`); limitations (`limitations`); intended inference level (`inference_level`); concise interpretation (`interpretation`); and smallest falsifiable next action (`next_action`). Do not equate process completion with scientific validation.

## Boundaries

Prediction confidence is not experimental validation or proof of interaction. Keep apo/holo assumptions explicit. Do not compare runs with different database snapshots as identical. Preserve failed runs and missing metrics rather than silently substituting defaults. Stop if essential entity/stoichiometry information is unresolved, an approval gate is unmet, or the pinned setup cannot represent the input; report an inconclusive or unavailable claim when evidence is insufficient. Treat AF2 code, parameter, database, and downstream asset terms separately; the repository skill's MIT license does not grant rights to model weights or databases. GPU, disk, installation, remote-service, and private-sequence gates remain in force.
