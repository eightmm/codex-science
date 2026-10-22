---
name: ncbi-gene-search
description: "Resolve human genes through NCBI Entrez Gene and preserve links to sequence, literature, variation, and GEO resources. Use for NCBI-centered gene and identifier research."
license: MIT
---

# NCBI Gene Search

## Decision contract

Record the supplied symbol, synonym or stable identifier, requested species, intended downstream link types, and evidence cutoff. Treat symbols as potentially ambiguous; the selected record must match both species and gene identity. Use Entrez Gene ID as the NCBI record key and preserve alternate identifiers as returned. Distinguish an NCBI Gene annotation record from experimental evidence of gene function.

## Reference usage

Read [NCBI gene identity and annotation evidence](references/gene-identity-evidence.md) before resolving an identifier, following Gene links, interpreting orthology, comparing sources, or assigning a claim class. It defines identifier and release checks, dependencies, controls, uncertainty, sensitivity, and source limits; the reference itself is not evidence for a target-gene claim.

## Workflow

1. Classify the request as identifier resolution, gene annotation, or a specific linked-record lookup; require species and the downstream evidence need before searching. Record the requested claim and unresolved inputs; stop if species cannot be established.
2. Call `science_search_ncbi_gene` with a canonical symbol, synonym, or stable identifier. The legacy MCP interface accepts required `query` and optional `limit` from 1 to 10 (default 5); if it is unavailable, use NCBI E-utilities directly and preserve the exact request. Select a route only when its operation matches the request; record endpoint/tool, query, and access time.
3. Confirm species and Entrez Gene ID and compare symbol, aliases, object type, and alternate IDs. Cross-check MyGene and Ensembl for ambiguous symbols; retain rejected candidate IDs and why they do not match. Select a record only when species and gene identity agree; record candidates and identity evidence.
4. Pin the genome assembly and annotation/release metadata reported by NCBI, and preserve transcript accession versions when used. For human transcript comparisons, state the RefSeq/MANE choice if available and verified; do not infer a transcript equivalence from gene-level mapping. Record exact version fields and what was not reported.
5. Classify results as database annotation/identifier mapping, linked record, or experimental evidence located in a cited primary study. A search hit, summary, orthology label, or linked record alone does not establish experimental function. Report orthology evidence type and relationship when available, including one-to-many mappings; record source dependencies and claim class.
6. Follow links only for the evidence required: sequence, PubMed/PMC, ClinVar/dbSNP, GEO, or conserved domains. Follow explicit database links, bound result sets, and retain the link relation rather than treating all linked records as equivalent evidence. Record linked identifiers, relation, counts, and exclusions; treat aggregator-propagated records as dependent rather than independent confirmation.
7. Use a known gene with a stable Entrez Gene ID as a positive control and an ambiguous alias as an ambiguity control; verify expected species and record identity and that the alias is not silently treated as unique. If a control fails, resolve query behavior before interpreting the target. Record control outcomes and deviations.
8. Vary species and synonym handling, and vary assembly/release or transcript selection when material. Treat the mapping as fragile if candidate identity, transcript, coordinates, or linked evidence changes in a way that affects the downstream conclusion. Record each variant and its effect.
9. Record database, query, IDs, release/access date, endpoint or tool, link path, returned/excluded counts and reasons, and a response artifact/hash with `$science-provenance`. Respect NCBI rate and usage policies. Capture release or last-updated metadata when reported; bound retries to transient failures and distinguish truncation, omitted fields, explicit null, no match, and service failure. Assign claim IDs and statuses (supported, contradicted, inconclusive, unavailable), state uncertainty/limits and the smallest resolving lookup, and check material conclusions with `$science-review`. Verify identity, evidence class, controls and provenance before returning.

The optional `science_query_source_v2` route uses `source="ncbi_gene"` and top-level `parameters`, with optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. Check `science_list_source_contracts` before supplying source-specific parameters. A search hit establishes an identifier mapping only; use primary source records for evidence.

## Outputs

Return one `ncbi-gene-evidence-v1` object with these required fields:

- Claim identifier (`claim_id`), claim status (`claim_status`: supported, contradicted, inconclusive, or unavailable), and claim class (`claim_class`).
- Normalized query (`normalized_query`), species/taxon (`species_taxon`), selected Entrez Gene ID (`entrez_gene_id`), alternate identifiers (`alternate_ids`), and rejected alternatives with reasons (`rejected_alternatives`).
- Genome assembly (`assembly`), NCBI release/update metadata (`source_release`), and transcript accession/version and RefSeq/MANE basis when relevant (`transcript_selection`).
- Linked record IDs and link relation (`linked_records`).
- Exact request, endpoint/tool, and access time (`query`, `endpoint_or_tool`, `access_time`).
- Returned/excluded counts and inclusion/exclusion table (`returned_count`, `excluded_count`, `inclusion_exclusion`).
- Source dependency and independence notes (`source_dependencies`), positive and ambiguity control results (`controls`), uncertainty (`uncertainty`), and sensitivity results (`sensitivity`).
- Applicability limitation (`applicability_limit`), response artifact/hash (`response_artifact`), and smallest resolving lookup (`next_lookup`).

## Boundaries

Do not treat Gene summaries or linked records as primary experimental evidence. Respect NCBI rate and usage policies. A linked PMID, sequence, or variation record is not itself evidence that a gene causes a phenotype. Orthology or a cross-reference is an annotation relationship, not proof of functional equivalence. Stop if species or gene identity remains ambiguous, or if an empty result has not been distinguished from service failure.

Source basis: [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/).
