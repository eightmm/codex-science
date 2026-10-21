---
name: cancer-genomics-evidence
description: "Synthesize public cancer genomic alterations across genes, cohorts, molecular profiles, clinical annotations, and literature. Use for somatic landscape, biomarker, resistance, or translational oncology research."
license: MIT
---

# Cancer Genomics Evidence

## Decision contract
Role: conductor over independent cohort and evidence lanes. Before retrieval, define cancer type/subtype, stage, cohort, sample or patient unit, gene/variant, alteration class, molecular profile, clinical endpoint, evidence cutoff, and intended decision. Assign stable claim IDs for prevalence, prognosis, predictive association, mechanism, resistance, and actionability separately. State the permitted inference level, denominators, uncertainty rule, and observations that would weaken each claim.

## Workflow
1. Normalize genes and variants with cBioPortal/NCBI/Ensembl, retaining symbols, stable IDs, genome build, and aliases. Use `science_search_cbioportal` with verified `query` and optional `limit` arguments for bounded source retrieval; the source tool limit is 1–10. Use public direct-source access for sources without a bundled connector; connector absence alone does not mean a source is unavailable. Never invent endpoint parameters.
2. Retrieve cohort evidence from cBioPortal and curated clinical interpretation from CIViC/ClinVar only where applicable. Freeze study, molecular profile, sample list, assay, alteration definition, co-occurrence method, treatment group, and clinical endpoint before comparing cohorts. Preserve study version, assay coverage, tumor purity when reported, sample count, denominator, filtering, and missing data.
3. Keep each cohort and evidence type in its own lane. Record exact queries, release/update values returned, access times, pagination, response completeness, record IDs, inclusions/exclusions, and terms. Validate schema, identifiers, denominators, null semantics, and truncation. Use bounded retries; failed or restricted sources are `unavailable`, not negative evidence.
4. Grade directness, independence, replication, bias, and applicability. Compare cohorts without pooling incompatible eligibility, ancestry, platform, treatment, endpoint, or follow-up. Deduplicate shared cohorts and propagated portal records. Separate prevalence, prognosis, predictive association, functional mechanism, resistance, and clinical actionability in synthesis.

## Outputs
Return normalized entities and assumptions; a cohort-by-claim evidence table with source/query, release, alteration definition, sample unit, numerator/denominator, endpoint, uncertainty, and missingness; included and excluded records with reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, conflicts, rejected alternatives, bias/coverage limitations, and validation needs; and the smallest falsifiable next experiment or analysis. Save cohort queries and denominator decisions with `$science-provenance`. Run `$science-review` before translational claims.

## Boundaries
Never present research output as patient-specific interpretation. Do not infer efficacy from mutation prevalence, prognosis from predictive association, or causality from co-occurrence. Stop if sample unit, cohort eligibility, endpoint, or variant identity cannot be reconciled. Preserve missing and null evidence; do not silently harmonize away disagreement.
