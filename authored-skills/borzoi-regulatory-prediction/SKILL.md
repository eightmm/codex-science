---
name: borzoi-regulatory-prediction
description: "Run pinned Borzoi models to predict RNA-seq and regulatory tracks from long DNA sequence and compare reference versus alternate alleles. Use for regulatory variant hypotheses with explicit genome assembly, sequence-window, tissue, and track provenance."
license: MIT
---

# Borzoi Regulatory Prediction

## Decision contract

Record assembly and coordinate convention, reference/alternate alleles and
validation, input windows, transcript/annotation release, track and tissue IDs,
question, evaluation split and permitted inference. Freeze the window, aggregation
and acceptance criterion before prediction. Borzoi scores are predicted assay
tracks; keep them separate from measured expression, causal or clinical claims.

## Reference usage

Read [prediction-protocol.md](references/prediction-protocol.md) before selecting
tracks, constructing reference/alternate inputs, aggregating windows or
interpreting a predicted score. Read [evaluation-and-controls.md](references/evaluation-and-controls.md)
before benchmarking, choosing controls, making held-out claims or extrapolating
to unseen cell types or distal elements.

## Workflow

1. **Gates (ask before proceeding).** Ask once before cloning or installing a
   pinned Borzoi revision, downloading model weights or using GPU compute. Keep
   genomic sequence local unless remote use is approved; follow
   `$cx-compute-environment`. Record the user's decision and what was authorized.
2. Normalize assembly, coordinates, strand, reference/alternate alleles and
   annotation release; verify the reference allele and coordinate map or stop.
   Borzoi was trained on hg38 and mm10; do not treat hg19 as a supported input
   build. For hg19 input, require a recorded, checked liftover to hg38 or mm10.
   Record all inputs and validation results.
3. Freeze model commit, ensemble/checkpoint checksums, preprocessing, target
   metadata, shifts/reverse-complement ensemble, precision, hardware, seeds,
   windows, evaluation split and claim threshold; compare conservation/motif and
   nearby-QTL baselines where relevant; record the configuration.
4. Smoke-test an official example and inspect output shapes and target labels;
   proceed only if the installed pinned model returns the expected contract.
   Record the example identity and check result.
5. Predict matched reference and alternate sequences into
   `artifacts/<run-id>/borzoi/`; retain windows, coordinate maps, raw tracks,
   target labels, differences, plots, logs and failed windows.
6. Summarize signed effects for prespecified track/tissue/transcript and window
   aggregations; compare suitable controls and baselines. Record denominators,
   controls and exclusions; predicted values remain distinct from assay outcomes.
7. Vary track choice, window placement/width, aggregation and model version
   where available. Record whether signs, rankings or claim class change; call
   the result fragile when they do materially.
8. **Verify** assembly/allele identity, pinned checksums, input/output alignment,
   target labels, completeness and artifact hashes; record each check and any
   failures or unavailable outputs.
9. Write the versioned result, preserve it with `$science-provenance`, review
   material claims with `$science-review`, and record disposition and the
   smallest falsifiable follow-up.

## Outputs

Write one `borzoi-regulatory-evidence-v1` record with these required fields:

- Claim identifier (`claim_id`) and status (`claim_status`: `supported`,
  `contradicted`, `inconclusive` or `unavailable`).
- Variant (`variant`), assembly (`assembly`), coordinate convention
  (`coordinate_convention`), reference check (`reference_check`) and
  annotation release (`annotation_release`).
- Model commit (`model_commit`), ensemble/checkpoint checksums
  (`ensemble_and_checkpoint_checksums`), checkpoint replicate used
  (`checkpoint_replicate`), preprocessing (`preprocessing`), track IDs
  (`track_ids`) and tissue/cell type (`tissue_or_cell_type`).
- Window/mask (`window_and_mask`), aggregation (`aggregation`), reference and
  alternate tracks (`reference_and_alternate_tracks`), predicted effects
  (`predicted_effects`) and evaluation split (`evaluation_split`).
- Controls (`controls`), sensitivity results (`sensitivity`), uncertainty and
  limits (`uncertainty_and_limits`), hardware/precision/seed
  (`hardware_precision_seed`) and failures/exclusions (`failures_and_exclusions`).
- Artifact paths/hashes (`artifacts`), provenance (`provenance`), review
  disposition (`review`) and smallest falsifiable next test (`next_test`).

Retain failed windows and separate prediction completion from acceptance.

## Boundaries

- Predicted expression effects are not causal, pathogenic, clinical or measured
  evidence. A model track is not an assay result.
- Prevent overlapping or LD-correlated windows and the same locus from crossing
  evaluation splits; audit training-data and annotation-release overlap.
- Preserve exact target IDs, coordinate maps, track differences, ensemble/window
  sensitivity and all failures. Do not turn an absent track into a null result.
- Do not remote-upload genomic sequence without the required approval or bypass
  install, model-weight or compute gates.
