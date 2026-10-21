---
name: rfdiffusion-protein-design
description: "Run pinned RFdiffusion for unconditional generation, motif scaffolding, binder backbones, symmetric assemblies, partial diffusion, or macrocyclic peptide design. Use when structural conditioning and a downstream sequence/refolding validation funnel are defined."
license: MIT
---

# RFdiffusion Protein Design

Use `$cx-modeling-problem-execution` for a concrete target or motif and continue
through the complete candidate funnel.

## Decision contract

Record the design objective, target or motif source and identifiers, structure
chains and residue numbering, conditioning constraints, topology, candidate
budget, and compute envelope before generation. Define acceptance and failure
criteria for geometry, motif recovery, diversity, and downstream refolding. State
which properties remain hypotheses for experimental evaluation.

## Workflow

1. Ask once before cloning a pinned commit/container, downloading checkpoints,
   and running GPU compute. State candidate count, expected time/storage, and any
   downstream ProteinMPNN/refolding compute.
2. Define design task, target/motif provenance, hotspots, contig map and indexing,
   fixed residues/chains, length/topology/symmetry, potentials, diffusion steps,
   seeds, and candidate budget. Pin checkpoint and config.
3. Smoke-test the matching official example and a tiny pilot. Run backbones into
   `artifacts/<run-id>/rfdiffusion/`; preserve PDB/TRB trajectories, mappings,
   configs, logs, rejects, and all candidate IDs.
4. Chain to `$cx-proteinmpnn-sequence-design`, independent refolding/complex
   prediction, geometry/interface filters, diversity/novelty checks, and
   developability screens. Report the full funnel and orthogonal-model agreement.
5. Record with `$science-provenance`; review with `$science-review` before ranking.

## Outputs

Save a manifest containing normalized target/motif inputs, coordinate and residue
maps, pinned code/checkpoint/config/environment, seeds, resource use, all candidate
IDs, stage-level counts and exclusions, output paths/hashes, and failure records.
Return per-candidate evidence, diversity and uncertainty, limitations, and the
smallest falsifiable next validation. Record artifacts with `$science-provenance`;
`$science-review` is mandatory before ranking. Keep process success separate from
scientific acceptance and preserve every rejected candidate with its reason.
Assign each material claim an ID and status: supported, contradicted, inconclusive,
or unavailable.

## Boundaries

- A generated backbone or computational pass does not establish folding,
  function, binding, specificity, safety, or experimental success.
- Never score only survivors; report generation and filter failure rates.

