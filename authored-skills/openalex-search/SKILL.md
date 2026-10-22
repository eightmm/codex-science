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
filtering; names can be ambiguous. OpenAlex records and metrics describe the
graph as retrieved, not scholarly quality or complete coverage. Keep
descriptive graph claims distinct from claims about research quality, influence,
or causality.

## Reference usage

Read [references/openalex-evidence.md](references/openalex-evidence.md) before
entity resolution, filtering, aggregation, or interpreting graph metrics. Read
lineage and independence guidance before combining works or citation counts;
read controls and sensitivity guidance before reporting rankings or trends.

## Workflow

1. **Gates (ask before proceeding).** On first use, pause and ask the user to
   review OpenAlex terms (`https://developers.openalex.org/`) and paper
   licenses; wait for acknowledgment before continuing and record the
   notice. Keep requests read-only, add `mailto=<email>` to each request for the
   polite pool, follow current source guidance, and use `uv run` rather than
   bare `python3` for helper code.
2. Define the question, entity type, intended use, cutoff, comparison set, and
   permitted inference; record ambiguity that could alter entity selection.
3. Use `science_search_openalex(query, limit)` for bounded work discovery
   (`query` up to 500 characters; `limit` 1–10, default 5). For other entities,
   filters, grouping, or pagination use the direct API. Resolve works with
   `https://api.openalex.org/works?search=<terms>` or entity names with
   `https://api.openalex.org/<entity>?search=<name>`, then filter by verified
   IDs, for example
   `https://api.openalex.org/works?filter=author.id:<A...>,publication_year:2024`;
   `select=` reduces fields and `group_by=` aggregates. DOI resolution uses
   `https://api.openalex.org/works/https://doi.org/<DOI>`. Entity types include
   works, authors, institutions, sources, topics, and funders. Write large
   responses to a file and parse them. Record exact query/URL, entity type,
   access time, and resolution candidates.
4. Resolve names to returned IDs before filtering. Verify entity type and
   disambiguate against available attributes; leave ambiguous matches
   unresolved. Record ID and resolution rationale before applying filters.
5. Paginate to source completion or a declared cap; validate response shape,
   IDs, missing pages, truncation, and null values. Record counts and source
   reported release/update time when present. Retry transient failures at most
   twice with backoff and do not silently substitute another source.
6. Apply prespecified criteria; retain included and excluded IDs with reasons.
   Report `cited_by_count`, `works_count`, or grouped counts with the
   source-reported date; do not turn absent/null values into zero. Record works
   that share a study, cohort, or propagated record as dependent evidence.
7. Check a known entity/record as a positive control and an impossible or
   out-of-scope identifier/filter as a negative control; record expected and
   observed outcomes. Vary search terms, entity resolution, date/window, and
   filters one at a time; record ranking/count changes and label unstable
   conclusions fragile.
8. Cite only returned IDs, DOIs, and URLs; list URLs for every paper used.
   Report metric definitions and dates. Check the source and license before
   reproducing text; distinguish graph description from scientific
   interpretation.
9. Save exact queries, records, exclusions, dependency groups, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.
   Verify page completeness and that each claim traces to a returned record.

## Outputs

Return `openalex-evidence-v1` with normalized entity/query/cutoff; resolved IDs
and rationale; source/update time and page status; included/excluded records
with reasons; ID, title, DOI, year, venue, URL, metric/date, and claim-ID table;
dependency groups; uncertainty and field/age limitations; supported,
contradicted, inconclusive, and unavailable claims; next falsifiable action;
artifact paths and hashes.

## Boundaries

- Cite only OpenAlex IDs/DOIs actually returned; never fabricate IDs or metrics.
- Report empty results honestly as no matches in the returned response, not
  evidence that no work exists.
- Citation counts, h-index, and impact are field- and age-biased; present them
  with those caveats, not as quality judgments.
- Open-access status varies per work; respect each item's license.
- Ambiguous entity resolution, missing pages, and null values remain unresolved
  and do not support negative conclusions. Bibliometric association establishes
  neither research quality, influence, nor causality.
