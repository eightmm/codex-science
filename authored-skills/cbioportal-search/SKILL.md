---
name: cbioportal-search
description: "Resolve cancer genes and plan public cBioPortal cohort queries. Use for somatic alteration, cancer cohort, co-alteration, survival, or translational oncology evidence."
license: MIT
---

# cBioPortal Search

## Decision contract
Role: retriever. Define the question, gene or variant, cancer type, study, molecular profile, sample or patient unit, alteration class, outcome, denominator, and evidence cutoff before querying. Use stable gene identifiers when available and retain the submitted symbol and aliases. State whether the task asks for cohort description, association, survival, or clinical interpretation; this source alone does not support the latter.

## Workflow
1. Resolve the gene with `science_search_cbioportal` using its `query` and optional `limit` arguments (legacy source tools accept `limit` from 1 to 10). Cross-check Entrez or Ensembl identity where ambiguity could change the cohort result. Do not invent source-specific tool arguments. For broader structured retrieval, inspect the source contract before using `science_query_source_v2` or `science_query_source_v3`; record `source`, parameters, page size, maximum pages, cutoff, and returned completeness fields.
2. Select study, molecular profile, sample list, alteration class, and endpoint from the returned records. Verify eligibility and denominator before calculating frequency. Preserve study and molecular-profile identifiers, sample/patient unit, assay platform, filtering, missingness, and access time.
3. Serialize and save the exact query and filters. Follow the endpoint's documented pagination for direct API access; record each page or cursor, total/returned counts, release or update marker reported by the response, and stop condition. Validate status, schema, identifiers, counts, and truncation before interpreting results. Retry transient failures only within a small fixed bound; report throttling, malformed responses, and unavailable fields explicitly.
4. Return records actually included and excluded with reasons. Distinguish absent alterations, unprofiled samples, filtered records, null clinical values, and query failure. Never treat a missing field as a negative finding. Preserve source citations and usage terms; do not redistribute data beyond their stated terms.

## Outputs
Return normalized gene and cohort inputs; an evidence table with study/profile/sample identifiers, query reference, release/access time, assay, numerator, denominator, and missingness; included/excluded record counts and reasons; claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies across studies; uncertainty and cohort limitations; rejected cohort alternatives; and the smallest falsifiable follow-up. Save queries, denominators, response metadata, and hashes with `$science-provenance`. Use `$cx-cancer-genomics-evidence` for multi-cohort synthesis and `$science-review` before translational or comparative claims.

## Boundaries
Do not compare frequencies across cohorts without reconciling eligibility, assay coverage, sample unit, and missing data. Alteration frequency is not penetrance, prognosis, treatment response, or causality. This is not patient-specific interpretation. Stop when gene identity, denominator, or cohort eligibility cannot be resolved; do not silently substitute studies or infer a negative from unavailable data.

Source basis: [cBioPortal web API](https://www.cbioportal.org/api/swagger-ui/index.html).
