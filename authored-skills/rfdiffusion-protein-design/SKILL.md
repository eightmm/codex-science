---
name: rfdiffusion-protein-design
description: "Run pinned RFdiffusion for unconditional generation, motif scaffolding, binder backbones, symmetric assemblies, partial diffusion, or macrocyclic peptide design. Use when structural conditioning and a downstream sequence/refolding validation funnel are defined."
license: MIT
---

# RFdiffusion Protein Design

Use `$cx-modeling-problem-execution` for a concrete target or motif and continue
through the complete candidate funnel.

## Gate and workflow

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

## Boundaries

- A generated backbone or computational pass does not establish folding,
  function, binding, specificity, safety, or experimental success.
- Never score only survivors; report generation and filter failure rates.

