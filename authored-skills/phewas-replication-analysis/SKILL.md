---
name: phewas-replication-analysis
description: "Compare one normalized variant across FinnGen, BioBank Japan, and UKB/TOPMed PheWAS evidence. Use for phenotype-wide replication, ancestry heterogeneity, pleiotropy screening, or cohort comparison."
license: MIT
---

# PheWAS Replication Analysis

## Decision contract
Role: analyzer of cross-cohort variant-phenotype evidence. Require a normalized `CHR:POS-REF-ALT` and declared genome build; record the source variant, rsID if resolved, effect allele, and any liftover chain/result. Define the phenotype family, evidence cutoff, replication rule, and permitted claim before querying. Treat exact replication and directionally consistent near matches as separate outcomes.

## Workflow
1. Resolve rsIDs and liftover before querying. Never silently convert builds or alleles; verify the resulting reference/alternate allele and preserve the original plus transformed variant. Stop if the mapping is ambiguous.
2. Confirm each source's build, population, release, and terms, then call `science_search_finngen` (GRCh38), `science_search_biobank_japan`, and `science_search_ukb_topmed`. These legacy tools take `query` and optional `limit`; start with `limit=10` (the tool maximum) and expand only a prespecified phenotype family or significance slice. Do not invent source-specific parameters.
3. Record exact serialized query, source response, access time, release/update value as reported, returned records, exclusions and reasons, and pagination/completeness. Validate variant identity, phenotype code, effect allele, beta/OR, p-value, case/control counts, allele frequency, ancestry, and null fields. Detect truncated pages and bound retries. A failed source is unavailable, not a negative replication.
4. Harmonize phenotype concepts without erasing source codes. Compare effect allele and beta/OR direction, uncertainty, p-value, counts, ancestry, ascertainment, build, and release. Track shared cohorts or samples as dependencies; do not count mirrored portal results as independent. Report exact replication, directionally consistent near matches, heterogeneous results, unmatched phenotypes, and unavailable sources separately. TPMI remains terms/access-gated until its public endpoint is independently usable.

## Outputs
Return normalized variant/build and phenotype mapping; a cohort-by-phenotype table with source/release, original codes, effect allele, beta/OR and uncertainty, p-value, counts, ancestry, query reference, and missingness; included/excluded records with reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependency groups, conflicts, alternative explanations, limitations, and the smallest falsifiable follow-up. Save source releases and cohort tables with `$science-provenance`; run `$science-review` on replication claims.

## Boundaries
Do not meta-analyze incompatible phenotypes or unharmonized effects. Population differences, power, ascertainment, LD, and phenotype coding can explain disagreement. A PheWAS association is not causal evidence or clinical guidance. Preserve null and nonsignificant results with their denominator and detection limits; do not infer absence from a filtered or unavailable record.
