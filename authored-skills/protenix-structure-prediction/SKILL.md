---
name: protenix-structure-prediction
description: "Run pinned Protenix structure prediction for protein, nucleic-acid, ligand, antibody-antigen, template, MSA, or constrained complexes. Use Protenix-v2 or another explicitly selected released model with a recorded training-data cutoff and inference budget."
license: MIT
---

# Protenix Structure Prediction

Use `$cx-modeling-problem-execution` for concrete inputs and continue through
execution, comparison, and review.

## Gate and workflow

1. Ask once before installing a pinned Protenix release, downloading weights or
   databases, using public MSA services, and running GPU/remote compute.
2. Validate the JSON entities, ligand states, templates, constraints, MSAs, and
   RNA features. Pin model name/checksum, code version, training-data cutoff,
   samples/seeds, inference-time scaling budget, kernels, device, and precision.
3. Smoke-test the official example. Run `protenix pred` into
   `artifacts/<run-id>/protenix/`; retain inputs, features, models/configs,
   structures, confidence, logs, timings, and every candidate/failure.
4. Report performance as specific to the selected model/cutoff. Inspect sample
   diversity, interface/ligand plausibility, clashes, constraints, MSA/template
   dependence, and uncertainty; compare another predictor for strong claims.
5. Record with `$science-provenance`; review with `$science-review`.

## Boundaries

- More inference samples increase selection opportunity and compute; report the
  full budget and avoid comparing against a lower-budget baseline unfairly.
- Structure confidence is not experimental interaction or affinity evidence.

