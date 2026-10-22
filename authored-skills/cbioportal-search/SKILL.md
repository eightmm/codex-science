---
name: cbioportal-search
description: "Resolve cancer genes and plan public cBioPortal cohort queries. Use for somatic alteration, cancer cohort, co-alteration, survival, or translational oncology evidence."
license: MIT
---

# cBioPortal Search

## Decision contract
Role: retriever. Define the question, gene or variant, cancer type, study, molecular profile, sample or patient unit, alteration class, outcome, denominator, and evidence cutoff before querying. Use stable gene identifiers when available and retain the submitted symbol and aliases. State whether the task asks for cohort description, association, survival, or clinical interpretation; this source alone does not support the latter. Classify claims as source description (what a selected study/profile reports), cohort estimate (frequency in a defined eligible denominator), association (a specified comparison under its analysis assumptions), or unavailable/contradicted/inconclusive. Do not turn any portal summary into patient-level prediction or clinical actionability.

## Reference usage
Read [cBioPortal cohort and claim semantics](references/cbioportal-cohort-claims.md) before assigning evidence status, comparing studies, interpreting survival or alteration frequencies, or reporting sensitivity. It defines dependency checks, controls, uncertainty, and the source's applicability limits.

## Workflow
1. **Gates (ask before proceeding).** If gene identity, cohort eligibility, denominator, access terms, or a requested clinical interpretation cannot be resolved without materially changing the question, stop and ask; do not silently substitute a study or profile. Record the unresolved choice and stop reason.
2. Normalize the gene/variant and question; retain submitted symbols, aliases, and stable identifiers. If ambiguity could change retrieval, cross-check Entrez or Ensembl identity; record mappings, alternatives, and the intended claim class.
3. Resolve the gene with `science_search_cbioportal` using its `query` and optional `limit` arguments (legacy source tools accept `limit` from 1 to 10). For broader structured retrieval, inspect the source contract before `science_query_source_v2` or `science_query_source_v3`; use only documented arguments. Record source, parameters, page size, page cap, cutoff, and completeness fields.
4. Select study, molecular profile, sample list, alteration class, and endpoint only when returned metadata match the contract. **Verify** eligibility and the sample/patient denominator before calculating frequency; record study/profile IDs, assay, filtering, missingness, numerator, denominator, and access time.
5. Serialize the exact query and filters. For direct API access, follow documented pagination and record every page/cursor, reported totals, release/update marker, and stop condition. Validate response status, schema, IDs, counts, and truncation; retry transient failures only within a small fixed bound. Record throttling, malformed responses, unavailable fields, and failed attempts.
6. Include and exclude records with reasons, distinguishing absent alterations, unprofiled samples, filtered records, null clinical values, and query failure. Never treat a missing field as a negative. Record a supported, contradicted, inconclusive, or unavailable status with the source-level claim and dependencies; cite source and terms, and do not redistribute beyond stated terms.
7. Run the reference's negative/control and sensitivity checks when estimating or comparing cohorts. If denominator, missingness, assay coverage, cohort overlap, or analysis choices alter the interpretation, downgrade to inconclusive or report separate strata; record the perturbations and their effect.
8. Save query, denominator, response metadata, and hashes with `$science-provenance`; use `$cx-cancer-genomics-evidence` for multi-cohort synthesis and `$science-review` before translational or comparative claims. Record unresolved limitations and the smallest falsifiable follow-up.

## Outputs
Return one `cbioportal-evidence-reconciliation-v1` record with: question and evidence cutoff (`question_and_cutoff`); normalized gene and aliases (`normalized_gene_and_aliases`); claim register (`claim_register`: claim ID, class, text, status, evidence IDs); cohort evidence table (`cohort_table`: study/profile/sample IDs, query reference, release/access time, assay, numerator, denominator, missingness, inclusion/exclusion); included and excluded record counts with reasons (`record_flow`); query provenance (`query_provenance`: serialized query, filters, pages, completeness, response hashes); dependency graph (`dependency_graph`: shared cohort/source/release relations); uncertainty and sensitivity (`uncertainty_and_sensitivity`); controls (`controls`); applicability domain (`applicability_domain`); rejected alternatives (`rejected_alternatives`); limitations (`limitations`); smallest falsifiable follow-up (`next_falsifiable_action`); provenance and review references (`provenance_and_review_refs`). Save queries, denominators, response metadata, and hashes with `$science-provenance`. Use `$cx-cancer-genomics-evidence` for multi-cohort synthesis and `$science-review` before translational or comparative claims.

## Boundaries
Do not compare frequencies across cohorts without reconciling eligibility, assay coverage, sample unit, and missing data. Alteration frequency is not penetrance, prognosis, treatment response, or causality. This is not patient-specific interpretation. Stop when gene identity, denominator, or cohort eligibility cannot be resolved; do not silently substitute studies or infer a negative from unavailable data.

Source basis: [cBioPortal web API](https://www.cbioportal.org/api/swagger-ui/index.html).
