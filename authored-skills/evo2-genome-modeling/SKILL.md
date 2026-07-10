---
name: evo2-genome-modeling
description: "Run pinned Evo 2 DNA sequence scoring, embeddings, variant scoring, or controlled generation. Use for long-context genomic foundation-model analyses when compatible local GPU hardware and explicit genome/strand provenance are available."
license: MIT
---

# Evo 2 Genome Modeling

## Gate

Ask once before installing pinned Evo 2/Vortex dependencies, downloading large
checkpoints, using GPU/remote compute, or sending sequence to a hosted API.
State hardware compatibility and estimated memory/time. Follow
`$cx-compute-environment`.

## Workflow

1. Record assembly, chromosome/contig, coordinates, strand, reference allele,
   sequence window, organism, and intended task. Validate reference alleles and
   keep reverse complements/overlapping loci together in evaluation splits.
2. Pin Evo 2 version/commit, checkpoint and checksum, tokenizer, context length,
   embedding layer or scoring rule, precision, hardware, seeds, and generation
   parameters/budget.
3. Run the official installation smoke test, then execute into
   `artifacts/<run-id>/evo2/`; retain exact sequences, coordinate maps, logits or
   embeddings, generations, configs, environment, logs, and failures.
4. For variants, compare matched reference/alternate windows and both strand
   conventions when appropriate. For generation, report memorization, novelty,
   composition, constraints, filter failures, and nearest database neighbors.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Likelihood is not pathogenicity, fitness, expression, or clinical evidence.
- Generated DNA is a computational hypothesis; do not automatically synthesize,
  deploy, or optimize for harmful biological function.

