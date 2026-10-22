---
name: autodock-vina-docking
description: "Run reproducible local protein-ligand docking with AutoDock Vina and Meeko. Use for pose generation, redocking, or small virtual screens when a receptor and a justified binding pocket are available; do not use a Vina score as experimental affinity."
license: MIT
---

# AutoDock Vina Docking

## Decision contract

Define whether the deliverable is a pose, a redocking validation, or an exploratory ranking; identify receptor, ligand microstates, intended pocket, evidence cutoff, and a prespecified pose-success criterion. Treat docking as pose generation, not affinity measurement. Record claim IDs and the control or observation that could falsify each material pose claim. A missing receptor state, ligand state, or pocket definition that changes the question is a stop condition. Keep process completion, pose agreement, ranking performance, and experimental binding validity as separate claim classes.

## Reference usage

Read [vina-evidence-and-controls.md](references/vina-evidence-and-controls.md) before selecting or interpreting pose and ranking claims, controls, sensitivity analyses, or applicability limits. Read it before constructing evaluation splits or comparing scores across receptor, ligand, or Vina versions.

## Workflow

1. **Gates (ask before proceeding).** Follow `$cx-compute-environment` and ask once before installing pinned Vina, Meeko, or preparation dependencies and before compute; require `$cx-molecular-input-preparation` outputs and an explicit pocket definition. Stop for unresolved receptor state, ligand state, pocket, or evaluation leakage; record approvals, blockers, and the frozen question.
2. Declare pose generation, redocking validation, or exploratory ranking, then freeze claim IDs and a symmetry-aware pose-success criterion; record criteria, denominator, reference identity, and falsifying observations.
3. Validate atom mapping, stereochemistry, charges, receptor assembly/state, and pocket coordinates; record preparation provenance, excluded waters/cofactors, ligand microstates, and unresolved structural uncertainty.
4. Pin Vina and Meeko versions and record box center and size in Å, exhaustiveness, modes, energy range, CPU count, seed, and environment identity; record the exact configuration and input hashes.
5. Smoke-test one ligand and confirm the search box covers the intended pocket without clipping ligand rotation; run a positive-control redock before screening, and record diagnostics and pass criteria.
6. Run each ligand state independently; retain raw PDBQT, log, config, converted SDF poses, and failures under `artifacts/<run-id>/vina/`, recording every attempted case and its execution status.
7. Compare poses with the frozen criterion and report pose ranking separately from compound ranking; use cold-target/ligand controls and decoys for comparative screening claims, and apply `$cx-docking-validation`; record metrics, controls, exclusions, and sensitivity results.
8. **Verify/check.** Check atom maps, pose conversion, hashes, denominators, controls, and the claim-to-artifact links; record failed checks and keep affected conclusions inconclusive.
9. Preserve commands, environment, control results, exclusions, uncertainties, material reference-use hashes, and artifacts with `$science-provenance`; obtain `$science-review` before material conclusions and record the review receipt and next discriminating action.

## Outputs

Return a `vina-docking-evidence-v1` record with required fields: run identity (`run_id`); claim register (`claim_register`); input identity (`input_identity`); model identity (`model_identity`); per-ligand execution table (`execution_table`); control results (`controls`); pose evaluation (`pose_evaluation`); uncertainty (`uncertainty`); applicability domain (`applicability_domain`); failures and exclusions (`failures_and_exclusions`); artifact hashes (`artifact_hashes`); hash-bound reference-use ledger (`reference_use_ledger`); and next action (`next_action`). Include normalized receptor/ligand-state inputs and a machine-readable per-ligand execution table with status, score, pose criterion, control result, and failure reason. Mark claims supported, contradicted, inconclusive, or unavailable. Preserve pose diversity, uncertainty, exclusions, limitations, apo/holo and assembly/template provenance, and hashes. Process completion is not scientific validation.

## Boundaries

Vina energy is a model score, not measured binding free energy or IC50/Kd. A score or successful run alone cannot establish affinity, binding, or enrichment. Do not leak a held-out bound pose into pocket construction or ligand initialization. Invalid or mismatched atom states, failed controls, or an undefined pocket leave conclusions inconclusive. Report applicability limits and ask before any gated installation or compute. Agreement with a known structure supports pose recovery only under the tested receptor, ligand, preparation, and search conditions; it does not validate affinity or prospective performance.
