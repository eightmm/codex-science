---
name: cancer-genomics-evidence
description: "Synthesize public cancer genomic alterations across genes, cohorts, molecular profiles, clinical annotations, and literature. Use for somatic landscape, biomarker, resistance, or translational oncology research."
license: MIT
---

# Cancer Genomics Evidence

## Decision contract
Role: conductor over independent cohort and evidence lanes. Before retrieval, define cancer type/subtype, stage, cohort, sample or patient unit, gene/variant, alteration class, molecular profile, clinical endpoint, evidence cutoff, and intended decision. Assign stable claim IDs for prevalence, prognosis, predictive association, mechanism, resistance, and actionability separately. State the permitted inference level, denominators, uncertainty rule, and observations that would weaken each claim.

## Reference usage

Read [references/cancer-genomics-evidence-calibration.md](references/cancer-genomics-evidence-calibration.md) before classifying prevalence, prognostic, predictive, mechanistic, resistance, or actionability claims or comparing cohorts.

## Workflow
1. Freeze cancer type/subtype, stage, cohort, patient/sample unit, gene/variant, alteration class, molecular profile, endpoint, cutoff, decision context, inference level, and claim IDs; before comparing cohorts also freeze the study, sample list, assay, alteration definition, co-occurrence method, and treatment group. Record denominators, uncertainty rules, and weakening observations.
2. Normalize genes and variants using cBioPortal/NCBI/Ensembl while retaining symbols, aliases, stable identifiers, build, and unresolved mappings; record identity checks and stop if variant identity cannot be reconciled. Retrieve cohort evidence from cBioPortal and curated clinical interpretation from CIViC/ClinVar only where applicable.
3. Check source terms, cohort/study, molecular profile, assay, coverage, and release; retrieve with `science_search_cbioportal` using verified `query` and optional `limit` (1–10), and use documented public direct access where justified. Connector absence alone does not mean a source is unavailable; never invent endpoint parameters. Record query plan and unavailable/restricted sources.
4. Capture exact queries and responses, study version and release/update, access time, pagination/completeness, record IDs, inclusion/exclusion reasons, terms, assay coverage, sample list/count, filtering, purity when reported, and missing data; validate schema, identifiers, denominators, and null semantics, detect truncation, and use bounded retries. Record denominator and completeness checks; failed or restricted sources are `unavailable`, not negative evidence.
5. Validate alteration definition, sample unit, numerator/denominator, endpoint, treatment group, follow-up, and null semantics; retain each evidence type in its own lane and record unresolved fields.
6. Classify claims as `supported`, `contradicted`, `inconclusive`, or `unavailable` separately for prevalence, prognosis, predictive association, functional mechanism, resistance, and clinical actionability; record directness, uncertainty, bias, and evidence IDs.
7. Assess shared cohorts, overlapping samples, mirrored/propagated portal records, study versions, platform, treatment, eligibility, ancestry, endpoint, and follow-up; record dependency groups and do not pool incompatible cohorts.
8. Run the prespecified controls and sensitivity analyses. Verify sample denominators, cohort eligibility, assay coverage, cohort dependencies, claim class, and source-to-claim evidence links; record check results and fragility, then downgrade unresolved claims.
9. Emit the schema below, save cohort queries and denominator decisions with `$science-provenance`, and run `$science-review` before translational claims; record review status and the smallest falsifiable next analysis.

## Outputs

- schema `cancer-genomics-reconciliation-v1`
- required fields: `scope` (cancer, subtype, stage, cohort, unit, gene_variant, alteration, profile, endpoint, cutoff); `sources` (query, release, access_time, completeness, terms, status); `evidence_rows` (claim_type, source, cohort, assay, alteration_definition, numerator, denominator, endpoint, uncertainty, missingness); `dependency_groups`; `claims` (claim_id, status, rationale, evidence_ids); `controls`; `sensitivity`; `conflicts`; `limitations`; `validation_needs`; `follow_up`; `provenance_ref`; `review_status`

Return normalized entities and assumptions; a cohort-by-claim evidence table with source/query, release, alteration definition, sample unit, numerator/denominator, endpoint, uncertainty, and missingness; included and excluded records with reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, conflicts, rejected alternatives, bias/coverage limitations, and validation needs; and the smallest falsifiable next experiment or analysis. Save cohort queries and denominator decisions with `$science-provenance`. Run `$science-review` before translational claims.

## Boundaries

Never present research output as patient-specific interpretation. Mutation prevalence does not establish efficacy; a prognostic association does not establish a predictive treatment association, and a predictive association does not establish prognosis; co-occurrence does not establish causality. Stop if sample unit, cohort eligibility, endpoint, or variant identity cannot be reconciled. Preserve missing/null evidence and disagreement; do not silently harmonize it away.
