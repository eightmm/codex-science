# MGnify retrieval and sensitivity

## Retrieval scope and evidence classes

The bundled `science_search_mgnify` connector accepts `query` and optional `limit` and is intended for study discovery. Use the public MGnify API for sample-, analysis-, assembly-, or file-level details not returned by that connector. Retain serialized query, endpoint/tool, filters, access time, reported release/update, returned count, pagination state, and artifact hashes.

Distinguish these claim classes: (1) accession resolution, based on a record returned by the pinned source; (2) metadata, limited to fields explicitly present; (3) pipeline profile, limited to the result and version; (4) cross-study comparison, requiring harmonized units and study structure; (5) biological interpretation, requiring evidence outside a portal profile. Assign `supported`, `contradicted`, `inconclusive`, or `unavailable` consistently.

## Validation and controls

Validate identifier syntax and returned record level before accepting a result. Check response status, schema, counts, pagination completeness, and whether profile files correspond to the requested analysis. Preserve nulls. List selected and excluded records with reasons. Retry only transient failures a bounded number of times, obey service throttling, and do not replace failed structured retrieval with generic web search.

For each retrieval batch, query a known accession and verify the expected study/sample/analysis level. Also issue a validly formed negative query and verify that the endpoint reports no match rather than an API error. Record both controls and their exact outputs. A control mismatch means stop and diagnose query or endpoint behavior before biological interpretation.

## Dependencies and version pinning

Record study accession, sample accession, run/analysis accession, input type, pipeline version, and reference database version where available. Link analyses back to their input records. Shared study, cohort, sample, assembly, or run means evidence is dependent; multiple files or annotation rows from one analysis do not increase biological replication. Preserve release/update dates and do not silently combine versions.

An accession that resolves successfully establishes retrievability for that identifier and release. It does not establish that all eligible samples were deposited or that metadata fields are complete. Preserve the query boundary when reporting counts.

## Sensitivity analysis

When feasible, rerun or compare the same input across available pipeline versions. Recompute eligible sets under defensible taxonomy filters, host/biome filters, and reference database selections. Keep all settings fixed except the one varied. Mark the claim fragile when membership, taxonomic assignment, functional profile, status, or comparison direction changes materially. If pipeline version or underlying records are unavailable, report sensitivity as untested rather than stable.

## Applicability and failure detection

API retrieval covers deposited public records and reported annotations; it does not guarantee complete metadata, uniform protocols, complete environmental sampling, or experimental validation. Stop if response pagination is incomplete, record levels are mixed, accessions do not resolve, release/version is ambiguous for a version-sensitive claim, or measurement units cannot be aligned.

- Wrong record level: detect by verifying accession prefix/type and parent links.
- Truncated or partial response: detect through pagination, counts, and file completeness checks.
- Transient outage or throttling: detect via HTTP/API error; retain `unavailable`, retry boundedly, never infer absence.
- Silent filter exclusion: compare query filters and returned/excluded counts; record exclusion reasons.
- Version drift: compare reported pipeline and reference versions; do not attribute version-dependent changes to biology without a controlled comparison.

## Sources

- MGnify API documentation, EMBL-EBI, current documentation: access paths and response resources; consult for endpoint-specific retrieval details.
- Mitchell et al., 2020, “MGnify: the microbiome analysis resource in 2020”: analysis types and pipeline evolution.
- MGnify release and pipeline-version documentation (EMBL-EBI): consult the notes for the exact pipeline version that produced the analysis being interpreted.
