# RNAcentral identity and evidence

## Claim semantics

Separate (1) URS sequence-record identity; (2) species-specific occurrence; (3) source/member-database accession mapping; (4) annotation or predicted RNA type/function; (5) sequence-based similarity/identity; and (6) experimentally demonstrated function. A URS supports claims about the represented sequence record when the sequence resolves and matches the stated version. A cross-reference supports the existence of a mapping in the selected release. Annotation supports what the contributing resource reports. Experimental function needs a suitable functional assay or primary evidence beyond an integrated database record.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable`. Absence of a cross-reference is not evidence that a sequence/function is absent. Keep database record status distinct from biological claim status.

## URS, source accessions, and dependencies

RNAcentral URS identifiers represent distinct ncRNA sequences; a taxonomy suffix identifies a species-specific occurrence. Preserve the source/member-database accession separately. The same sequence can have cross-references from several expert databases, while one source accession may map ambiguously or change with releases. Do not merge records based only on display name or annotation label.

RNAcentral aggregates sequences and annotations from expert databases. These sources can share underlying submissions, literature, sequence records, or propagated annotation. Record each member database and accession, release/date where reported, and the exact mapping. Multiple cross-references are not independent confirmation unless their evidence lineage is independent.

## Sequence and annotation evidence

Sequence-based evidence includes exact sequence resolution, sequence version, alphabet, length, organism mapping, and any alignment/similarity method used downstream. Record algorithm and parameters for sequence comparison; similarity alone does not prove equivalent function. Annotation-based evidence names the expert database, accession, annotation text/type, status and source version. Report conflict or disagreement rather than aggregating labels into an unsupported consensus.

Carry uncertainty in version, taxonomy assignment, sequence completeness, ambiguous symbols, accession mapping, inactivity/deprecation, member-database coverage, and disagreement. Keep missing sequence, no match, filtered record, inactive record and API failure separate.

## Controls and sensitivity

Use a known URS and member-database accession as a positive control and a syntactically valid nonexistent accession as a negative control. Confirm the expected sequence/organism mapping and explicit no-match behavior. Pin RNAcentral release/access time and member database versions when present.

Vary release and expert-database selection; when sequence-based analysis is performed, vary defensible alignment thresholds or database subsets. Mark a claim fragile if URS mapping, organism, annotation status, or claim status changes across plausible settings. Record all alternatives and unavailable versions.

## Applicability and failure modes

RNAcentral provides integrated ncRNA sequence access; coverage and annotation depend on contributing resources and releases. It does not assure that every transcript, isoform, organism, or functional effect is represented. A stable identifier is not a guarantee of stable annotation or function.

- Description-based false match: detect by comparing sequence, organism/taxonomy, and source accession.
- URS/source accession conflation: detect by validating identifier type and preserving both identifiers.
- Cross-reference treated as independent evidence: trace member databases and shared upstream provenance.
- Annotation disagreement hidden: report each source label/version and preserve conflicts.
- Sequence version drift or truncation: validate length, alphabet, hash/version and complete response before use.
- Function inferred from similarity or annotation alone: identify whether evidence is sequence-based, database annotation, or a direct experiment.

## Sources

- RNAcentral Consortium, “RNAcentral 2021: secondary database for non-coding RNA sequences,” 2021: integrated sequence resource and contributing expert databases.
- RNAcentral FAQ and linking documentation, EMBL-EBI: URS identifiers, taxonomy-specific forms, and external accession mappings.
- The RNAcentral Consortium, “RNAcentral: an international database of ncRNA sequences,” 2015: URS design and cross-reference tracking.
