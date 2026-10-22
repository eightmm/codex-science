---
name: protenix-structure-prediction
description: "Run pinned Protenix structure prediction for protein, nucleic-acid, ligand, antibody-antigen, template, MSA, or constrained complexes. Use Protenix-v2 or another explicitly selected released model with a recorded training-data cutoff and inference budget."
license: MIT
---

# Protenix Structure Prediction

Use `$cx-modeling-problem-execution` for concrete inputs and continue through execution, comparison, and review.

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

State the structural question, intended use, claim IDs, entity/chemistry state, selected model and permitted inference. Record what result would change the interpretation and what makes it inconclusive. Pin the selected released model explicitly; do not treat model-family performance as validation on the target.

## Reference usage

- Read [references/protenix-complex-evidence.md](references/protenix-complex-evidence.md) before interpreting complex confidence, chain-pair metrics, ligand poses, MSA/template inputs, training overlap, or controls.
- Record the exact reference revision and use with `$science-provenance`; a reference is a procedure, not evidence that the prediction is experimentally correct.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned Protenix release, downloading weights or databases, using public MSA services, and running GPU/remote compute. Name the resource or host and request approval before transfer or allocation. Record approvals, declines, and the stop reason.
2. Define prediction unit, biological assembly, chain identities, ligand state, intended claim, and falsifier. Separate predicted arrangement/structural agreement from experimental interaction evidence; record claim IDs and whether the run is exploratory or decision-bearing.
3. Validate JSON entities, ligand states, templates, constraints, MSAs, and RNA features. Preserve input and hashes. Record unsupported fields rather than silently dropping them; stop on unresolved mapping and mark affected claims `inconclusive` or `unavailable`.
4. Pin model name, code revision, weight checksum and terms, database revisions, training-data cutoff, samples/seeds, inference-time scaling budget, kernels, device, precision, MSA/template mode, and restraints. Record actual runtime revisions and unknown cutoff/overlap explicitly.
5. Smoke-test the official example and verify expected outputs before full inference. Run `protenix pred` into `artifacts/<run-id>/protenix/`; retain inputs, features, models/configs, structures, confidence, logs, timings, and every candidate/failure. Record whether the smoke test passed before proceeding.
6. For each candidate inspect per-chain-pair interface metrics, available ipTM and interface PAE, chain mapping, contacts, ligand stereochemistry and state, geometry, clashes, and restraint satisfaction. Run a PoseBusters-style validity battery when applicable; treat its passes as physical plausibility checks, not evidence of binding or pose correctness.
7. Evaluate known-complex recovery and apo/decoy partners when suitable controls exist. Compare seed/sample diversity and sensitivity to MSA, restraints, seeds, and sampling budget; use matched settings for baselines. Record control identities, outcomes, dependency overlap, and any material conclusion change.
8. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Report uncertainty, cutoff-related leakage risks, and limitations for the exact selected model; downgrade claims if control, sensitivity, or overlap evidence weakens them.
9. Record with `$science-provenance`; run `$science-review` before material conclusions. Verify schema completeness, claim statuses, retained failures, license terms, and separation of prediction from experiment.

## Outputs

Return one `protenix-complex-evidence-v1` record with required fields: `claim_id`, `status` (`planned`, `supported`, `contradicted`, `inconclusive`, or `unavailable`), `claim_class`, `prediction_unit`, `input_hash`, `model_release`, `code_revision`, `weight_checksum`, `license_terms`, `database_revisions`, `training_cutoff_or_unknown`, `MSA_template_provenance`, `restraints`, `inference_budget_settings`, `hardware_precision`, `candidate_paths_hashes`, `chain_pair_metrics`, `ligand_validity`, `controls`, `sample_diversity`, `failures_nulls`, `uncertainty_sensitivity`, `dependencies`, `applicability_domain`, `interpretation`, `limitations`, and `next_action`. Include metrics actually emitted, rejected alternatives, and the smallest falsifiable next action. Separate successful process completion from scientific acceptance.

## Boundaries

Report performance only for the selected model and cutoff. More inference samples increase selection opportunity and compute; record the full budget and avoid unfair comparison to a lower-budget baseline. Structure confidence is not experimental interaction or affinity evidence. Do not infer calibration, generalization, or clinical utility from model confidence. Keep code, weights, database, and service terms distinct and verify the pinned release's actual terms before use or redistribution; Protenix-v2 weights, in particular, may have terms different from released code or other model weights. Stop for unresolved entity/constraint mapping, unsupported chemistry, or unmet approval; preserve failures and mark affected claims inconclusive or unavailable.
