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
identifier. Separate repository metadata claims from findings in a paper;
material claims require the paper itself and stable claim IDs.

## Reference usage

Read [references/arxiv-evidence.md](references/arxiv-evidence.md) before
screening or synthesizing preprints. Read version, lineage, and publication
status guidance before deduplication or citation; read controls and sensitivity
guidance before interpreting bounded-search results.

## Workflow

1. Define the question, intended use, subject area, cutoff, acceptable
   publication states, and permitted claim types; record whether peer review is
   required.
2. Select arXiv for preprint discovery and record why its subject coverage fits;
   state that this search does not establish coverage or peer-review status.
3. Search with `science_search_arxiv(query, limit)` (`query` up to 500
   characters; `limit` 1–10, default 5); `query` is free text, arXiv field
   syntax (e.g. `ti:`, `au:`, `cat:` with AND/OR/ANDNOT) or a bare arXiv ID. Record exact query, tool, access time,
   returned IDs, and count; the result is `{id,title,summary,url}` with no
   completeness or pagination guarantee.
4. For structured retrieval use `https://export.arxiv.org/api/query`; record
   query and pagination parameters, response metadata, and each page. Normalize
   IDs exactly. Merge version suffixes only after verifying same-work identity;
   preserve version/date and distinct published records.
5. Triage against explicit criteria; discard off-topic hits and do not pad the list. Retain included and excluded IDs with
   reasons. Check required fields, page counts, truncation, and malformed data;
   retry at most twice with backoff, preserve failed responses, and mark
   unavailable rather than silently switching sources. Empty results mean no
   match in this response, not evidence of absence.
6. Check one known relevant preprint as a positive control and a clearly
   off-topic term as a negative control; record outcomes. Vary terms, author,
   subject, or date bounds one at a time; record record-set changes and label
   conclusions fragile when reasonable variants alter them materially. When
   broad, re-query with a focused term, author, or narrower concept.
7. Open the returned paper only as needed; base specific claims on text actually
   read, not metadata or abstract alone. Record version, publication state,
   claim locator, dependencies, and license before quoting or reproducing text.
   Ask before large downloads; use the returned URL or its `/pdf/` variant only
   when needed.
8. Distinguish preprint status from peer review and verify any published version
   through its returned/source-linked identity; do not conflate versions or
   independent studies from the same underlying work.
9. Save query, source receipt, evidence table, exclusions, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.
   Verify identifiers, completeness, and claim-to-text links.

## Outputs

Return `arxiv-evidence-v1` with normalized question/query/cutoff; source/API
and version/update time; included/excluded IDs with reasons; ID, title, URL,
relevance (separating strong matches from tangential results), publication
state/version, and claim-ID table; completeness and
dependency status; uncertainty and limitations; supported, contradicted,
inconclusive, and unavailable claims; next falsifiable action; artifact paths
and hashes. Label abstract-only evidence.

## Boundaries

- arXiv preprints are **not peer-reviewed**; flag that when it matters and
  prefer the published version where one exists.
- Cite only identifiers, titles, and URLs actually returned; never invent IDs
  or abstracts.
- Metadata and abstracts do not establish full-text claims. Respect license and
  redistribution terms before reproducing content.
- Stop if peer-reviewed-only evidence, complete recall, or unavailable claim
  text is required. API failures and missing records are unavailable, not
  negative findings.
