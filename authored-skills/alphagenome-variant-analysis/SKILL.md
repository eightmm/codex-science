---
name: alphagenome-variant-analysis
description: "Analyze how a single non-coding genetic variant affects gene expression, chromatin accessibility, histone marks, transcription factors, and splicing using the AlphaGenome API. Use when the user gives a variant in chr:pos:ref/alt form and asks about regulatory or splicing effects, tissue-specific impact, or pathogenicity of a non-coding change. Requires an AlphaGenome API key."
license: Apache-2.0
---

# AlphaGenome Single-Variant Analysis (Codex-native)

Codex-native adaptation of Google DeepMind's `alphagenome-single-variant-analysis`
skill. It maps the upstream workflow onto Codex tools instead of a bundled
script harness. Attribution: adapted from
[google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
(Apache-2.0 + CC-BY-4.0). Model terms: https://deepmind.google.com/science/alphagenome/

## Decision contract

Normalize one variant as `chr:pos:ref/alt` (or `ref>alt`); record assembly,
reference-allele validation, evidence cutoff, tissue/cell type, modality, track,
model release and the permitted interpretation. State the selected spatial mask,
aggregation, scale and direction before ranking. A model score supports a
prediction about a measured modality; it is not measured expression, chromatin,
splicing, a calibrated probability, clinical classification or proof of function.

## Reference usage

Read [variant-scoring-method.md](references/variant-scoring-method.md) before
choosing scorers, interpreting returned columns, aggregating tracks/windows or
making a variant-effect claim. Read [evaluation-and-controls.md](references/evaluation-and-controls.md)
before evaluating a score against variants, choosing controls or generalizing
across loci, tissues or modalities.

## Workflow

1. **Gates (ask before proceeding).** Confirm `ALPHAGENOME_API_KEY` is already
   exported; never read, print or hardcode it. On first workspace use, tell the
   user to review the AlphaGenome terms and record the notice in provenance. Ask
   before installing `alphagenome`, `pandas` or `numpy`; run Python only through
   `uv run`, never bare `python3` or system `pip`. If the key is absent, stop and
   ask the user to register at the model terms URL above.
2. Parse the variant and reject malformed coordinates, unsupported alleles or
   reference mismatch; record the normalized allele, assembly and validation.
3. Freeze tissue/cell type, modality/output type, track selection, scorer,
   window/mask, aggregation, model release and allowed claim; record each choice
   and its rationale before querying.
4. Run the API with matched reference and alternate sequence predictions; retain
   endpoint, request settings, returned outputs and failures. Treat requested
   modalities without returned records as unavailable, not negative.
5. Check returned schema and score direction against the reference method; rank
   only the declared track subset and threshold, preserving all candidates,
   exclusions and reasons in the score table.
6. Compare observed predicted differences with positive and negative controls;
   if held-out or matched controls are unavailable, label the result exploratory
   and record the gap.
7. Vary track/cell type, window, aggregation and reported model version where
   available; call the effect fragile when sign, rank or claim class changes
   materially and record the comparison.
8. **Verify** the normalized input, assembly, reference allele, selected
   reference/alternate outputs, score table and artifact hashes; record check
   results and unresolved failures.
9. Write `report.md` with the normalized variant, top-hits table, per-tissue
   interpretation, caveats and notice that AlphaGenome was used; preserve the
   plot and JSON score table in the output folder. Record the versioned output,
   inputs, endpoint and artifacts with `$science-provenance`, then use
   `$science-review` before presenting material variant interpretation; record
   review disposition and smallest falsifiable follow-up.

## Outputs

Write one `alphagenome-variant-evidence-v1` record with these required fields:

- Claim identifier (`claim_id`) and status (`claim_status`: `supported`,
  `contradicted`, `inconclusive` or `unavailable`).
- Normalized variant (`variant`), genome assembly (`assembly`), reference check
  (`reference_check`) and evidence cutoff (`evidence_cutoff`).
- Model release (`model_release`), API endpoint (`endpoint`), tissue/cell type
  (`tissue_or_cell_type`), output modality (`modality`) and track identifiers
  (`track_ids`).
- Scorer (`scorer`), spatial window and mask (`window_and_mask`), aggregation
  (`aggregation`), reference/alternate scores (`reference_and_alternate_scores`)
  and direction (`score_direction`).
- Returned/excluded records and reasons (`returned_and_excluded_records`),
  controls (`controls`), sensitivity results (`sensitivity`) and uncertainty/
  limitations (`uncertainty_and_limits`).
- Artifact paths/hashes (`artifacts`), provenance record (`provenance`), review
  disposition (`review`) and smallest falsifiable next test (`next_test`).

Include the output folder, plot, JSON score table and `report.md` paths in
`artifacts`; `report.md` contains the top-hits table and per-tissue interpretation.
Preserve negative results and failed or unavailable queries.

## Boundaries

- Predictions are computational hypotheses, not clinical or diagnostic
  conclusions. Do not assert pathogenicity, disease causation or treatment
  implications from these scores alone.
- A quantile hit is relative to its reference distribution, not a calibrated
  probability. Near-boundary or single-tissue hits are weak evidence; report
  negative results honestly.
- Do not substitute external gene/annotation APIs for the model's own outputs
  when reproducing the upstream method.
- Preserve failures, uncertainty and known limitations, including weak
  performance on some ncRNA structures. A predicted track effect does not
  establish measured molecular change or biological function.
