---
name: docking-validation
description: "Validate docking, pose-prediction, rescoring, and virtual-screening workflows with leakage-aware controls and prespecified metrics. Use before interpreting AutoDock Vina, GNINA, DiffDock, or related docking outputs."
license: MIT
---

# Docking Validation

## Reference usage

Read [benchmark design](references/benchmark-design.md) before defining states, pockets, controls, or data splits. Read [metrics and acceptance](references/metric-and-acceptance.md) before computing metrics, fixing thresholds, calibrating scores, or declaring a pass. Read [inference boundaries](references/inference-boundaries.md) before writing pose, ranking, affinity, mechanism, or generalization claims.

Do not infer benchmark information boundaries, metric aggregation, or claim strength from an engine name or score. Record the reference hashes used for a material benchmark or claim in a `reference-use-ledger`.

## Decision contract
Prespecify the use case, prediction unit, receptor and ligand states, pocket information allowed at inference, benchmark split, controls, primary metric, uncertainty method, applicability domain, and success threshold before inspecting outcomes.
Treat benchmark construction, preparation, pose generation, scoring, and decision analysis as separate stages with separate artifacts.

## Workflow
1. Audit biological assembly, chain and residue mapping, protonation, tautomers, stereochemistry, charges, metals, cofactors, waters, covalent bonds, pocket definition, and every conversion hash.
2. Redock valid reference ligands with symmetry-aware heavy-atom RMSD and interaction recovery; report top-1, top-k, failures, and the complete distribution rather than a favorable pose.
3. Cross-dock across apo, holo, alternate-state, and predicted receptors when the claim requires conformation robustness; quantify sensitivity to preparation, pocket, microstate, seed, and pose aggregation.
4. For screening, define actives, property-matched decoys, assay provenance, and compound-level grouping; report PR-AUC plus enrichment metrics and bootstrap intervals, with ROC-AUC only as a secondary view.
5. Test cold-ligand, cold-target, and cold-both generalization using scaffold and target-homology groups; audit bound-pose, template, ligand-frame, analog-series, duplicate-complex, and model-training overlap.
6. Compare against simple baselines and an orthogonal method where feasible; calibrate probabilistic claims, define abstention rules, and keep pose confidence, ranking score, predicted affinity, and experimental affinity distinct.
7. Report metrics by target, scaffold, receptor state, ligand class, and failure mode; inspect whether aggregate gains are driven by a narrow or leaked subgroup.
8. For affinity or mechanism claims, require assay-aware external evidence beyond docking and state the domain where the conclusion is unsupported.

## Outputs
Save the protocol, split ledger, leakage report, exclusions, raw poses and scores, metric tables with intervals, failure taxonomy, sensitivity analyses, and applicability domain.
Assign each prespecified claim a pass, fail, or inconclusive result and retain negative controls and failed systems.
Save engine and model revisions, seeds, command lines, preparation manifests, and pose-to-compound aggregation rules so the benchmark can be rerun exactly.

## Boundaries
Do not tune thresholds on held-out data, derive a benchmark pocket from the held-out pose, count related analogs as independent, or infer affinity or mechanism from a docking score.
Record all artifacts with `$science-provenance`; require `$science-review` before reporting generalization, enrichment, affinity, or mechanism claims.
