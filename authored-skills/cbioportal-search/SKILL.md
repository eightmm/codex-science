---
name: cbioportal-search
description: "Resolve cancer genes and plan public cBioPortal cohort queries. Use for somatic alteration, cancer cohort, co-alteration, survival, or translational oncology evidence."
license: MIT
---

# cBioPortal Search

1. Resolve the canonical gene with `science_search_cbioportal` and cross-check Entrez/Ensembl IDs.
2. Define cancer type, study, molecular profile, sample list, alteration class, and denominator before cohort retrieval.
3. Preserve study version, sample/patient unit, assay platform, filtering, missingness, alteration frequency, and access time.
4. Use `$cx-cancer-genomics-evidence` for multi-cohort synthesis and `$science-review` before translational conclusions.

Do not compare frequencies across cohorts without reconciling eligibility, assay coverage, sample unit, and missing data. This is not patient-specific interpretation.

Store cohort queries and denominators with `$science-provenance` before `$science-review`.

Source basis: [cBioPortal web API](https://www.cbioportal.org/api/swagger-ui/index.html).
