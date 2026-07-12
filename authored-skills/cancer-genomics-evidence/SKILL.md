---
name: cancer-genomics-evidence
description: "Synthesize public cancer genomic alterations across genes, cohorts, molecular profiles, clinical annotations, and literature. Use for somatic landscape, biomarker, resistance, or translational oncology research."
license: MIT
---

# Cancer Genomics Evidence

1. Define cancer type/subtype, stage, cohort, sample/patient unit, gene/variant, alteration class, molecular profile, and clinical endpoint.
2. Resolve genes with cBioPortal/NCBI/Ensembl; retrieve cohort evidence from cBioPortal and curated clinical interpretation from CIViC/ClinVar only where applicable.
3. Preserve study version, assay coverage, tumor purity, sample count, denominator, alteration definition, co-occurrence method, and missing data.
4. Separate prevalence, prognosis, predictive association, functional mechanism, resistance, and clinical actionability.
5. Compare cohorts without pooling incompatible eligibility, ancestry, platform, treatment, or follow-up.

Return cohort-specific evidence, conflicts, bias/coverage limitations, and validation steps. Never present research output as patient-specific interpretation.

Record cohort queries and denominator decisions with `$science-provenance`; run `$science-review` before translational claims.
