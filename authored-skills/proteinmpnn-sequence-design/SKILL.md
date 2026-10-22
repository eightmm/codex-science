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
Sequence recovery is a structural-design diagnostic, not evidence of function,
binding, expression, or experimental success.

## Gate

Ask once before cloning a pinned repository commit, downloading model weights, or
using GPU compute. Follow `$cx-compute-environment`; do not automatically submit
generated sequences for synthesis or remote screening. Review the code, model
weight, and service terms separately; the MIT repository license does not override
other assets' terms.

## Reference usage

Read [references/proteinmpnn-evidence.md](references/proteinmpnn-evidence.md)
before selecting a model/noise/temperature, interpreting recovery or likelihood,
comparing candidates, or claiming compatibility. It defines claim classes,
dependence, controls, uncertainty, sensitivity, and applicability.

## Workflow

1. **Gate (ask before proceeding).** Before cloning the pinned commit, downloading
   model weights, or using GPU compute, state the model, objective, candidate
   budget, and resource estimate; record approval or stop without executing the
   gated action. Follow `$cx-compute-environment` and preserve tool/weight terms.
2. Audit backbone source and hash, assembly, chains, missing residues,
   ligand/cofactor atoms, fixed/designable positions, symmetry/tied residues, and
   target context; continue only if sequence-to-structure mapping is unambiguous,
   and record mappings and unresolved caveats.
3. Select ProteinMPNN, LigandMPNN, or SolubleMPNN for the declared objective;
   pin commit, checkpoint checksum, noise level, temperature, seed, batch size,
   residue constraints, biases, and ligand/side-chain context flags; record the
   frozen configuration before generating sequences.
4. Smoke-test an upstream example; continue only if sequence and residue outputs
   pass integrity checks, and record command, environment, and failures.
5. Generate and score into `artifacts/<run-id>/proteinmpnn/`; preserve structures,
   configs, FASTA/PDB, per-position probabilities, scores, atom/residue maps, and
   every candidate; stop at budget and record all attempted sequences.
6. Report recovery only as a diagnostic against an explicitly named native or
   parent sequence; continue to comparison only with identical designable-position
   masks, and record both numerator and denominator plus masked residues.
7. Evaluate diversity, novelty to training and known sequences, structural
   consistency, clashes, ligand-context dependence, and developability proxies
   with orthogonal methods; report full generation/filter denominators and compare
   with native/known, scrambled/random, and unconditioned controls where valid.
8. Vary seeds, temperature, noise level, residue constraints, and filter
   thresholds; treat rank, retained set, or conclusion changes as sensitivity,
   and record the perturbation plan and all resulting funnels.
9. Verify mappings, hashes, denominators, evidence statuses, and artifact links;
   preserve results with `$science-provenance`, then use `$science-review` before
   candidate selection, and record the review receipt and unresolved findings.

## Outputs

Produce one `proteinmpnn-sequence-evidence-v1` record containing: run identifier
(`run_id`); backbone, mapping, and ligand context with hashes (`backbone`);
pinned model/checkpoint/dependency identities and terms (`software`); frozen
settings, constraints, and resource envelope (`configuration`); seeds (`seeds`);
all sequence identifiers and stage denominators (`funnel`); execution environment
and observed resource use (`environment` and `resource_use`); full candidate table
with sequences, recovery mask/numerator/denominator, scores, and structural
metrics (`candidate_table`); uncertainty and baseline comparisons (`uncertainty`
and `baseline_comparisons`); control and sensitivity results (`controls` and
`sensitivity`); claim identifiers, classes, statuses, and limitations (`claims`);
smallest falsifiable next test (`next_step`); artifact paths/hashes (`artifacts`);
provenance and review receipts (`handoffs`). Assign each material claim an ID and
status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- Model likelihood, recovery, or confidence is not function, binding, solubility,
  safety, or experimental validation.
- Prevent template/parent leakage and report similarity to the input sequence.
- Do not treat candidate filtering as independent confirmation; preserve rejected
  candidates and selection denominators.
- Preserve failed candidates and separate process completion from scientific
  acceptance.
- Do not automatically submit sequences for synthesis or remote screening.
