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

## Workflow

1. Confirm once up front before installing `boltz` (pip) and downloading model weights (several GB) on first run, using GPU compute, or transmitting sequence to an MSA service. State hardware and rough time. GPU is best; CPU works but can be very slow. `--use_msa_server` sends query sequence to the public ColabFold MSA server; do not use it for proprietary/sensitive sequences without explicit approval. Supply a precomputed MSA instead. Follow `$cx-compute-environment`.
2. Create an isolated uv environment and install a pinned Boltz version:
   ```bash
   uv venv "<run_dir>/.venv"
   uv pip install --python "<run_dir>/.venv" boltz
   ```
3. Prepare and preserve a YAML (or FASTA) input describing protein/RNA/DNA sequences, ligands (SMILES/CCD), and optional MSA. Record entity IDs, stoichiometry, modifications, chain mapping, and ligand state; hash the input.
4. Smoke-test the pinned environment with its help/official small example and validate output before the full run. Predict with `uv run --python "<run_dir>/.venv" boltz predict "<input>" --out_dir "<run_dir>/artifacts/<run-id>/boltz" --use_msa_server`; omit `--use_msa_server` and pass precomputed MSA for sensitive sequences. First run downloads weights; subsequent runs reuse the cache. Retain command, outputs, timings, logs, and failures.
5. Validate actual output schema. Inspect predicted structure (mmCIF/PDB), pLDDT/pTM/ipTM, predicted affinity for ligand runs, region/interface confidence, clashes, and sample variability. Record exact Boltz and weights versions, hardware, seeds, and environment. Compare a justified baseline for material claims.
6. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
7. Record inputs, command, environment, outputs, and hashes with `$science-provenance`; use `$science-review` before conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized input and hash, Boltz/weights revision, MSA source, command/settings, hardware, artifact paths/hashes, measured confidence or affinity fields actually present, failures/nulls, uncertainty, and limitations. Summarize confident and low-confidence regions/interfaces and give the smallest falsifiable next action. Process success is not scientific validation.

## Boundaries

Predictions are computational hypotheses, not experimental truth; report confidence and treat low-confidence regions/interfaces skeptically. Report Boltz and weights version and hardware; results can vary across versions and with/without MSA. Do not send proprietary sequences to the public MSA server without approval. An affinity estimate is not measured affinity or proof of binding. For downstream visualization use `$cx-pymol-visualize`; for confidence-style analysis of a predicted model, the AlphaFold pLDDT/PAE guidance also applies.
