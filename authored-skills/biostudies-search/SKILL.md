---
name: biostudies-search
description: "Discover public life-science studies and associated archive records through EMBL-EBI BioStudies. Use for ArrayExpress, supplementary-data, accession, and public dataset discovery; not as evidence of study quality or reuse permission."
license: MIT
---

# BioStudies Search

## Decision contract

Define the biological question, organism, assay/study type, desired data level, access constraints, and evidence cutoff. Normalize accession and organism identifiers where possible. Distinguish archive discovery from scientific evaluation and from permission to reuse data. Classify a record by its accession/archive type and distinguish submitter-provided metadata, links to external resources, and files actually hosted in BioStudies.

## Reference usage

Read [archive-records-and-discovery-evidence.md](references/archive-records-and-discovery-evidence.md) before recommending an accession, interpreting its files or metadata, comparing records, or claiming dataset availability. It defines accession and file semantics, record dependencies, controls, sensitivity, and reuse boundaries.

## Workflow

1. Define the biological question, organism, assay/study type, desired data level, access constraints, and evidence cutoff; record the discovery contract and what would count as a useful archive record.
2. Call `science_search_biostudies` with a bounded biological query and optional `limit`; retain exact query, parameters, tool, access time, result count, page coverage, and response hash.
3. Filter by accession, study type, organism, assay, release date, and public availability before recommending a dataset; record each included or excluded record with the reason and keep missing/null metadata distinct from explicit filter failures.
4. Follow accession pages to verify the accession/archive type, record status, linked files, linked publications, licenses, and download size; use the BioStudies REST API directly for accession details and file manifests. Ask before large downloads and stop until approved.
5. Validate accession and response shape, expected fields, truncation, and source release/update timestamp. Distinguish submitter-provided descriptions from independently curated metadata and external linked records; do not silently substitute an unstructured web search if search fails.
6. Check one known accession as a positive control and a deliberately unrelated query as a negative control; verify accession shape, expected record, and result scope. Preserve bounded transient retries, throttling behavior, and `unavailable` when search fails.
7. Vary organism/study-type filters, exact accession versus text query, linked-record inclusion, and release cutoff; if a recommendation, file availability, or metadata interpretation changes materially, mark it fragile and record the alternatives.
8. Return an archive-discovery claim only, with file-level availability, completeness, metadata quality, license, and uncertainty stated separately; save query, manifest, exclusions, and hashes via `$science-provenance`, and use `$science-review` before interpreting study findings.

## Outputs

Return one `biostudies-archive-discovery-v1` record with required fields: `biological_question_and_scope`, `evidence_cutoff`, `query_and_parameters`, `endpoint_or_tool`, `release_and_access_time`, `result_count_and_page_coverage`, `accession_and_archive_type`, `organism_assay_and_study_type`, `record_metadata_and_provenance`, `linked_records_and_publications`, `file_manifest`, `file_size_and_license_as_reported`, `availability_and_completeness`, `controls`, `sensitivity`, `included_and_excluded_records`, `claim_id_and_status`, `uncertainty_and_limitations`, and `next_action`. Claim status `supported`, `contradicted`, `inconclusive`, or `unavailable` applies only to archive-discovery claims; archive presence is not a scientific result. Save query, manifest, exclusions, and hashes using `$science-provenance`; use `$science-review` before interpreting study findings.

## Boundaries

Archive presence does not imply assay quality, complete metadata, or reuse permission. Public availability does not override license terms. Do not describe a study as validated from its archive record or infer results from filenames. Stop before a large download until approved; retain incomplete manifests as incomplete rather than treating them as the full study.

Source basis: [BioStudies REST API](https://www.ebi.ac.uk/biostudies/help).
