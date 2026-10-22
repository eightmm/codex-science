# BioStudies archive record interpretation

## Claim semantics

An **archive-retrieval claim** states that a query returned an accession record within a named search scope, release/update state, and access time. An **archive-identity claim** states that the accession page identifies a particular archive record and type. A **file-availability claim** states that a particular file or link appears in the retrieved manifest and is accessible under the observed access conditions; it does not say that the file is complete, valid, scientifically useful, or reusable. A **metadata claim** reports what the record says and who supplied or curated it where known. A **study-result claim** must be supported by the study's methods and data, not by archive presence or submitter description. A **reuse-permission claim** requires license/terms applicable to the actual files and intended use; public visibility alone is insufficient.

BioStudies records can describe studies, link data held in other databases, and hold data files that do not fit a structured archive, including supplementary material. Classify accession prefixes as source/collection clues, not evidence of assay type or quality. For example, current BioStudies help describes `S-BSST` for records submitted through its Submission Tool, `S-EPMC` for Europe PMC imports, and `E-MTAB` for the ArrayExpress collection; confirm the record's actual collection and details instead of relying on the prefix alone. Classify each manifest item as a BioStudies-hosted file, external database link, publication link, or submitter-provided metadata. Do not assume that a paper-like record contains primary data or that an external link is still live. Report exact accession and file identifiers returned.

## Source dependencies and release

A record may repeat or aggregate information from the associated publication, an external archive, a project collection, or submitter text. Preserve the BioStudies accession, record/update timestamp or release if reported, linked accession identifiers, publication identifiers, query, API endpoint/tool, access time, response hash, and manifest completeness. Record `unknown` when a version or contributor is not stated. Do not infer record provenance from filenames or treat linked representations as independent studies.

When multiple records link to the same publication, sample set, project, or external accession, flag the shared source and avoid counting each record as independent evidence. A BioStudies description may summarize rather than reproduce the source dataset; downstream analysis should cite and inspect the primary data location and the source's own metadata. An accession can be valid while individual files are withdrawn, private, inaccessible, or superseded.

## Uncertainty, metadata quality, and controls

Track uncertainty by field: organism, assay, sample design, data level, file identity, checksum/size, license, record status, submission source, linked-resource reachability, and page completeness. Mark whether a field is absent, null, ambiguous, conflicting, submitter-provided, externally linked, or independently checked. Do not convert unstructured metadata into a precise value without documenting the normalization and evidence. A missing license is not permission; a visible file listing is not verified file integrity.

Use a known accession from the relevant archive class as a positive retrieval control and a deliberately unrelated query/accession as a negative control. Check the expected accession format, page response, record type, and whether files are hosted or linked. Controls test query and endpoint behavior, not study quality. If the positive control is missing or the negative query returns the target record, inspect query breadth, accession normalization, pagination, and filters. Confirm one manifest entry against its record page or API details when availability matters.

## Sensitivity and fragility

Rerun with exact accession lookup versus text search; constrained versus broad organism/study-type filters; linked external records included versus BioStudies-hosted files only; and a stated evidence cutoff versus the latest reported update. Compare the recommended accession, record classification, visible files, and metadata interpretation. Record each query and page count. Mark discovery **fragile** if a reasonable filter changes the recommended record, archive type, apparent file availability, or whether required organism/assay metadata exists. A robust retrieval remains an archive finding, not a scientific validation.

## Applicability domain and failure detection

BioStudies is a study-description and data-dissemination resource, not a uniform structured assay database. Record schemas and metadata completeness vary across submissions and linked repositories. It is suitable for discovering records and inventorying links/files; it is not by itself a quality appraisal, reproducibility assessment, or reuse authorization. Specialized repositories may be authoritative for file semantics and experimental metadata. Private records may be invisible; public records may have incomplete or stale links.

- **Archive presence promoted to validation:** inspect methods/data separately; state that accession presence only establishes a record.
- **Submitter metadata treated as independently verified:** identify the metadata source and validate critical organism/assay/sample fields against linked primary records.
- **External link mistaken for hosted file:** classify every manifest item and test link reachability only when needed; preserve inaccessible status.
- **Filename used to infer results:** inspect file metadata/content under an approved workflow; do not infer assay outcomes from names.
- **License or reuse permission assumed:** inspect the record and source terms for each relevant file; mark missing or ambiguous terms unresolved.
- **Partial manifest reported as complete:** inspect result pagination, file counts, truncation, and access limits; label incomplete manifests explicitly.
- **Silent empty search or transient outage:** validate status, response shape, result count, and positive control; distinguish successful no-match from `unavailable` service.
- **Duplicate studies counted independently:** compare publication, project, sample, and external accession links; record shared lineage.

## Accession and manifest audit

Treat an accession prefix as a routing clue. Current BioStudies help gives examples such as `S-BSST` for BioStudies Submission Tool submissions, `S-EPMC` for Europe PMC imports, and `E-MTAB` for the ArrayExpress collection. Prefixes are not a universal quality code; inspect the returned collection, record page, and linked resource because collections and archive integrations can evolve.

For each candidate accession, record:

- Exact accession and collection/archive type returned by the service.
- Record title and description as supplied, with missing or conflicting values retained.
- Organism, assay, study type, release date, and public/access-controlled state only when explicitly reported.
- Publication identifiers and external accessions as links, not as contents verified by BioStudies.
- Each file path or URL, whether hosted in BioStudies or external, reported size/type, and any available checksum or annotations.
- License/terms attached to the record or file and whether they cover the intended use.
- Pagination/truncation state and whether all reported manifest entries were inspected.

An accession-level summary is incomplete when a required file list is paginated, inaccessible, or truncated. Preserve the partial list and state what was not inspected. Do not infer checksum, file integrity, or content from a reported size or filename. If checking a file requires download, apply the workflow's approval gate and record the approval scope before retrieval.

## Metadata quality and evidence lane

Describe metadata quality field by field rather than giving an ungrounded overall score. Useful labels are `present-and-consistent`, `present-but-unverified`, `missing`, `ambiguous`, `conflicting`, and `not-applicable`. Apply them to organism, assay, sample design, data type, publication link, file identity, and license. Explain any normalization from free text to a controlled term and preserve the original value.

Keep three evidence lanes separate:

1. **Archive lane:** what accession, record, and files the archive reports.
2. **Publication lane:** what linked article or external repository reports after it is independently retrieved.
3. **Analysis lane:** what a reproducible inspection of the data supports.

An archive result may support the first lane only. The publication link does not transfer its conclusions into the archive claim, and the file listing does not establish that an analysis was performed. Refer study interpretation to `$science-review` with the actual paper/data evidence and preserve the archive record as provenance.

When a candidate is intended for later analysis, make the handoff actionable without implying admission or quality:

- Identify the accession and exact file/link set to inspect.
- State which required metadata fields are present, missing, or conflicting.
- Record any access restriction, license uncertainty, and unapproved download requirement.
- Name the independent source that must be checked for experimental design or results.
- State whether the search covered all result pages and whether the manifest was complete.
- Retain rejected alternatives and the query/filter reason for rejection.

This handoff lets a later workflow decide whether to retrieve or analyze the data under its own approval and provenance contract. It does not make BioStudies discovery an endorsement of the dataset.

## Sources

- McEntyre, Sarkans, and Brazma, “The BioStudies database” (2015), for the study-centric record and data-dissemination model.
- Sarkans et al., “The BioStudies database—one stop shop for all data supporting a life sciences study,” *Nucleic Acids Research* (2018), for linked and supplementary data use; it does not certify submitter metadata or study validity.
- EMBL-EBI BioStudies REST API and help documentation (living primary documentation; record access date, accession, and reported update state).
