---
name: metabolomics-proteomics-context
description: "Integrate public metabolite, reaction, protein, proteomics, and study evidence. Use for pathway mechanism, biomarker context, multi-omics follow-up, or dataset selection."
license: MIT
---

# Metabolomics And Proteomics Context

1. Normalize metabolites/chemical forms with ChEBI/PubChem and proteins with UniProt; preserve species and modification state.
2. Use Rhea/Reactome for reaction/pathway context and PRIDE/ProteomeXchange for public proteomics studies.
3. Treat MetaboLights/HMDB as terms- and availability-gated sources; do not claim live coverage when access is blocked or search is not query-specific.
4. Preserve assay platform, extraction, quantification, normalization, identification confidence, batch, sample unit, release, and file provenance.
5. Reconcile feature-to-entity mapping, missingness, multiple testing, and pathway over-representation assumptions.

Return evidence maps and reusable dataset candidates separately. Spectral match, abundance change, pathway membership, and causal mechanism are distinct claims.

Run `$science-review` on cross-omics identity and mechanism claims.
