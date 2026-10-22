---
name: gnina-docking
description: "Run reproducible local GNINA docking or CNN rescoring on protein-ligand systems. Use when GPU-assisted pose generation, refinement, or CNN reranking is wanted; keep CNN pose score, predicted affinity, and experimental affinity as distinct quantities."
license: MIT
---

# GNINA Docking

## Decision contract

Declare whether the goal is pose generation, redocking, or comparative ranking; specify target/receptor state, ligand microstates, pocket definition, evaluation split, and acceptance criterion. Assign claim IDs and define a control or observation that could falsify each material conclusion. Stop if receptor/ligand mapping, pocket, or split provenance is not adequate to preserve the intended question. Keep execution, pose recovery, ranking, model confidence, predicted affinity, and experimental validity as separate claim classes.

## Reference usage

Read [gnina-evidence-and-controls.md](references/gnina-evidence-and-controls.md) before interpreting CNN or empirical scoring outputs, designing benchmark splits/controls, choosing sensitivity runs, or making applicability claims. Consult it before comparing GNINA versions, CNN models, or score modes.

## Workflow

1. **Gates (ask before proceeding).** Follow `$cx-compute-environment`; ask once for the pinned GNINA binary/container, model download, GPU compute, and any structure download. Require prepared inputs from `$cx-molecular-input-preparation`; prefer the official release binary or a digest-pinned container over a source build. Record approvals and the frozen task.
2. Declare pose generation, redocking, or comparative ranking; freeze claim IDs, split, acceptance criterion, baselines, and falsifying observations. Record reference identity, denominators, and whether any structure is used for autoboxing.
3. Validate receptor and ligand atom mapping, stereochemistry, protonation, and box coordinates; record preparation choices, receptor state, exclusions, and ligand microstates.
4. Pin GNINA release, binary checksum/container digest, CUDA/GPU, CNN model, empirical scoring function, `cnn_scoring` mode, box/autobox source, seed, exhaustiveness, and number of modes; record the exact command and environment identity.
5. Smoke-test the binary and a positive-control complex; use an experimental reference ligand for autoboxing only when legitimate for the evaluation split. Record diagnostics and pass criteria.
6. Run docking/rescoring and retain SDF properties, raw log, receptor, reference ligand, exact command, and failures under `artifacts/<run-id>/gnina/`; keep empirical energy, CNN pose score, and CNN affinity output in separate fields and preserve all attempted cases.
7. Validate redocking and ranking with `$cx-docking-validation`; compare with prespecified controls and baselines, retain exclusions, and test relevant score-mode/model/seed sensitivity. Record metrics, control outcomes, and fragility.
8. **Verify/check.** Check output schema, atom mapping, score-field separation, reference leakage, denominator, hashes, and claim-to-artifact links; record failed checks and keep affected claims inconclusive.
9. Record environment, material reference-use hashes, and artifact hashes with `$science-provenance`; use `$science-review` before material claims and retain review outcome, limitations, and next discriminating action.

## Outputs

Return a `gnina-docking-evidence-v1` record with required fields: run identity (`run_id`); claim register (`claim_register`); input identity (`input_identity`); model identity (`model_identity`); per-complex execution table (`execution_table`); control results (`controls`); pose evaluation (`pose_evaluation`); score interpretation (`score_interpretation`); uncertainty (`uncertainty`); applicability domain (`applicability_domain`); failures and exclusions (`failures_and_exclusions`); artifact hashes (`artifact_hashes`); hash-bound reference-use ledger (`reference_use_ledger`); and next action (`next_action`). Include normalized inputs and a machine-readable per-complex table with each score in its own field, pose metric, control status, failures/exclusions, and execution identity. Mark claims supported, contradicted, inconclusive, or unavailable. A successful process does not validate the model scientifically.

## Boundaries

CNN confidence/score is not experimental affinity and is not calibrated across arbitrary targets or model versions. Interpret each CNN metric only within the model and task for which it was trained and evaluated; predicted affinity remains a model estimate, not an assay. Blind whole-protein docking needs stronger controls and higher search effort; label it exploratory. Flexible-sidechain docking requires a justified residue set and separate validation; more flexibility does not guarantee realism. Failed controls or unresolved atom mapping prohibit a success claim.
