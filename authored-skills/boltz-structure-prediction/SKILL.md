---
name: boltz-structure-prediction
description: "Predict 3D biomolecular structures and binding affinity with the open-source Boltz model — proteins, complexes, nucleic acids, and protein-ligand systems from sequence. Use when the user wants a predicted structure or affinity from sequence (not an experimental structure or a database lookup). Downloads and installs Boltz into an isolated uv environment and runs it."
license: MIT
---

# Boltz Structure Prediction (Codex-native)

Actually run structure prediction: create an isolated environment, install Boltz,
fetch its weights, and predict from sequence — then interpret the confidence.
Boltz is open source (Boltz-1 / Boltz-2). See https://github.com/jwohlwend/boltz.

## When to use / not use

- **Use** to predict a 3D structure (or binding affinity) of a protein, complex,
  nucleic acid, or protein-ligand system **from sequence**.
- **Do not use** for an experimental structure (use `$cx-pdb-search`), a
  precomputed AlphaFold DB model (use `$cx-alphafold-structure-analysis`), or
  structural-homolog search (use `$cx-foldseek-structural-search`).

## Gates — ask once, then run to completion

Confirm with the user **once**, up front, then proceed:

- **Install + weights**: installs `boltz` (pip) and downloads model weights
  (several GB) on first run.
- **Compute**: runs best on a **GPU**; CPU works but can be very slow. State the
  hardware and rough time.
- **MSA / network**: `--use_msa_server` sends the query sequence to the public
  ColabFold MSA server. Do **not** use it for proprietary/sensitive sequences
  without explicit approval — supply a precomputed MSA instead.

## Workflow

1. Follow `$cx-compute-environment` to make an isolated uv env and install a
   pinned Boltz:
   ```bash
   uv venv "<run_dir>/.venv"
   uv pip install --python "<run_dir>/.venv" boltz
   ```
2. Prepare the input. Boltz takes a YAML (or FASTA) describing the sequences
   (protein/RNA/DNA) and any ligands (SMILES/CCD), plus optional MSA. Write it
   under the run dir.
3. Predict:
   ```bash
   uv run --python "<run_dir>/.venv" boltz predict "<input>" \
     --out_dir "<run_dir>/artifacts/<run-id>/boltz" --use_msa_server
   ```
   Omit `--use_msa_server` and pass a precomputed MSA for sensitive sequences.
   First run downloads weights; subsequent runs reuse the cache.
4. Read the outputs: predicted structure (mmCIF/PDB) and confidence
   (pLDDT/pTM/ipTM; and predicted affinity for ligand runs). Summarize which
   regions/interfaces are confident vs. low-confidence.
5. Record inputs, exact Boltz version, weights version, command, hardware, seeds,
   and outputs with `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Predictions are computational hypotheses, **not** experimental truth; report
  confidence and treat low-confidence regions/interfaces skeptically.
- Report the Boltz and weights version and the hardware; results can vary across
  versions and with/without MSA.
- Do not send proprietary sequences to the public MSA server without approval.
- For downstream visualization use `$cx-pymol-visualize`; for confidence-style
  analysis of a predicted model, the AlphaFold pLDDT/PAE guidance also applies.
