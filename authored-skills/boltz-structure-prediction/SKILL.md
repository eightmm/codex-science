---
name: boltz-structure-prediction
description: "Predict 3D biomolecular structures and binding affinity with the open-source Boltz model — proteins, complexes, nucleic acids, and protein-ligand systems from sequence. Use when the user wants a predicted structure or affinity from sequence (not an experimental structure or a database lookup). Downloads and installs Boltz into an isolated uv environment and runs it."
license: MIT
---

# Boltz Structure Prediction (Codex-native)

Actually run structure prediction: create an isolated environment, install Boltz,
fetch its weights, and predict from sequence — then interpret the confidence.
Boltz is open source (Boltz-1 / Boltz-2). See https://github.com/jwohlwend/boltz.

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Use to predict a 3D structure or binding affinity of a protein, complex, nucleic acid, or protein-ligand system from sequence. Do not use for an experimental structure (`$cx-pdb-search`), precomputed AlphaFold DB model (`$cx-alphafold-structure-analysis`), or structural-homolog search (`$cx-foldseek-structural-search`). Before setup, record the scientific question, normalized entities and chemistry, intended use, claim IDs, model family, and what result could change the conclusion. Treat affinity as exploratory unless independently validated for the stated domain.

## Reference usage

Read [boltz-evidence.md](references/boltz-evidence.md) before interpreting pLDDT, pTM, ipTM, docking scores, or affinity; selecting controls; or assigning claim status. It distinguishes model confidence from experimental validity and defines ligand/complex applicability, evidence dependencies, sensitivity, and failure criteria.

## Workflow

1. **Gates (ask before proceeding).** Confirm once up front before installing `boltz` with pip and downloading several-GB weights on first run, using GPU compute, or transmitting sequence to an MSA service. State hardware and rough time. GPU is best; CPU can be very slow. `--use_msa_server` sends query sequence to the public ColabFold MSA server; never use it for proprietary/sensitive sequences without explicit approval. Supply precomputed MSA instead. Follow `$cx-compute-environment`; record approvals and data-transfer choice.
2. Create an isolated uv environment with `uv venv "<run_dir>/.venv"` and install the selected pinned release with `uv pip install --python "<run_dir>/.venv" "boltz==<VERSION>"`; record Boltz version, weight revision/checksum where available, environment, hardware, and setup output.
3. Prepare and preserve YAML or FASTA input for protein/RNA/DNA sequences, ligands (SMILES/CCD), and optional MSA. Validate entity IDs, stoichiometry, modifications, chain mapping, ligand state, and chemistry; hash the input. Stop on ambiguous mappings or unsupported entity/ligand forms and record the failure.
4. Smoke-test the pinned environment with its help or official small example and validate output before the full run. If valid, run `uv run --python "<run_dir>/.venv" boltz predict "<input>" --out_dir "<run_dir>/artifacts/<run-id>/boltz"`; add `--use_msa_server` only after the required approval, otherwise omit it and pass a precomputed MSA when used. Record command, parameters, timings, outputs, and failures; first run downloads weights and later runs reuse cache.
5. Verify actual output schema and entity/residue mapping. Inspect mmCIF/PDB, pLDDT, pTM, ipTM, predicted affinity for ligand runs, region/interface confidence, and clashes only when those fields are present; record missingness instead of inferring absent metrics.
6. Evaluate structure and affinity claims separately under the reference criteria. Compare with a justified known-structure or redocking benchmark and decoy/negative controls where applicable; affinity requires independent measured validation for the stated domain. Record control identities, shared evidence sources, outcomes, and uncertainty.
7. Vary seed and sampling settings, MSA source/presence, and relevant model/version or input assumptions; record the exact changes and whether structure, interface, or affinity conclusions change. Report `supported`, `contradicted`, `inconclusive`, or `unavailable`; computational confidence alone cannot establish experimental validity.
8. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation/failure logs. Retain outputs, timings, exact Boltz and weights versions, hardware, seeds, and environment.
9. **Verify** artifact hashes, structure parsing, chain/ligand mapping, metrics present, and the separation of process completion from scientific acceptance. Record inputs, command, environment, outputs, and hashes with `$science-provenance`; use `$science-review` before conclusions.

## Outputs

Return `boltz-prediction-evidence-v1` with these required fields: claim identifier (`claim_id`); status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized input and hash (`input`, `input_hash`); entity, chain, ligand, and stoichiometry mapping (`entity_mapping`); Boltz/weights revision (`model_revision`, `weights_revision`); MSA source and approval status (`msa_source`, `msa_approval`); command/settings, seed, and hardware (`command`, `settings`, `seed`, `hardware`); artifact paths/hashes (`artifacts`); confidence or affinity fields actually present plus confident/low-confidence region and interface summaries (`metrics`, `confidence_regions`); failures/nulls (`failures`, `missingness`); controls and results (`controls`); uncertainty (`uncertainty`); applicability limits (`applicability_limits`); process completion (`process_completed`); scientific acceptance status (`acceptance_status`); concise interpretation (`interpretation`); and smallest falsifiable next action (`next_action`).

## Boundaries

Predictions are computational hypotheses, not experimental truth; report confidence and treat low-confidence regions/interfaces skeptically. Report Boltz and weights version and hardware; results can vary across versions and with/without MSA. Do not send proprietary sequences to the public MSA server without approval. An affinity estimate is not measured affinity or proof of binding. For downstream visualization use `$cx-pymol-visualize`; for confidence-style analysis of a predicted model, the AlphaFold pLDDT/PAE guidance also applies.
