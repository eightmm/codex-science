---
name: public-omics-dataset-discovery
description: "Discover and triage reusable public transcriptomics, proteomics, metabolomics, microbiome, and supplementary-study datasets. Use when a research question needs external data rather than only literature."
license: MIT
---

# Public Omics Dataset Discovery

## Decision contract
Define organism, tissue or cell state, disease or perturbation, assay, sample unit, comparator, minimum metadata, reuse terms, raw-versus-processed need, storage and compute budget, and a validation analysis before searching.

## Reference usage
Read [dataset-evidence-and-reuse.md](references/dataset-evidence-and-reuse.md) before ranking candidates, resolving cross-listed accessions, interpreting missing metadata or controls, or proposing transfer. It defines evidence classes, cohort dependencies, uncertainty, sensitivity checks, and the reuse boundary.

## Workflow
1. Freeze the scientific question, estimand, organism, tissue/state, assay, sample unit, comparator, and acceptance criteria; record any ambiguity that would change eligibility.
2. Select repositories whose scope and access model match the assay and reuse need; record repository name, query, release or access date, and why each source is relevant.
3. Search with explicit terms and inclusion/exclusion rules; retain exact accession, record version, query result identity, and exclusion reason for every screened candidate.
4. Resolve cross-listed records to underlying study, cohort, donor, and sample identities; merge duplicates and record shared or propagated records before counting evidence.
5. Inspect design, controls, metadata, assay/platform, batch structure, raw and processed assets, checksums, size, publication, and terms; check leakage, pseudoreplication, donor overlap, confounding, missing controls, file accessibility, harmonization burden, and whether the study can identify the requested estimand. Record facts separately from inferred fitness and retain each bias or harmonization risk.
6. Assign each candidate a claim class and fitness against the prespecified estimand; record support, counterevidence, uncertainty, applicability, and a falsifier for any material claim.
7. Test sensitivity to inclusion rules, alternate accessions/releases, sample-unit definitions, missingness, batch/confounder assumptions, and raw-versus-processed choice; record rank changes and fragility.
8. Rank eligible candidates and retain rejected near matches; verify that controls, metadata, licensing, access, and budget satisfy the decision contract, or stop with a named gap.
9. Record the smallest smoke analysis that could invalidate selection and exact bounded transfer plan; do not transfer large or controlled data before approval.
10. Emit `omics-dataset-selection-v1`, preserve the full ledger and source snapshots with `$science-provenance`, and use `$science-review` before final selection.

## Outputs
Emit one `omics-dataset-selection-v1` record with required fields: `question`, `estimand`, `searches`, `candidates`, `ranked_dataset_ids`, `rejected_near_matches`, `dependency_groups`, `claim_evidence`, `harmonization_and_bias_risks`, `sensitivity`, exact download plan (`exact_download_plan`), `expected_cost`, `smoke_analysis`, `limitations`, and `provenance`.

## Boundaries
Repository presence, citation count, or query rank is not evidence of quality or permission; do not download large or controlled data before approval, never silently substitute samples or endpoints, record the full candidate ledger and snapshots with `$science-provenance`, and run `$science-review` before final selection. Public availability does not establish consent for every reuse, independent replication, or suitability for the target estimand.
