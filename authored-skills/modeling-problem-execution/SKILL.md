---
name: modeling-problem-execution
description: "Drive a concrete scientific modeling problem from supplied inputs through model selection, falsifiable plan, one-time approval, environment setup, smoke test, full execution, downstream analysis, provenance, and review. Use when the user provides sequences, structures, molecules, omics data, trajectories, or a specific modeling objective and expects an actual result rather than instructions."
license: MIT
---

# Modeling Problem Execution

Do not stop at a tutorial when a concrete problem and usable inputs are present.
Continue through execution after the required gate.

## Intake

1. Inspect supplied files/data and state the concrete problem, prediction unit,
   deliverable, inference-time information, and non-goals. Ask only for missing
   facts that materially change execution; choose and state safe local defaults.
2. Search the audited catalog and load the narrow specialized modeling skill plus
   required preparation/analysis skills. Prefer a current open implementation
   whose modalities, license, hardware, and evidence boundary fit the problem.
3. For a scientific claim, preregister the question, falsifiable hypothesis,
   prediction, baseline, primary metric, and success threshold. Define the
   smallest falsifying experiment before the expensive run.

## One-time gate

Ask once with the exact package/repository and pin, weight/database downloads,
network hosts, private-data transfer, expected disk/GPU/time, and output path.
After approval, do not pause between reversible steps inside that scope.

## Execute

1. Create an isolated environment or digest-pinned container. Capture the code
   revision, dependency lock, weight checksums, input hashes, hardware, seeds,
   and configuration under `artifacts/<run-id>/`.
2. Validate schemas, chemistry/sequence alphabets, coordinate/feature mappings,
   and privacy. Run the official smoke example or smallest real input first.
3. If preflight succeeds, run the full input. On failure, diagnose and retry
   bounded alternatives within the approved plan; preserve every failed attempt.
4. Compare against the preregistered baseline or an orthogonal model where the
   claim requires it. Never select a favorable model after seeing results without
   labeling that comparison exploratory.
5. Chain downstream work automatically: confidence/geometry and visualization
   for structures; sequence design and independent refolding for generated
   proteins; pose/interactions for complexes; donor/split-aware diagnostics for
   omics; convergence/uncertainty for simulations.
6. Record commands, environment, inputs, outputs, metrics, failures, and claims
   with `$science-provenance`. Run `$science-review`, resolve findings when
   possible, then report results, limitations, and exact artifact paths.

## Docking route

For receptor/ligand inputs, load `$cx-molecular-input-preparation`, the selected
docking engine, `$cx-docking-validation`, and `$cx-plip-interaction-analysis`.
Resolve the pocket in this order: an intended bound ligand whose use is valid for
the evaluation, user-provided residues or box, then a separately validated pocket
prediction. A different pocket is an interpretation-changing fork.

Prespecify ligand microstate and seed handling, pose-to-compound aggregation,
score ties, and sensitivity to receptor/pocket preparation. Redock a reference
when available. Without a valid positive control, label ranking exploratory.
Report the top result as the "highest-priority predicted docking candidate", not
the best binder; docking score and interaction counts are not affinity.

## Stop conditions

Stop only for a new permission boundary, missing essential input, incompatible
hardware/license, unsafe data transfer, or an interpretation-changing fork.
Do not present installation success, a completed process, or model confidence as
a scientific result.
