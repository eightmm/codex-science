---
name: ncbi-gene-search
description: "Resolve human genes through NCBI Entrez Gene and preserve links to sequence, literature, variation, and GEO resources. Use for NCBI-centered gene and identifier research."
license: MIT
---

# NCBI Gene Search

## Decision contract
Record the supplied symbol, synonym or stable identifier, requested species, intended downstream link types, and evidence cutoff. Treat symbols as potentially ambiguous; the selected record must match both species and gene identity. Use Entrez Gene ID as the NCBI record key and preserve alternate identifiers as returned.

## Workflow
1. Call `science_search_ncbi_gene` with a canonical symbol, synonym, or stable identifier. The legacy MCP interface accepts required `query` and optional `limit` from 1 to 10 (default 5); if it is unavailable, use NCBI E-utilities directly and preserve the exact request.
2. Confirm species and Entrez Gene ID; cross-check MyGene and Ensembl for ambiguous symbols. Retain rejected candidate IDs and why they do not match.
3. Follow links only for the evidence required: sequence, PubMed/PMC, ClinVar/dbSNP, GEO, or conserved domains. Follow explicit database links, bound result sets, and retain the link relation rather than treating all linked records as equivalent evidence.
4. Record database, query, IDs, release/access date, endpoint or tool, link path, returned/excluded counts and reasons, and a response artifact/hash with `$science-provenance`. Respect NCBI rate and usage policies. Capture release or last-updated metadata when reported; bound retries to transient failures and do not treat truncation, omitted fields, explicit null, no match, and service failure as the same outcome.

The optional `science_query_source_v2` route uses `source="ncbi_gene"` and top-level `parameters`, with optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. Check `science_list_source_contracts` before supplying source-specific parameters. A search hit establishes an identifier mapping only; use primary source records for evidence. Check material conclusions with `$science-review`.

## Outputs
Return normalized query, species, selected Entrez ID and cross-references, rejected alternatives, linked record IDs and relation, source/version and retrieval metadata, and an inclusion/exclusion table. Assign claim IDs and statuses (supported, contradicted, inconclusive, unavailable) to conclusions; state uncertainty, missing data, limitations, and the smallest resolving lookup.

## Boundaries
Do not treat Gene summaries or linked records as primary experimental evidence. Respect NCBI rate and usage policies. A linked PMID, sequence, or variation record is not itself evidence that a gene causes a phenotype. Stop if species or gene identity remains ambiguous.

Source basis: [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/).
