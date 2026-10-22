---
name: alphafold3-structure-prediction
description: "Run the official AlphaFold3 inference pipeline for approved theoretical modeling of proteins, nucleic acids, ligands, modifications, and covalent complexes. Use only when the user has legitimately obtained model parameters and accepts the source, weight, output, and non-commercial terms."
license: MIT
---

# AlphaFold3 Structure Prediction

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

For a concrete approved input, follow `$cx-modeling-problem-execution` through execution and review. State the structural question, intended use, entity and chemical state, claim IDs, permitted inference, and the observation that would change the conclusion. Record whether the result is exploratory; do not frame a predicted complex as binding evidence.

## Reference usage

- Read [references/alphafold3-evidence.md](references/alphafold3-evidence.md) before assigning claims, interpreting confidence/ranking or chemistry, selecting controls, using MSA/template inputs, assessing PDB/training overlap, or judging sensitivity across seeds and inference settings.

## Workflow

1. **Gates (ask before proceeding).** Verify intended use and that parameters came directly from Google. AlphaFold3 code, model parameters, and outputs have separate restrictive terms. Before inspecting credentialed parameter paths, pulling a pinned container, downloading databases, or using GPU compute, ask once. Never copy, redistribute, or log weights or credentials; never use for clinical purposes. Record the applicable terms and approval state without exposing restricted assets.
2. Validate the AlphaFold3 JSON dialect/version, entity IDs, sequences, ligand CCD/SMILES, modifications, bonds, custom CCD, MSAs/templates, and model seeds. Preserve the exact input and hash; stop rather than silently dropping unsupported entities or chemistry, and record the unresolved representation.
3. Pin code release/container digest, database snapshots, parameter provenance, template cutoff, pipeline/inference flags, seeds, hardware, and precision. Record actual versions and the training-data cutoff only when verified from an authoritative version-specific source; otherwise mark it unknown.
4. Assess MSA depth and pairing, template dependence, ligand/chemical-state support, and possible PDB or training-set overlap; record source versions and shared dependencies and narrow claims when independence or applicability is limited.
5. Smoke-test the official example and validate the installed release's expected output structure. Run the real JSON into `artifacts/<run-id>/alphafold3/`; retain input hashes and compliant metadata, outputs, confidence, logs, timings, and failures. Exclude restricted weights and credentials from artifacts.
6. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Record null, missing, and unavailable outputs distinctly.
7. Inspect per-atom and per-residue pLDDT (atom-level for ligands), PAE, pTM/ipTM, ranking score, interfaces, ligand state, covalent geometry, clashes, template/MSA dependence, and sample diversity under the reference criteria; report what each metric can support and the remaining uncertainty.
8. Compare a positive structural control and a negative/sanity control, and compare an open model when the claim requires independent evidence; document shared data or methods. For benchmark claims use targets released after the documented training cutoff and audit homolog/template overlap. Vary MSA source/depth, template use/cutoff, recycles, and seeds; classify the result as fragile if plausible settings change the claim or structure beyond the prespecified criterion.
9. Record compliant provenance with `$science-provenance`; run `$science-review` before material conclusions. Report claim status, applicability, restrictions, and the smallest falsifiable next action; distinguish model output from experimental structure and binding evidence.

## Outputs

Return a summary and machine-readable `alphafold3-structure-evidence-v1` record with these required fields: claim identifier (`claim_id`); evidence status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized entities and chemical inputs (`input`); input hash (`input_hash`); entity and atom mapping (`entity_mapping`); official code release or container revision (`code_version`); disclosed model-parameter provenance (`parameter_provenance`); database snapshots (`database_versions`); execution command (`command`); pipeline and inference configuration (`settings`); hardware and precision (`hardware`); output artifact paths and hashes (`output_paths`, `output_hashes`); emitted metrics and their domain-specific interpretation (`metrics`, `metric_interpretations`); MSA, template, PDB, and training-overlap assessment (`msa_template_overlap`); shared data and method dependencies (`dependencies`); controls and their outcomes (`controls`); varied settings, results, and fragility (`sensitivity`); uncertainty (`uncertainty`); execution and validation failures (`failures`); missing and null fields (`missingness`); restricted assets omitted from the record (`restricted_asset_omissions`); applicability domain (`applicability`); limitations (`limitations`); permitted inference level (`permitted_inference`); concise interpretation (`interpretation`); and smallest falsifiable next action (`next_action`). State explicitly when a restricted asset cannot be recorded. Distinguish process completion from scientific validation.

## Boundaries

The repository skill license does not grant rights to AlphaFold3 assets. Predictions are theoretical models, not binding, efficacy, safety, or clinical evidence. Confidence does not establish chemical correctness. Stop if terms, parameter provenance, approval, or input representation is unresolved; do not imply validation from successful execution alone. Never copy or redistribute weights or credentials. Preserve separate source-code, weight, and output terms, and retain GPU, installation, database, and compute approval gates.
