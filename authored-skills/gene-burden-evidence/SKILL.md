---
name: gene-burden-evidence
description: "Assess rare-variant gene burden evidence with explicit cohort, ancestry, mask, frequency threshold, model, phenotype, and multiple-testing semantics. Use for gene-level human genetic support and locus-to-gene follow-up."
license: MIT
---

# Gene Burden Evidence

## Decision contract
Role: analyzer of supplied or retrieved rare-variant burden results. Define gene/transcript, phenotype, cohort, ancestry, case/control unit, qualifying variant mask, frequency threshold, statistical model, correction family, evidence cutoff, and intended claim. State whether the analysis is discovery, replication, or descriptive; freeze the variant mask and phenotype mapping before comparing results.

## Workflow
1. Validate gene/transcript identity, cohort and ancestry, phenotype definition, case/control counts, build, qualifying consequences, and mask. Preserve original source identifiers and do not infer a mask from a gene-level label.
2. Retrieve a versioned public burden result only from a source whose terms and endpoint are available; otherwise report the source as unavailable instead of fabricating a lookup. Use a bundled source tool only when its contract covers the query; use a documented public direct endpoint when available. Absence of a repository connector alone does not make a source unavailable. GeneBass and similar portals remain availability-gated until a stable, documented public API is verified.
3. Record mask, consequence definition, sample size, effect direction, confidence interval, p-value, burden/SKAT model, covariates if reported, and correction scope. Capture exact query, source release/update as reported, access time, pagination/completeness, included and excluded records, and reasons. Validate response fields and truncation; preserve missing estimates, null values, and unavailable sources separately. Use bounded retries only for transient failures.
4. Compare independent cohorts only after aligning phenotype, mask, ancestry, build, model, and correction scope. Keep discovery and replication separate. Compare coding/constraint evidence as distinct evidence types, track shared samples and study dependencies, and report sensitivity to mask or phenotype choices. Use burden evidence as one lane in `$cx-locus-to-gene-prioritization`, never as standalone causal proof.

## Outputs
Return normalized gene/transcript, phenotype, cohort, and mask; a result table with source/release, cohort, ancestry, unit/counts, mask, model, effect, interval, p-value, correction, query reference, and missingness; included/excluded records and reasons; claim IDs marked `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, uncertainty, rejected alternatives, applicability limits, and the smallest falsifiable replication or sensitivity analysis. Record source, release, cohort, mask, model, results, and hashes with `$science-provenance`; run `$science-review` before synthesis.

## Boundaries
Do not compare differently defined masks or phenotypes as exact replication. A significant burden result is not proof that a gene causes disease or identifies a causal variant. Do not interpret missing p-values as nonsignificance or mix discovery and replication evidence. Stop when source terms, endpoint, phenotype, or mask cannot be verified; retain unresolved evidence as inconclusive or unavailable.
