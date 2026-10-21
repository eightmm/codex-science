---
name: protenix-structure-prediction
description: "Run pinned Protenix structure prediction for protein, nucleic-acid, ligand, antibody-antigen, template, MSA, or constrained complexes. Use Protenix-v2 or another explicitly selected released model with a recorded training-data cutoff and inference budget."
license: MIT
---

# Protenix Structure Prediction

Use `$cx-modeling-problem-execution` for concrete inputs and continue through
execution, comparison, and review.

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

State the structural question, intended use, claim IDs, entity/chemistry state, model choice and permitted inference. Record what result would change the interpretation and what makes it inconclusive. Pin the selected released model explicitly; do not treat model family performance as validation on the target.

## Workflow

1. Ask once before installing a pinned Protenix release, downloading weights or databases, using public MSA services, and running GPU/remote compute.
2. Validate JSON entities, ligand states, templates, constraints, MSAs, and RNA features. Preserve input and hashes. Pin model name/checksum, code version, training-data cutoff, samples/seeds, inference-time scaling budget, kernels, device, and precision; record actual revisions.
3. Smoke-test the official example and verify expected outputs before the full run. Run `protenix pred` into `artifacts/<run-id>/protenix/`; retain inputs, features, models/configs, structures, confidence, logs, timings, and every candidate/failure.
4. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs.
5. Report performance only as specific to the selected model/cutoff. Inspect sample diversity, interface/ligand plausibility, clashes, constraints, MSA/template dependence, and uncertainty. Compare another justified predictor for strong claims, noting shared data and method dependencies.
6. Record with `$science-provenance`; run `$science-review` before material conclusions.

## Outputs

Return an execution/evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), normalized input/hash, model/code/weight/database revisions and cutoff, inference budget/settings, hardware, output paths/hashes, metrics actually emitted, candidate failures, uncertainty, and limitations. Include an interpretation, rejected alternatives, and smallest falsifiable next action. Separate successful process completion from scientific acceptance.

## Boundaries

More inference samples increase selection opportunity and compute; report the full budget and avoid comparing against a lower-budget baseline unfairly. Structure confidence is not experimental interaction or affinity evidence. Do not infer calibration, generalization, or clinical utility from model confidence. Stop for unresolved entity/constraint mapping, unsupported input chemistry, or unmet approval; preserve failures and mark affected claims inconclusive or unavailable.
