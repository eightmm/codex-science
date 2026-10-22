---
name: ncbi-integrated-research
description: "Run bounded NCBI-centered research across Gene, PubMed/PMC, sequence, variation, and GEO-linked records. Use when a gene, accession, sequence, or literature question requires traceable NCBI cross-links."
license: MIT
---

# NCBI Integrated Research

## Decision contract
Before retrieval, state the question, target gene/accession/sequence, species and taxon, evidence cutoff, permitted inference, and which NCBI record types are necessary. Create claim IDs for material conclusions and define which primary records could support or contradict them. Select lanes only as needed; linked records do not become independent evidence simply because they are separate databases.

## Reference usage

Read [ncbi-evidence-method.md](references/ncbi-evidence-method.md) before claim registration, cross-database synthesis, or interpreting cross-study evidence.

## Workflow

1. **Gates (ask before proceeding).** Confirm target identity/species, record types needed, permitted inference, evidence cutoff, and whether any requested access/download exceeds bounded read-only retrieval; stop and ask before large payloads or credentialed access. Record decision and scope.
2. Freeze the question, target gene/accession/sequence, taxon, cutoff, claim IDs, permitted inference, and primary records that could support or contradict each claim; record unresolved identity alternatives.
3. Resolve the canonical human gene with `science_search_ncbi_gene`; preserve species and Entrez ID. Its legacy MCP arguments are `query` (required) and `limit` (1–10, default 5). Cross-check ambiguous mappings rather than guessing.
4. Select only necessary lanes: PubMed, PMC, sequence/Datasets, ClinVar/dbSNP, or GEO metadata. Use direct NCBI links rather than repeated broad searches; bound each result set and respect NCBI rate policy. Record lane rationale and bounded scope.
5. For available MCP operations, use only registered tool names and schemas. `science_query_source_v2` takes `source`, `parameters`, and optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`; check `science_list_source_contracts` before setting source-specific parameters. Public API access remains available where a repository connector is absent. Preserve database, endpoint/tool, exact query, IDs, link relation, release/access time, result count, exclusions and reasons, and raw artifact path/hash; distinguish metadata, abstract, full text, sequence record, and curated assertion.
6. Validate that linked records match the requested entity; detect truncated responses, missing fields, nulls, and unavailable services separately. Use bounded transient retries only; never infer negative evidence from retrieval failure or an empty partial response. Record reported release/update information and preserve response shape.
7. Classify record identity, literature, sequence/property, variation, study metadata, association, and clinical-adjacent claims separately. Check known link-path sanity, primary article support, sample/study dependencies, query-cap sensitivity, accession/version and lane sensitivity; record uncertainty and fragile conclusions.
8. Verify claim status (`supported`, `contradicted`, `inconclusive`, `unavailable`), link-path table, dependency graph, exclusions, uncertainty, limitations, and applicability against the contract; render PMIDs and DOIs as links, reconcile evidence with primary publications and `$science-review` before conclusions, preserve unavailable/null states, and store cross-database link paths and identifiers with `$science-provenance` before review. Do not download large sequence or GEO payloads without a declared file and compute plan.

## Outputs

Return normalized input, gene/species/Entrez ID, selected lanes, link-path table, included/excluded records with reasons, evidence artifact/hash references, dependency graph, uncertainty, limitations, next falsifiable action, and claim register statuses. Schema `ncbi-evidence-reconciliation-v1` requires `schema_id`, `contract`, `entities`, `selected_lanes`, `link_paths`, `records`, `claims`, `dependencies`, `uncertainty`, `controls`, `sensitivity`, `exclusions`, `limitations`, and `provenance`. Store link paths with `$science-provenance`; use `$science-review` before conclusions.

## Boundaries
Do not treat NCBI summaries as clinical guidance. Do not count cross-linked copies or multiple records derived from one study as independent confirmation. Preserve unavailable and null results as distinct from biological negatives. Stop if essential gene identity, source record, or required primary text cannot be resolved; do not download large sequence or GEO payloads without a declared file and compute plan.
