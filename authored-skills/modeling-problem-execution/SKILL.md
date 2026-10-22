---
name: modeling-problem-execution
description: "Drive a concrete scientific modeling problem from supplied inputs through model selection, falsifiable plan, one-time approval, environment setup, smoke test, full execution, downstream analysis, provenance, and review. Use when the user provides sequences, structures, molecules, omics data, trajectories, or a specific modeling objective and expects an actual result rather than instructions."
license: MIT
---

# Modeling Problem Execution

## Decision contract

State the concrete modeling objective, supplied inputs, prediction unit, intended deliverable, and inference-time information. Define the smallest falsifier, acceptance criteria, and required approval boundary before execution. Do not stop at a tutorial when a concrete problem and usable inputs are present; continue through execution after the required gate.

## Reference usage

Read [references/model-execution-evidence.md](references/model-execution-evidence.md) before selecting a model for a scientific claim, preregistering an evaluation, interpreting process completion, or judging sensitivity and validity. It specifies model-fit evidence, dependency and revision records, controls, uncertainty, and failure semantics.

## Workflow

1. **One-time approval gate (standing rule; ask after intake, method selection and the falsifiable plan fix the pins).** Before any gated action, ask once with the exact package/repository and pin, weight/database downloads, network hosts, private-data transfer, expected disk/GPU/time, and output path; after approval, do not pause between reversible steps inside that scope. Approval covers only that envelope, and request approval again if data boundary, environment, resources, or method changes.
2. **Intake and directive.** Inspect supplied files/data and state the concrete problem, prediction unit, deliverable, inference-time information, and non-goals; if a missing fact materially changes execution, ask, otherwise choose and record safe local defaults, then continue through execution rather than returning only a tutorial.
3. **Method selection.** Search the audited catalog and load the narrow specialized modeling skill plus required preparation/analysis skills; prefer a current open implementation whose modalities, license, hardware, and evidence boundary fit the problem, and record candidates, rationale, exclusions, and versions.

   **Docking route.** For receptor/ligand inputs, load `$cx-molecular-input-preparation`, the selected docking engine, `$cx-docking-validation`, and `$cx-plip-interaction-analysis`. Resolve the pocket in this order: an intended bound ligand whose use is valid for the evaluation, user-provided residues or box, then a separately validated pocket prediction. A different pocket is an interpretation-changing fork.

   Prespecify ligand microstate and seed handling, pose-to-compound aggregation, score ties, and sensitivity to receptor/pocket preparation. Redock a reference when available. Without a valid positive control, label ranking exploratory. Report the top result as the "highest-priority predicted docking candidate", not the best binder; docking score and interaction counts are not affinity.
4. **Falsifiable plan.** For a scientific claim, preregister the question, falsifiable hypothesis, prediction, baseline, primary metric, success threshold, and smallest falsifying experiment before the expensive run; record data split, seeds, and stopping rule when relevant.
5. **Environment and input preflight.** Create an isolated environment or digest-pinned container and capture code revision, dependency lock, weight checksums, input hashes, hardware, seeds, and configuration under `artifacts/<run-id>/`; validate schemas, chemistry/sequence alphabets, coordinate/feature mappings, and privacy.
6. **Smoke and execution.** Run the official smoke example or smallest real input first; only if preflight succeeds run the full input. Diagnose and retry bounded alternatives within the approved plan, preserve every failed attempt, and stop at a new permission boundary or incompatible prerequisite.
7. **Controls and downstream analysis.** Compare against the preregistered baseline or an orthogonal model where the claim requires it; chain applicable analyses automatically (structure confidence/geometry and visualization, sequence design and independent refolding for generated proteins, complex pose/interactions, donor/split-aware omics diagnostics, or simulation convergence/uncertainty) and record control outcomes.
8. **Sensitivity and decision.** Vary relevant settings, seeds, splits, and preprocessing; assess whether conclusions change against the declared threshold, distinguish exploratory model selection from confirmatory results, and record uncertainty, failure taxonomy, and applicability limits.
9. **Verify and hand off.** Record commands, environment, inputs, outputs, metrics, failures, and claims with `$science-provenance`; run `$science-review`, resolve findings when possible, then report the scientific acceptance result separately from process status with limitations and exact artifact paths.

## Outputs

Return one `model-execution-evidence-v1` record with required fields: decision contract (`decision_contract`), inputs (`inputs`), model candidates (`model_candidates`), selection rationale (`selection_rationale`), preregistered plan (`preregistered_plan`), approval scope (`approval_scope`), environment (`environment`), smoke result (`smoke_result`), execution runs (`execution_runs`), controls (`controls`), sensitivity analysis (`sensitivity_analysis`), claim register (`claim_register`), scientific acceptance (`scientific_acceptance`), uncertainty (`uncertainty`), applicability domain (`applicability_domain`), limitations (`limitations`), failed attempts (`failed_attempts`), next action (`next_action`), artifact paths and hashes (`artifact_paths_and_hashes`), and review receipt (`review_receipt`). Use claim statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`; retain commands, derivations, and hashes through `$science-provenance`.

## Boundaries

- Do not present installation success, process completion, confidence, docking scores, or interaction counts as scientific validation or affinity.
- Stop only for a new permission boundary, missing essential input, incompatible hardware/license, unsafe data transfer, an interpretation-changing fork, or a failed essential schema or smoke invariant check.
- Do not present model confidence as calibrated probability without domain-specific calibration evidence.
- Preserve failures and nulls; if a control is unavailable or a result is sensitive to reasonable settings, label the claim exploratory or inconclusive.

## Source basis

This workflow is an original synthesis informed by Hefferon's openly licensed *Linear Algebra*;
source provenance is recorded in `../../docs/TEXTBOOK_SOURCES.md`.
