---
name: pride-search
description: "Discover public proteomics projects through PRIDE Archive. Use for mass-spectrometry datasets, reanalysis candidates, protein evidence, or public-study discovery."
license: MIT
---

# PRIDE Search

## Decision contract
Role: retriever. State whether the goal is project discovery, dataset selection, or a specific protein/assay question. Normalize organism, disease, tissue, protein accession, instrument, assay, and date range as applicable. Set inclusion rules and evidence cutoff first; project metadata alone cannot establish an identification or biological result.

## Workflow
1. Query `science_search_pride` with a concise, source-specific `query` and optional `limit` (legacy source tools accept `limit` from 1 to 10). Preserve the exact serialized query. For structured pagination, inspect the available source contract before calling `science_query_source_v2` or `science_query_source_v3`; record source, parameters, page size, maximum pages, cutoff, and response completeness. Direct API calls must follow the current PRIDE API documentation rather than guessed parameters.
2. Resolve each returned accession to its project record. Verify organism, tissue, instrument, quantification method, publication, file availability, and license on the project page. Record the release or last-updated value actually reported, access time, and repository citation. Keep project, sample, file, and publication identifiers distinct.
3. Inspect the file manifest, formats, and sizes before selecting files; ask before large transfers. Capture the exact files used and any transformations. Do not download files merely to improve a metadata-only discovery answer. If a transfer or response is interrupted, preserve partial status and do not call the project complete.
4. Detect pagination exhaustion, response truncation, repeated records, and malformed accessions. Use bounded retries for transient failures; do not silently broaden a query or replace a failed structured query with an unrelated web search. Distinguish no matching record, no available files, filtered results, null metadata, and source failure. Report records returned and excluded with reasons, and observe the source's access and reuse terms.

## Outputs
Return normalized query inputs; a project table with accession, organism, tissue, instrument, assay/quantification, publication, file counts or manifest reference, release/access time, and terms; exact query and page provenance; records included and excluded with reasons; claim IDs and statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`; uncertainty, dependencies, and dataset-selection limitations; and the smallest falsifiable next action. Save query, manifest, chosen files, transformations, and hashes with `$science-provenance`. Use `$science-review` before claims that rely on reanalysis or protein evidence.

## Boundaries
Dataset discovery is not peptide/protein identification evidence until the relevant files and search parameters are inspected. A project page does not prove data quality, completeness, biological relevance, or reproducibility. Do not infer missing metadata from file names. Stop before large downloads, credentialed access, or unclear license terms; distinguish files absent from files not checked.

Source basis: [PRIDE Archive API](https://www.ebi.ac.uk/pride/ws/archive/v3/swagger-ui.html); [API guide](https://www.ebi.ac.uk/pride/ws/archive/v2/docs/api-guide.html).
