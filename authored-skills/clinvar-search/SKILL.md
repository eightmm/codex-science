---
name: clinvar-search
description: "Look up clinical significance and pathogenicity classifications (Pathogenic, Benign, VUS) and supporting evidence for human genomic variants in NCBI ClinVar. Use for variant clinical interpretation or benchmark controls. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Clinvar Search (Codex-native)

Codex-native adaptation of Google DeepMind's `clinvar-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract
Record the variant query (rsID, HGVS, or gene), species, any supplied assembly, condition/phenotype, evidence cutoff, and whether the task asks for a record lookup or an interpretation summary. Preserve ambiguous variants as unresolved until normalized to a returned ClinVar record. ClinVar assertions are submissions with review-status metadata; do not collapse distinct conditions or submissions into one label.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (`esearch`, `esummary`, `efetch`, `db=clinvar`). Search, retain the exact query and returned identifiers, then retrieve the selected record. Validate that the returned variant and condition match the request; record response truncation or failed pages and do not treat them as empty results. If the Codex Science MCP source is enabled, `science_query_source_v2` with `source="clinvar"` is an additional route; its arguments are `source`, `parameters`, optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. Consult `science_list_source_contracts` and use only the parameter schema it reports.

Capture query, endpoint/tool, access time, response or artifact hash, record identifiers, returned and excluded counts, exclusion reasons, and release/version metadata when reported. Distinguish no matching record, unavailable service, omitted field, and explicit null. Bound retries to transient failures, honor service responses, and do not substitute broad web search for a failed structured query. Record queries, endpoints, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Outputs
Return normalized query and assembly, ClinVar VCV/RCV accessions actually returned, condition, classification, review status/star rating, supporting and conflicting evidence, retrieval timestamp/version, and an inclusion/exclusion table. Mark each requested conclusion supported, contradicted, inconclusive, or unavailable, with uncertainty, limitations and the smallest next lookup that could resolve ambiguity. Preserve the raw response or a hash-bound saved artifact.

## Boundaries
Clinical significance and review status vary in confidence; report the star rating. This is not clinical or diagnostic advice. Cite only ClinVar accessions (VCV/RCV) actually returned. A missing record or blank field is not evidence of benignity; a classification is not an individual diagnosis. Stop interpretation when allele, build, condition, or record identity cannot be resolved.
