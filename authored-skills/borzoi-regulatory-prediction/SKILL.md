---
name: borzoi-regulatory-prediction
description: "Run pinned Borzoi models to predict RNA-seq and regulatory tracks from long DNA sequence and compare reference versus alternate alleles. Use for regulatory variant hypotheses with explicit genome assembly, sequence-window, tissue, and track provenance."
license: MIT
---

# Borzoi Regulatory Prediction

## Gate

Ask once before cloning/installing a pinned Borzoi revision, downloading model
weights, or using GPU compute. Keep genomic sequence local unless remote use is
approved. Follow `$cx-compute-environment`.

## Workflow

1. Pin genome assembly, coordinates, strand, reference/alternate alleles,
   transcript/annotation release, tissue/track IDs, input length, and boundary
   handling. Verify reference alleles against the assembly.
2. Pin code commit, ensemble/checkpoint checksums, preprocessing, target metadata,
   shifts/reverse-complement ensemble, precision, hardware, and seeds.
3. Smoke-test an official example. Predict into
   `artifacts/<run-id>/borzoi/`; retain input windows, coordinate maps, target
   labels, raw tracks, reference/alternate differences, plots, logs, and failures.
4. Summarize effect direction/magnitude by declared tissues and transcripts;
   report ensemble variability and sensitivity to window placement. Compare
   simple conservation/motif and nearby-QTL baselines where relevant.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- Predicted expression effects are not causal, pathogenic, or clinical evidence.
- Prevent overlapping/LD-correlated windows and the same locus from crossing
  evaluation splits; audit training-data and annotation-release overlap.

