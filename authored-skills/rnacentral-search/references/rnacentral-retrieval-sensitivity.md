# RNAcentral retrieval and sensitivity

## Retrieval contract

The `science_search_rnacentral` connector accepts `query` and optional `limit` for description search. Use the RNAcentral API for accession, sequence, status and cross-reference details not returned by the search. Preserve exact serialized query, endpoint, access time, reported release/update, page coverage, returned count and artifact hash. Use only a direct endpoint that resolves the same RNA record.

Classify the question as sequence identity, organism occurrence, source-accession mapping, annotation, sequence similarity, or experimental function. A retrieval can support a database-level claim only. Use statuses `supported`, `contradicted`, `inconclusive`, or `unavailable` consistently.

## Validation and controls

Validate URS syntax and resolution, member-database accession, organism/taxonomy, active status, sequence alphabet, length, strand, and sequence version where supplied. Check pagination/truncation and preserve null fields. Record selected and excluded records with reasons. A missing sequence, no match, deprecated/inactive record, explicit filter, and API failure are distinct outcomes. Retry transient errors a bounded number of times.

Use a known URS/accession pair as a positive control, checking the expected sequence and taxon. Use a well-formed nonexistent accession as a negative control and confirm explicit no-match. Record control query and result; if either control fails, stop claim interpretation and diagnose retrieval.

## Dependencies and version pinning

Record RNAcentral release/access time and member-database accession, release/date and evidence type when available. Preserve URS and species-specific identifier separately from source accession and sequence version. Trace linked records for shared submissions or propagated annotation. Do not treat a set of expert-database links as independent observations by default.

## Sensitivity analysis

Vary RNAcentral release and relevant expert-database selection. For downstream sequence comparisons, test reasonable alignment thresholds and source-database inclusion choices. Keep species and sequence version fixed unless they are the intended variable. A conclusion is fragile when sequence mapping, organism assignment, annotation agreement, status or claim outcome changes. If versions/settings are inaccessible, report the analysis as untested.

## Applicability and failure detection

Results apply to records and annotations included in the selected RNAcentral/member releases. Integrated database coverage is incomplete by design and cannot establish biological function. Stop when sequence identity, organism, version, accession mapping, or response completeness cannot be resolved.

- Wrong URS or source accession: validate each identifier against its namespace and returned record.
- Species ambiguity: inspect taxon-specific identifier and organism field; do not assume identical sequence means same occurrence.
- Stale/deprecated mapping: compare active status and source release, retain old accession as provenance.
- Truncation or partial result set: validate page coverage, returned counts and sequence length/hash.
- API failure mistaken for absence: inspect status/error and preserve `unavailable` rather than a negative claim.
- Member database disagreement: retain each source/version and classify the functional interpretation as inconclusive when unresolved.

## Sources

- RNAcentral API documentation, EMBL-EBI: current retrieval routes and response detail.
- RNAcentral FAQ and linking documentation, EMBL-EBI: URS stability, taxonomic identifiers, and external accessions.
- RNAcentral Consortium, 2021, “RNAcentral 2021: secondary database for non-coding RNA sequences”: release and integrated-resource context.
