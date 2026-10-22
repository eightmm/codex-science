---
name: gene-burden-evidence
description: "Assess rare-variant gene burden evidence with explicit cohort, ancestry, mask, frequency threshold, model, phenotype, and multiple-testing semantics. Use for gene-level human genetic support and locus-to-gene follow-up."
license: MIT
---

# Gene Burden Evidence

## Decision contract
Role: analyzer of supplied or retrieved rare-variant burden results. Define gene/transcript, phenotype, cohort, ancestry, case/control unit, qualifying variant mask, frequency threshold, statistical model, correction family, evidence cutoff, and intended claim. State whether the analysis is discovery, replication, or descriptive; freeze the variant mask and phenotype mapping before comparing results.

## Reference usage

Read [references/gene-burden-evidence-calibration.md](references/gene-burden-evidence-calibration.md) before interpreting burden claims, aligning masks, or deciding whether cohorts provide independent replication.

## Workflow
1. Freeze the claim purpose (discovery, replication, descriptive), gene/transcript, phenotype, cohort, ancestry, case/control unit, build, mask, frequency threshold, model, correction family, and cutoff; record this contract before inspecting comparative results.
2. Validate source terms, endpoint, and release; retrieve a versioned result only when supported by the source contract, otherwise record unavailable. Use a bundled tool only within its declared contract or a documented public endpoint; absence of a repository connector alone does not make a source unavailable. GeneBass and similar portals remain availability-gated until a stable, documented public API is verified; do not infer source-specific fields or parameters.
3. Validate gene/transcript, phenotype, cohort, ancestry, case/control counts, build, qualifying consequences, and mask; retain original IDs and unresolved mappings, and do not infer a mask from a gene-level label. Record validation outcomes.
4. Capture exact query, response, access time, release/update, completeness, pagination, included/excluded records and reasons; validate response fields, detect truncation, preserve missing estimates, null values, and unavailable sources separately. Use bounded retries only for transient failures and record provenance.
5. Validate effect direction, interval, p-value, burden/SKAT model, covariates, correction scope, sample size, and sample unit; record missing fields and statistical uncertainty without interpreting absent values as null effects.
6. Compare results only after aligning phenotype, mask, ancestry, build, model, correction scope, and estimand; record shared samples, cohort and propagated-summary dependencies, and keep coding/constraint evidence in distinct lanes.
7. Classify claims `supported`, `contradicted`, `inconclusive`, or `unavailable`; separate discovery from replication and state which aligned independent evidence supports each classification, recording reasons.
8. Run mask, phenotype, and other prespecified sensitivity checks plus sanity controls. Verify the source contract, denominators, mask, correction family, cohort dependence, and claim-to-evidence links; record check results and fragility, then downgrade unresolved claims.
9. Emit the schema below; record source, release, cohort, mask, model, results, and hashes with `$science-provenance`; use burden evidence as one lane in `$cx-locus-to-gene-prioritization` and submit synthesis to `$science-review`.

## Outputs

- schema `gene-burden-reconciliation-v1`
- required fields: `gene_transcript`; `phenotype`; `analysis_contract` (cohort, ancestry, unit, build, mask, frequency_threshold, model, correction_family, cutoff, purpose); `sources` (query, release, access_time, coverage, status); `evidence_rows` (source, cohort, dependencies, counts, effect, interval, p_value, correction, missingness); `included_excluded`; `claims` (claim_id, status, rationale, evidence_ids); `controls`; `sensitivity`; `uncertainty`; `limitations`; `follow_up`; `provenance_ref`; `review_status`

Return normalized gene/transcript, phenotype, cohort, and mask; a result table with source/release, cohort, ancestry, unit/counts, mask, model, effect, interval, p-value, correction, query reference, and missingness; included/excluded records and reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, uncertainty, rejected alternatives, applicability limits, and the smallest falsifiable replication or sensitivity analysis. Record source, release, cohort, mask, model, results, and hashes with `$science-provenance`; run `$science-review` before synthesis.

## Boundaries

Do not treat results from differently defined phenotypes, masks, estimands, or correction families as exact replication. A significant gene-level burden is not proof that a gene causes disease or identifies a causal variant. Missing p-values do not establish nonsignificance; keep discovery and replication evidence separate. Stop when source terms, endpoint, phenotype, or mask cannot be verified, and retain unresolved evidence as `inconclusive` or `unavailable`.
