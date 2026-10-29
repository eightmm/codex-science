---
name: proteomexchange-search
description: "Resolve a known PXD accession through ProteomeXchange. Use for cross-repository accession verification and proteomics reanalysis planning; use PRIDE for keyword discovery."
license: MIT
---

# ProteomeXchange Search

## Decision contract
Role: retriever. Start from a PXD accession supplied by a paper, PRIDE search, or dataset record; this skill verifies a known accession and does not replace keyword discovery. State the metadata question, evidence cutoff, and required repository or file checks. Preserve the accession exactly as supplied and do not normalize it into a different repository's identifier. Classify claims as registration metadata, repository availability, publication linkage, or file/analysis evidence; a registration alone cannot establish dataset quality or identification validity. Use statuses `supported`, `contradicted`, `inconclusive`, and `unavailable` for scoped claims.

## Reference usage
Read [ProteomeXchange registration and provenance](references/proteomexchange-registration.md) before resolving identifier relationships, comparing ProteomeCentral with a member repository, interpreting a registration or reprocessed dataset, or claiming availability. It defines dependence, controls, uncertainty, and source boundaries.

## Workflow
1. **Gates (ask before proceeding).** If repository terms prevent traceable use, a requested action needs credentialed access, or the accession cannot be resolved unambiguously, stop and ask before substitution, access, or analysis. Record the unresolved accession/action and stop reason.
2. Preserve the supplied PXD accession exactly and state the metadata question, evidence cutoff, and required repository/file checks. Record whether the task is verification or a separately authorized reanalysis plan; keyword discovery remains in PRIDE search.
3. Call `science_search_proteomexchange` with the accession as query and optional `limit` (legacy source tools accept `limit` from 1 to 10). For bounded normalized retrieval, use `source="proteomexchange"`. `science_query_source_v2` requires `source` and `parameters`; optional top-level fields are `operation`, `page_size`, `max_pages`, and `include_snapshot`. Current v2 legacy sources accept required `parameters.query` (a non-empty string) and optional `parameters.limit` (an integer from 1 to 10). `science_list_source_contracts` lists available sources and operations; it does not return a parameter schema. Current v2 routes refuse `evidence_cutoff`; record the cutoff in your protocol and apply it to returned record dates yourself, treating missing dates as unresolved. Record query, source, page size/cap, cutoff, and completeness.
4. **Verify** accession identity, hosting repository, species, instrument, publication status, keywords, and availability using the response and repository of record. Prefer PRIDE-specific metadata when hosted by PRIDE; preserve repository-specific IDs and record only reported release/update markers and access time.
5. Compare the registration with cited paper and repository record. Preserve exact queries, pages, included/excluded records and reasons; validate response shape, accession identity, and truncation. Distinguish valid registration, accessible project, downloadable files, published analysis, and identification quality.
6. Retry transient errors within a small fixed bound; then report source unavailable with attempted query and failure state. Never substitute another accession or treat request failure as absence. Check citation and data terms before reanalysis or redistribution; record null/missing fields separately from inaccessible records.
7. Apply the reference's identity and independence controls. Treat ProteomeCentral, member repository records, the corresponding paper, and reprocessed descendants as linked evidence until provenance establishes otherwise; report conflicts and sensitivity to repository/release choice.
8. Record manifests, repository checks, queries, and hashes with `$science-provenance`; use `$science-review` before dataset-selection or reanalysis claims. Return claim statuses, uncertainty, applicability limits, unresolved metadata, and the smallest falsifiable follow-up.

## Outputs
Return one `proteomexchange-accession-evidence-v1` record with: question and evidence cutoff (`question_and_cutoff`); supplied PXD accession (`supplied_accession`); claim register (`claim_register`: claim ID, class, text, status, evidence IDs); verification table (`verification_table`: source, hosting repository, repository accession, species, instrument, publication status, keywords, availability, release/access time, query reference); exact query and page provenance (`query_provenance`: query, parameters, pages, completeness, response hashes); included/excluded records and counts with reasons (`record_flow`); dependency graph (`dependency_graph`: registration, repository, paper, reprocessing relationships); uncertainty and sensitivity (`uncertainty_and_sensitivity`); controls (`controls`); applicability domain (`applicability_domain`); unresolved metadata (`unresolved_metadata`); limitations (`limitations`); smallest falsifiable follow-up (`next_falsifiable_action`); provenance and review references (`provenance_and_review_refs`). Record file manifests, repository checks, queries, and hashes with `$science-provenance`. Use `$science-review` before dataset-selection or reanalysis claims.

## Boundaries
Do not infer completeness, data accessibility, identification quality, or biological support from ProteomeXchange registration alone. A PXD record is not independent evidence from the corresponding PRIDE or repository record. Stop when the accession cannot be resolved or repository terms prevent traceable use; distinguish missing fields from null values and inaccessible records.

Source basis: [ProteomeXchange API](https://proteomecentral.proteomexchange.org/cgi/GetDataset); [ProteomeCentral service documentation](https://proteomecentral.proteomexchange.org/doc/serviceDocs.php).
