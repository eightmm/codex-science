---
name: phewas-replication-analysis
description: "Compare one normalized variant across FinnGen, BioBank Japan, and UKB/TOPMed PheWAS evidence. Use for phenotype-wide replication, ancestry heterogeneity, pleiotropy screening, or cohort comparison."
license: MIT
---

# PheWAS Replication Analysis

1. Require `CHR:POS-REF-ALT` and the declared build; resolve rsIDs and liftover before querying.
2. Call `science_search_finngen` (GRCh38), `science_search_biobank_japan`, and `science_search_ukb_topmed` only after confirming each source's build and terms.
3. Start with `limit<=10`; expand only a prespecified phenotype family or significance slice.
4. Harmonize phenotype concepts without erasing source codes. Compare effect allele, beta/OR direction, p-value, case/control counts, allele frequency, ancestry, and release.
5. Report exact replication, directionally consistent near matches, heterogeneous results, unmatched phenotypes, and unavailable sources separately.
6. Save a cohort-by-phenotype table and query metadata; review claims independently.

Do not meta-analyze incompatible phenotypes or unharmonized effects. Population differences, power, ascertainment, LD, and phenotype coding can explain disagreement. TPMI remains terms/access-gated until its public endpoint is independently usable.

Record source releases and cohort tables with `$science-provenance`; run `$science-review` on replication claims.
