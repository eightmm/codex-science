---
name: proteomexchange-search
description: "Resolve a known PXD accession through ProteomeXchange. Use for cross-repository accession verification and proteomics reanalysis planning; use PRIDE for keyword discovery."
license: MIT
---

# ProteomeXchange Search

## Decision contract
Role: retriever. Start from a PXD accession supplied by a paper, PRIDE search, or dataset record; this skill verifies a known accession and does not replace keyword discovery. State the metadata question, evidence cutoff, and required repository or file checks. Preserve the accession exactly as supplied and do not normalize it into a different repository's identifier.

## Workflow
1. Call `science_search_proteomexchange` with the accession as the query and optional `limit` (legacy source tools accept `limit` from 1 to 10). The connector contract identifies this source as accession-based. For structured retrieval, inspect `science_list_source_contracts` before using `science_query_source_v2` or `science_query_source_v3`; pass only verified source parameters and record page size, page cap, evidence cutoff, and completeness.
2. Verify the accession, hosting repository, species, instrument, publication status, keywords, and availability at the repository of record. Prefer PRIDE-specific metadata when the dataset is hosted by PRIDE; keep repository-specific identifiers intact. Record release/update metadata reported by each response and access time rather than inferring a release.
3. Compare the returned registration with the cited paper and repository record. Preserve exact queries, pages, returned and excluded records, and exclusion reasons. Validate response shape, accession identity, and truncation. Distinguish a valid registration from an accessible project, downloadable files, published analysis, and identification quality.
4. Use bounded retries for transient errors, then report the source as unavailable with the attempted query and failure state. Do not silently substitute another accession or treat a failed request as evidence of absence. Review citation and data terms before reanalysis or redistribution.

## Outputs
Return the normalized query and exact PXD accession; a verification table containing source, hosting repository, repository accession, species, instrument, publication status, keywords, availability, release/access time, and query reference; records returned and excluded with reasons; claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; source dependencies, uncertainty, and unresolved metadata; and the smallest falsifiable follow-up. Record file manifests, repository checks, queries, and hashes with `$science-provenance`. Use `$science-review` before dataset-selection or reanalysis claims.

## Boundaries
Do not infer completeness, data accessibility, identification quality, or biological support from ProteomeXchange registration alone. A PXD record is not independent evidence from the corresponding PRIDE or repository record. Stop when the accession cannot be resolved or repository terms prevent traceable use; distinguish missing fields from null values and inaccessible records.

Source basis: [ProteomeXchange API](https://proteomecentral.proteomexchange.org/cgi/GetDataset); [ProteomeCentral service documentation](https://proteomecentral.proteomexchange.org/doc/serviceDocs.php).
