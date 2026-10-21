---
name: ncbi-integrated-research
description: "Run bounded NCBI-centered research across Gene, PubMed/PMC, sequence, variation, and GEO-linked records. Use when a gene, accession, sequence, or literature question requires traceable NCBI cross-links."
license: MIT
---

# NCBI Integrated Research

## Decision contract
Before retrieval, state the question, target gene/accession/sequence, species and taxon, evidence cutoff, permitted inference, and which NCBI record types are necessary. Create claim IDs for material conclusions and define which primary records could support or contradict them. Select lanes only as needed; linked records do not become independent evidence simply because they are separate databases.

## Workflow
1. Resolve the canonical human gene with `science_search_ncbi_gene`; preserve species and Entrez ID. Its legacy MCP arguments are `query` (required) and `limit` (1–10, default 5). Cross-check ambiguous mappings rather than guessing.
2. Select only required lanes: PubMed literature, PMC open text, sequence/Datasets, ClinVar/dbSNP variation, or GEO metadata. Use direct NCBI database links rather than repeating broad free-text searches. Bound each result set and respect NCBI rate policy.
3. For available MCP operations, use only registered tool names and schemas. `science_query_source_v2` takes `source`, `parameters`, and optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`; check `science_list_source_contracts` before setting source-specific parameters. Public API access remains available where a repository connector is absent.
4. Preserve database, endpoint/tool, exact query, IDs, link relation, release/access time, result count, exclusions and reasons, and raw artifact path/hash. Record reported release/update information; distinguish metadata, abstract, full text, sequence record, and curated assertion. Validate that linked records match the requested entity and detect truncated responses, missing fields, nulls, and unavailable services separately.
5. Render PMIDs and DOIs as links; reconcile evidence with primary publications and `$science-review` before conclusions. Use bounded transient retries only; never infer negative evidence from retrieval failure or an empty partial response.

Store cross-database link paths and identifiers with `$science-provenance` before review. Do not download large sequence or GEO payloads without a declared file and compute plan.

## Outputs
Return normalized input, gene/species/Entrez ID, selected lanes, link-path table, records included and excluded with reasons, evidence artifact/hash references, and claim register with supported/contradicted/inconclusive/unavailable status. Include uncertainty, dependency deduplication, limitations, and the smallest falsifiable next action.

## Boundaries
Do not treat NCBI summaries as clinical guidance. Do not count cross-linked copies or multiple records derived from one study as independent confirmation. Preserve unavailable and null results as distinct from biological negatives. Stop if essential gene identity, source record, or required primary text cannot be resolved; do not download large sequence or GEO payloads without a declared file and compute plan.
