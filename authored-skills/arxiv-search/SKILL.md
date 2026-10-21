---
name: arxiv-search
description: "Search arXiv preprints for a topic, author, or concept and triage the results. Use when the user wants recent primary literature, preprints, or methods papers in physics, math, CS, quantitative biology, or statistics; use another source for peer-review status or complete coverage. Uses the plugin's built-in read-only arXiv MCP tool — no credential or install needed."
license: Apache-2.0
---

# arXiv Literature Search (Codex-native)

Codex-native literature search wired to this plugin's built-in read-only MCP
tool. Inspired by Google DeepMind's `literature-search-arxiv`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## Decision contract

Record the question, intended use, subject area, evidence cutoff, and whether
preprints are acceptable. Search is discovery, not systematic coverage. Use
arXiv identifiers as returned; do not infer a DOI or journal version from an
identifier. Material claims require the paper itself and stable claim IDs.

## Workflow

1. Search with `science_search_arxiv(query, limit)`: `query` is topic/author/
   keywords up to 500 characters; `limit` is 1–10, default 5. The result is a
   JSON list of `{id, title, summary, url}`. Save the exact query, tool, access
   time, returned IDs, and result count. For deeper structured retrieval, the
   direct API is `https://export.arxiv.org/api/query`; preserve its query,
   pagination parameters, response metadata, and pages. The MCP discovery call
   does not establish completeness or expose pagination.
2. Normalize arXiv IDs exactly as returned and deduplicate version suffixes
   only after verifying they identify the same work. Record the version/date
   reported by the response. Triage each record against explicit criteria;
   discard off-topic hits; do not pad the list. Retain included and excluded
   IDs with reasons. Empty results mean no match
   in this response, not evidence of absence.
3. If refining, re-query with more specific terms, an author, or a narrower
   concept; full-text search is broad, so precise terms help. Make a bounded
   focused query. On errors, malformed XML/JSON,
   missing IDs, or apparent truncation, preserve the failed response and retry
   at most twice with backoff; do not silently substitute web search. Mark an
   exhausted or unavailable source as unavailable. Open the returned URL (or
   its `/pdf/` variant) only when needed; ask before large downloads.
4. Validate required fields and record response/page counts and whether all
   requested pages were received. Cite only returned identifiers and URLs.
   Check license and redistribution terms before reproducing content.
5. Save a source receipt and evidence table with `$science-provenance`, including
   artifact paths and hashes. Use `$science-review` before material conclusions.

## Outputs

Return normalized question and query, cutoff, source/API and version or reported
update time, included and excluded IDs with reasons, and a table of ID, title,
URL, relevance, publication state, and supporting claim IDs. Separate strong
matches from tangential ones. Record claims as
supported, contradicted, inconclusive, or unavailable; include dependencies,
uncertainty, limitations, next falsifiable action, and artifact hashes. Abstract
only evidence remains abstract-level evidence.

## Boundaries

- arXiv preprints are **not peer-reviewed**; flag that when it matters and prefer
  the published version where one exists.
- Cite only ids/titles actually returned by the tool — never invent arXiv ids or
  fabricate abstracts.
- The tool is discovery, not full text; base specific claims on the paper you
  actually read, not the abstract alone.
- Stop if the question requires peer-reviewed-only evidence, complete recall,
  or a claim that cannot be checked from available text. Report API failures and
  missing records as unavailable, not negative findings.
