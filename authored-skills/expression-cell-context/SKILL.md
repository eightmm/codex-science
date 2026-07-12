---
name: expression-cell-context
description: "Reconcile gene expression across GTEx, Human Protein Atlas, Bgee, cell atlases, and disease datasets. Use for tissue, cell-type, developmental, baseline-versus-disease, or target-expression questions."
license: MIT
---

# Expression And Cell Context

1. Normalize gene, species, transcript, tissue ontology, cell type, disease state, and assay.
2. Use GTEx for bulk non-diseased tissue, HPA for tissue/cell protein and RNA context, Bgee for healthy ontology-aware expression, and cellxgene/scRNA workflows for cell-level evidence.
3. Keep assay units, normalization, donor/sample counts, batch, tissue composition, release, and detection thresholds separate.
4. Distinguish baseline expression, differential expression, eQTL, protein localization, and functional dependence.
5. Return concordant and discordant contexts plus experiments that resolve cell-state or assay ambiguity.

Do not infer absence from dropout or portal filtering. Bulk tissue does not identify the expressing cell type; RNA does not guarantee protein abundance or activity.

Save assay-context tables with `$science-provenance`; use `$science-review` for cross-assay conclusions.
