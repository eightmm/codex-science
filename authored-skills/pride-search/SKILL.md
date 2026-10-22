---
name: pride-search
description: "Discover public proteomics projects through PRIDE Archive. Use for mass-spectrometry datasets, reanalysis candidates, protein evidence, or public-study discovery."
license: MIT
---

# PRIDE Search

## Decision contract
Role: retriever. State whether the goal is project discovery, dataset selection, or a specific protein/assay question. Normalize organism, disease, tissue, protein accession, instrument, assay, and date range as applicable. Set inclusion rules and evidence cutoff first; project metadata alone cannot establish an identification or biological result. Classify claims as project metadata, dataset availability, analysis-result evidence (only when relevant files, search parameters, and result records were inspected), or unavailable/contradicted/inconclusive. Dataset discovery alone supports candidate selection, not biological conclusions.

## Reference usage
Read [PRIDE project and file evidence](references/pride-project-evidence.md) before ranking candidate datasets, treating repository metadata as evidence, reporting file availability, or planning a reanalysis. It defines project/sample/file distinctions, dependence checks, controls, uncertainty, and applicability limits.

## Workflow
1. **Gates (ask before proceeding).** Stop and ask before a large file transfer, credentialed access, or use with unclear license/reuse terms; do not proceed until authorized and terms are clear. Record the requested action, size/access/terms uncertainty, and stop reason.
2. Normalize the discovery or assay question and applicable organism, disease, tissue, protein accession, instrument, assay, date range, inclusion rules, and evidence cutoff. Record which fields are required and which can remain unknown.
3. Query `science_search_pride` with a concise, source-specific `query` and optional `limit` (legacy source tools accept `limit` from 1 to 10). Preserve the serialized query. For structured pagination, inspect the source contract before `science_query_source_v2` or `science_query_source_v3`; direct API calls follow current PRIDE API documentation. Record source, parameters, page size, maximum pages, cutoff, and completeness.
4. Resolve each returned accession to its project record. **Verify** organism, tissue, instrument, quantification method, publication, file availability, and license from returned/project metadata; record only release or last-updated values actually reported, access time, repository citation, and distinct project/sample/file/publication IDs.
5. Inspect manifest, formats, and sizes before selecting files. Download only when needed for the stated analysis and after Gate 1; capture exact files and transformations. Do not download to improve a metadata-only answer. If transfer or response is interrupted, retain partial status and do not mark the project complete.
6. Check pagination exhaustion, truncation, repeated records, and malformed accessions. Retry transient failures within a small fixed bound; do not broaden silently or replace a failed structured query with unrelated web search. Distinguish no matching record, unavailable files, filtered results, null metadata, and source failure; record returned/excluded records and reasons, and follow access/reuse terms.
7. Apply controls and sensitivity checks from the reference before ranking or selecting datasets. If rankings depend on metadata completeness, publication status, inclusion choices, or project/sample duplication, report the sensitivity and downgrade the selection claim as needed.
8. Save query, manifest, chosen files, transformations, and hashes with `$science-provenance`; use `$science-review` before claims relying on reanalysis or protein evidence. Record uncertainty, dependencies, applicability limits, and the smallest falsifiable next action.

## Outputs
Return one `pride-dataset-evidence-v1` record with: question and evidence cutoff (`question_and_cutoff`); normalized query inputs (`normalized_search_inputs`); claim register (`claim_register`: claim ID, class, text, status, evidence IDs); project evidence table (`project_table`: accession, organism, tissue, instrument, assay/quantification, publication, file count/manifest, release/access time, terms, inclusion/exclusion); included/excluded records and counts with reasons (`record_flow`); exact query and page provenance (`query_provenance`: query, source, pages, completeness, response hashes); selected files and transformations (`file_lineage`); dependency graph (`dependency_graph`: project/sample/publication and propagated-result relationships); uncertainty and sensitivity (`uncertainty_and_sensitivity`); controls (`controls`); applicability domain (`applicability_domain`); limitations (`limitations`); smallest falsifiable next action (`next_falsifiable_action`); provenance and review references (`provenance_and_review_refs`). Save query, manifest, chosen files, transformations, and hashes with `$science-provenance`. Use `$science-review` before claims that rely on reanalysis or protein evidence.

## Boundaries
Dataset discovery is not peptide/protein identification evidence until the relevant files and search parameters are inspected. A project page does not prove data quality, completeness, biological relevance, or reproducibility. Do not infer missing metadata from file names. Stop before large downloads, credentialed access, or unclear license terms; distinguish files absent from files not checked.

Source basis: [PRIDE Archive API](https://www.ebi.ac.uk/pride/ws/archive/v3/swagger-ui.html); [API guide](https://www.ebi.ac.uk/pride/ws/archive/v2/docs/api-guide.html).
