---
name: biostudies-search
description: "Discover public life-science studies and associated archive records through EMBL-EBI BioStudies. Use for ArrayExpress, supplementary-data, accession, and public dataset discovery; not as evidence of study quality or reuse permission."
license: MIT
---

# BioStudies Search

## Decision contract

Define the biological question, organism, assay/study type, desired data level, access constraints, and evidence cutoff. Normalize accession and organism identifiers where possible. Distinguish archive discovery from scientific evaluation and from permission to reuse data.

## Workflow

1. Call `science_search_biostudies` with a bounded biological query.
2. Filter by accession, study type, organism, assay, release date, and public availability before recommending a dataset.
3. Follow accession pages to verify files, linked publications, licenses, and download size; ask before large downloads.
4. Record query, accession, release, file manifest, and access time with `$science-provenance`.
5. Capture the exact query and parameters, endpoint/tool, access time, source release or update timestamp, result count, page coverage, and response hash. The bundled search accepts `query` and optional `limit`; use the BioStudies REST API directly for accession details and file manifests. Validate accession and response shape, detect truncation, and retain returned and excluded records with reasons.
6. Retry transient failures a bounded number of times and respect service throttling. If search fails, preserve an unavailable status; do not silently substitute an unstructured web search. Keep missing/null metadata distinct from records excluded by explicit filters.

## Outputs

Return normalized query/organism/assay, accession-level evidence table, included and excluded records with reason, linked publications, file manifest and size/license fields as reported, release/access provenance, missingness, uncertainty and limits, and the smallest falsifiable next action. Assign claim IDs as `supported`, `contradicted`, `inconclusive`, or `unavailable` only for archive-discovery claims; archive presence is not a scientific result. Save query, manifest, exclusions, and hashes using `$science-provenance`; use `$science-review` before interpreting study findings.

## Boundaries

Archive presence does not imply assay quality, complete metadata, or reuse permission. Public availability does not override license terms. Do not describe a study as validated from its archive record or infer results from filenames. Stop before a large download until approved; retain incomplete manifests as incomplete rather than treating them as the full study.

Source basis: [BioStudies REST API](https://www.ebi.ac.uk/biostudies/help).
