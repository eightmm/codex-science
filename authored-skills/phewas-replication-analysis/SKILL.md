---
name: phewas-replication-analysis
description: "Compare one normalized variant across FinnGen, BioBank Japan, and UKB/TOPMed PheWAS evidence. Use for phenotype-wide replication, ancestry heterogeneity, pleiotropy screening, or cohort comparison."
license: MIT
---

# PheWAS Replication Analysis

## Decision contract
Role: analyzer of cross-cohort variant-phenotype evidence. Require a normalized `CHR:POS-REF-ALT` and declared genome build; record the source variant, rsID if resolved, effect allele, and any liftover chain/result. Define the phenotype family, evidence cutoff, replication rule, and permitted claim before querying. Treat exact replication and directionally consistent near matches as separate outcomes.

## Reference usage

Read [references/phewas-evidence-calibration.md](references/phewas-evidence-calibration.md) before labeling replication, comparing source cohorts, or interpreting missing/null results.

## Workflow
1. Retain the original variant and normalize `CHR:POS-REF-ALT` against the declared build; do not silently convert builds or alleles. Verify reference/alternate alleles and any rsID/liftover mapping, preserve the original and transformed variant, record mappings, and stop on ambiguity.
2. Freeze phenotype family, evidence cutoff, and exact versus directional replication criteria before retrieval; record definitions and claim IDs.
3. Check source terms, build, population, and release; call `science_search_finngen` (GRCh38), `science_search_biobank_japan`, and `science_search_ukb_topmed` using only `query` and optional `limit`. Start with `limit=10` (the tool maximum) and expand only a prespecified phenotype family or significance slice; do not invent source-specific parameters. Record availability and query plan. TPMI remains terms/access-gated until its public endpoint is independently usable.
4. Capture exact serialized queries, responses, access time, release/update as reported, pagination/completeness, returned records, exclusions/reasons, and source failures; detect truncated pages and use bounded retries. Record completeness and classify a failed source as unavailable rather than negative evidence.
5. Validate variant identity, phenotype code, effect allele, beta/OR, uncertainty, p-value, counts, allele frequency, ancestry, and null semantics; record each validated or unresolved field.
6. Map phenotype concepts without erasing source codes; assess allele direction, uncertainty, ascertainment, ancestry, build, release, cohort overlap, and propagated records. Track shared cohorts or samples as dependencies and do not count mirrored portal results as independent; record dependency groups and conflicts.
7. Apply the frozen criterion: classify each claim `supported`, `contradicted`, `inconclusive`, or `unavailable`; reserve exact replication for aligned phenotype/allele/estimand and report directional near matches separately. Record each status, rationale, heterogeneous result, unmatched phenotype, unavailable source, and sensitivity result separately.
8. Run the reference's sanity and sensitivity checks. Verify source coverage, returned-record denominators, harmonization, cohort dependencies, missingness, and claim-to-record links; record each check result and downgrade claims when a failure remains unresolved.
9. Emit the schema below, preserve source releases and cohort tables with `$science-provenance`, and send replication claims to `$science-review`; record review status and smallest falsifiable follow-up.

## Outputs

- schema `phewas-reconciliation-v1`
- required fields: `variant` (original, normalized, build, mapping); `phenotype_family` and `phenotype_map`; `criterion` and `cutoff`; `sources` (query, release, access time, coverage, records, exclusions, status); `evidence_rows` (source, cohort, phenotype code, allele, effect, uncertainty, p-value, counts, ancestry, missingness); `dependency_groups`; `claims` (claim_id, status, rationale, evidence_ids); `controls`; `sensitivity`; `conflicts`; `limitations`; `follow_up`; `provenance_ref`; `review_status`

Return normalized variant/build and phenotype mapping; a cohort-by-phenotype table with source/release, original codes, effect allele, beta/OR and uncertainty, p-value, counts, ancestry, query reference, and missingness; included/excluded records with reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependency groups, conflicts, alternative explanations, limitations, and the smallest falsifiable follow-up. Save source releases and cohort tables with `$science-provenance`; run `$science-review` on replication claims.

## Boundaries

Do not meta-analyze incompatible phenotypes or unharmonized effects. Population differences, power, ascertainment, linkage disequilibrium, and phenotype coding can explain disagreement. Preserve null and nonsignificant results with denominators and detection limits; filtered, unavailable, or unqueried records do not establish absence. PheWAS associations do not establish causality or provide clinical guidance.
