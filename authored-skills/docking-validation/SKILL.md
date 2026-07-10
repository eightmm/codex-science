---
name: docking-validation
description: "Validate docking, pose-prediction, rescoring, and virtual-screening workflows with leakage-aware controls and prespecified metrics. Use before interpreting AutoDock Vina, GNINA, DiffDock, or related docking outputs."
license: MIT
---

# Docking Validation

## Validation ladder

1. **Input audit:** verify receptor assembly/state, ligand stereo/protonation,
   cofactors/metals/waters, pocket definition, atom mapping, and provenance.
2. **Positive-control redocking:** prespecify top-1/top-k symmetry-aware heavy-atom
   RMSD thresholds. Report the complete distribution, not one favorable pose.
3. **Cross-docking:** test receptor conformation sensitivity when multiple holo or
   apo structures exist. Separate apo, holo, and predicted receptors.
4. **Screening:** define actives/decoys and negative provenance before scoring.
   Report enrichment factor, BEDROC or PR-AUC plus ROC-AUC; bootstrap uncertainty
   by compound or target as appropriate.
5. **Generalization:** use cold-ligand, cold-target, and cold-both splits. Cluster
   by chemical scaffold and target homology before splitting.
6. **Leakage:** check bound-pose/template overlap, ligand-frame leakage, duplicated
   complexes, shared analog series, and model training-set overlap.
7. **Calibration:** if a score is used probabilistically, test calibration and
   applicability domain. Do not regress docking score directly to experimental
   affinity without assay-aware validation.

Save the protocol, exclusions, failures, metrics, confidence intervals, and raw
tables with `$science-provenance`; review claims with `$science-review`.

