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
are source records, not a complete review or evidence of absence.

## Workflow

1. **Gates (ask before proceeding).** On first use tell the user to review
   Europe PMC terms (`https://europepmc.org/`) and each paper's license; record
   the notice in provenance. Read-only HTTP; keep to about 1 request/second. If
   writing helper code, use `uv run`, never bare `python3`.
2. Search with `science_search_europepmc(query, limit)` (`query` up to 500
   characters, `limit` 1–10, default 5). This bounded discovery tool does not
   expose API pagination. For exact pagination, citations, annotations, or
   full text, use the direct API:
   `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=<n>`.
   Europe PMC covers 40M+ abstracts across PubMed, PMC, preprints, and patents.
   Use source query syntax such as `AUTH:` and `PUB_YEAR:`. For full text
   restrict to open access (`OPEN_ACCESS:y`) and fetch by PMCID at
   `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC<ID>/fullTextXML`;
   only open-access articles have retrievable full text.
   Citations/references use `.../MED/<PMID>/citations` and `.../references`.
3. Record exact serialized query, tool/API, page size/token, access time,
   response count, and the release/update time actually reported. Page to an
   explicit source completion signal or a declared cap; state when capped.
   Validate JSON/XML structure, required identifiers, page continuity, and
   truncation before parsing. Write large XML responses to a file, not stdout.
4. Deduplicate exact records by verified PMID/PMCID/DOI; retain publication
   type and version. Apply stated inclusion criteria and report every returned
   and excluded record with reasons. Missing abstract/full text is unknown, not
   a negative result. For transient failures, retry at most twice with backoff;
   never replace structured-source failure with web search. Mark unavailable.
5. Report title, ID (PMID/PMCID/DOI), source, year, relevance, and URL; list URLs
   for every paper used. Save query and record receipts, exclusions and hashes
   with `$science-provenance`; use `$science-review` before material claims.

## Outputs

Return normalized question, exact query and cutoff, source and reported update
time, page/completeness status, included/excluded records with reasons, and a
table of IDs, title, source, year, URL, publication type, and claim IDs. Mark
claims supported, contradicted, inconclusive, or unavailable; include source
dependencies, missingness, uncertainty, limitations, next falsifiable action,
and artifact paths/hashes. Preserve raw response references and cited text
locators.

## Boundaries

- Cite only IDs actually returned; never invent PMIDs/PMCIDs/DOIs or abstracts.
- Full text exists only for open-access items; respect each article's license
  before reproducing content.
- Search results are references, not clinical advice. An empty result or missing
  full text is not evidence that no study or effect exists.
- Stop when required full text is unavailable, the result is truncated, or a
  material claim cannot be checked at the source. Abstract-only support must be
  labeled as such.
