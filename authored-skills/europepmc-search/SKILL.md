---
name: europepmc-search
description: "Search Europe PMC for life-science literature and retrieve abstracts, citations, and open-access full text (XML/plain text) by PMCID. Use when the user wants broad biomedical literature discovery or open-access full text. Public API, no credential needed."
license: Apache-2.0
---

# Europe PMC Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-europepmc` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public Europe PMC REST API directly.

## Decision contract

Record the biomedical question, intended use, population or system, cutoff,
publication types, and whether open-access full text is needed. Normalize PMID,
PMCID, and DOI separately; do not treat them as interchangeable. Search results
are source records, not a complete review or evidence of absence. Separate
record-description claims from claims about study findings, and state the
permitted inference level.

## Reference usage

Read [references/europepmc-evidence.md](references/europepmc-evidence.md) before
screening, deduplicating, interpreting citation links, or making claims from
Europe PMC. Read retrieval and lineage guidance before paging or merging with
other sources; read uncertainty, controls, and sensitivity guidance before
describing coverage or robustness.

## Workflow

1. **Gates (ask before proceeding).** On first use, pause and ask the user to
   review Europe PMC terms (`https://europepmc.org/`) and each paper's license;
   wait for acknowledgment before continuing and record the notice in
   provenance. Keep read-only HTTP to about 1 request/second. If writing helper
   code, use `uv run`, never bare `python3`.
2. Define the question, population/system, intended use, cutoff, eligible
   publication types, permitted claims, and whether full text is required;
   record material unresolved choices.
3. Use `science_search_europepmc(query, limit)` for bounded discovery (`query`
   up to 500 characters; `limit` 1–10, default 5). For exact pagination,
   citations, annotations, or full text, use the direct API, for example
   `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=<n>`.
   Use source syntax such as `AUTH:` and `PUB_YEAR:`. For full text require
   `OPEN_ACCESS:y` and fetch via PMCID at
   `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC<ID>/fullTextXML`;
   citation/reference routes use `.../MED/<PMID>/citations` and `.../references`.
   Europe PMC records span PubMed, PMC, preprints, and patents.
   Record exact serialized query, tool/API, access time, and requested page size/token.
4. Page to an explicit completion signal or declared cap; state when capped.
   Validate JSON/XML,
   identifiers, page continuity, and truncation; record response counts and
   source-reported update time. Write large XML responses to a file, not stdout.
5. Deduplicate verified PMID/PMCID/DOI identities while preserving publication
   type and version; do not collapse distinct preprint and published records.
   Apply stated criteria and retain all returned/excluded records with reasons.
6. Treat missing abstract/full text as unknown. Check one known eligible record
   as a positive control and an out-of-scope query or record as a negative
   control; record outcomes. Retry transient failures at most twice with
   backoff; never replace structured-source failure with web search.
   Mark exhausted or unavailable retrieval explicitly.
7. Vary synonyms, filters, date bounds, or page cap one at a time; report the
   changes in eligible records. Mark conclusions fragile if reasonable query
   variants or source overlap materially change the evidence set.
8. Verify each cited statement against the available source text; distinguish
   abstract-only from full-text support and honor licenses. List URLs for every
   paper used. Record source dependencies, including shared underlying studies
   and propagated records.
9. Save queries, source receipts, exclusions, cited text locators, and hashes
   with `$science-provenance`; use `$science-review` before material claims.
   Verify identifiers, counts, completeness, and claim status consistency.

## Outputs

Return `europepmc-evidence-v1` with normalized question/cutoff; exact query,
source and reported update time; page/completeness status; included/excluded
records with reasons; identifier, title, source, year, URL, publication type,
and claim-ID table; dependency groups; missingness and uncertainty; supported,
contradicted, inconclusive, and unavailable claims; limitations; next
falsifiable action; raw response references, artifact paths, and hashes.

## Boundaries

- Cite only identifiers actually returned; never invent PMIDs, PMCIDs, DOIs, or
  abstracts.
- Full text exists only for open-access items; respect each article's license
  before reproducing content.
- Search results are references, not clinical advice. Empty results and missing
  full text do not show that no study or effect exists.
- Stop when required full text is unavailable, the result is truncated, or a
  material claim cannot be checked at source. Abstract-only support must be
  labeled.
