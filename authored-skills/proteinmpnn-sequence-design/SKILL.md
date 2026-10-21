---
name: proteinmpnn-sequence-design
description: "Design or score protein sequences for fixed backbones with ProteinMPNN, LigandMPNN, or SolubleMPNN. Use for backbone-conditioned design, ligand-context design, soluble-protein design, residue constraints, or side-chain packing."
license: MIT
---

# ProteinMPNN Sequence Design

## Decision contract

Record the backbone source/hash, biological objective, chain and residue mapping,
fixed/designable positions, ligand context, sequence constraints, and evaluation
split before scoring or design. Prespecify candidate budget and acceptance checks
for sequence validity, structural compatibility, diversity, and applicable
downstream tests. State the intended applicability domain and falsifiers.

## Gate

Ask once before cloning a pinned repository commit, downloading model weights,
or using GPU compute. Follow `$cx-compute-environment`; do not automatically
submit generated sequences for synthesis or remote screening.

## Workflow

1. Audit backbone source, assembly, chains, missing residues, ligand/cofactor
   atoms, fixed/designable positions, symmetry/tied residues, and target context.
2. Select ProteinMPNN, LigandMPNN, or SolubleMPNN for the declared objective.
   Pin commit, checkpoint checksum, noise level, temperature, seed, batch size,
   residue constraints, biases, and ligand/side-chain context flags.
3. Smoke-test an upstream example, then generate and score into
   `artifacts/<run-id>/proteinmpnn/`. Preserve structures, configs, FASTA/PDB,
   per-position probabilities, scores, atom/residue maps, and all candidates.
4. Report recovery only as a diagnostic. Evaluate diversity, novelty to training
   and known sequences, structural consistency, clashes, ligand-context
   dependence, and developability proxies with orthogonal methods.
5. Record the candidate funnel with `$science-provenance`; review with
   `$science-review` before selecting candidates.

## Outputs

Save a run manifest with normalized backbone/constraint identifiers and hashes,
model/checkpoint/config/environment, seeds, resource use, all candidate IDs,
per-stage counts, scores and exclusions, and output paths/hashes. Return the full
candidate table, uncertainty and baseline comparisons, limitations, and the
smallest falsifiable next test. Record artifacts with `$science-provenance`;
`$science-review` is mandatory before candidate selection. Preserve failed
candidates and separate process completion from scientific acceptance. Assign each
material claim an ID and status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- Model likelihood, recovery, or confidence is not function, binding, solubility,
  safety, or experimental validation.
- Prevent template/parent leakage and report similarity to the input sequence.

