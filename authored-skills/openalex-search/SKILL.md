---
name: openalex-search
description: "Query the OpenAlex scholarly graph for works, authors, institutions, sources, topics, and funders; resolve DOIs; and aggregate bibliometrics (citation counts, works). Use for academic discovery, author/institution lookup, or bibliometric summaries across all disciplines. Public API, no credential needed."
license: Apache-2.0
---

# OpenAlex Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-openalex` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public OpenAlex API directly. No credential needed — join the free
"polite pool" by adding your email as `mailto=` to each request.

## Decision contract

Record the question, entity type, intended bibliometric or discovery use,
cutoff, and comparison population. Resolve names to source identifiers before
filtering; names can be ambiguous. OpenAlex records and bibliometrics describe
the graph as retrieved, not scholarly quality or complete coverage.

## Workflow

1. **Gates (ask before proceeding).** Tell the user on first use to review
   OpenAlex terms (`https://developers.openalex.org/`) and paper licenses;
   record the notice. Read-only HTTP; add `mailto=<email>` for the polite pool
   and respect the source's current guidance. Helper code must use `uv run`,
   never bare `python3`.
2. Search with `science_search_openalex(query, limit)` (`query` up to 500
   characters, `limit` 1–10, default 5) for bounded work discovery. For other
   entities, filters, grouping, or pagination use the direct API. Resolve first:
   `https://api.openalex.org/works?search=<terms>` or
   `https://api.openalex.org/<entity>?search=<name>`; take and verify the
   returned ID. Then filter, e.g.
   `https://api.openalex.org/works?filter=author.id:<A...>,publication_year:2024`.
   Use `select=` to reduce response size, `group_by=` for aggregate counts, and
   `https://api.openalex.org/works/https://doi.org/<DOI>` for DOI lookup.
   Entity types include works, authors, institutions, sources, topics, and
   funders. Write large responses to a file and parse them.
3. Record exact query/URL, entity IDs, access time, page parameters, counts, and
   reported release/update time. Paginate to source completion or a declared
   cap; the MCP search is not paginated. Validate response shape and IDs, detect
   missing pages/truncation, and preserve null fields. Retry transient failures
   at most twice with backoff. Do not silently substitute another source.
4. Apply stated criteria and preserve returned and excluded IDs with reasons.
   Report the returned `cited_by_count`/`works_count` or group counts with
   source-reported date; citation counts are field- and age-biased; do not
   infer missing metrics as zero. Cite only IDs, DOI, and URLs returned. List
   the URLs of every paper used. Respect each work's license before reproducing text.
5. Save exact queries, records, exclusions, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return normalized entity/query and cutoff, resolved OpenAlex IDs, source and
reported update time, completeness/page status, included and excluded records
with reasons, and a table of ID, title, DOI, year, venue, URL, metric and its
date, and claim IDs. Mark claims supported, contradicted, inconclusive, or
unavailable; include dependency groups, uncertainty, field/age limitations,
next falsifiable action, and artifact paths/hashes.

## Boundaries

- Cite only OpenAlex IDs/DOIs actually returned; report empty results honestly
  and never fabricate ids or metrics.
- Bibliometrics (h-index, citation counts, "impact") are biased across fields
  and time; present them with that caveat, not as quality judgments.
- Open-access status varies per work; respect each item's license.
- Ambiguous entity resolution, missing pages, and null values remain unresolved;
  they do not support a negative conclusion. Bibliometric association does not
  establish research quality, influence, or causality.
