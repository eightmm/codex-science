---
name: openalex-search
description: Query the OpenAlex scholarly graph for works, authors, institutions, sources, topics, and funders; resolve DOIs; and aggregate bibliometrics (citation counts, works). Use for academic discovery, author/institution lookup, or bibliometric summaries across all disciplines. Public API, no credential needed.
license: Apache-2.0
---

# OpenAlex Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-openalex` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public OpenAlex API directly. No credential needed — join the free
"polite pool" by adding your email as `mailto=` to each request.

## Gates (ask before proceeding)

- **Terms notice**: on first use, tell the user to review the OpenAlex terms
  (https://developers.openalex.org/) and to check each retrieved paper's own
  license; record the notice in provenance.
- **Network / install**: read-only public HTTP. Add `mailto=<email>` for the
  polite pool and rate-limit yourself. If you write helper code, run it via
  `uv run`, never bare `python3`.

## Workflow

1. **Resolve before you filter.** Never filter by a raw name. First resolve a
   name to an OpenAlex ID:
   - works: `https://api.openalex.org/works?search=<terms>`
   - authors/institutions/sources/topics/funders:
     `https://api.openalex.org/<entity>?search=<name>` → take the `id`.
2. **Filter by ID**, e.g.
   `https://api.openalex.org/works?filter=author.id:<A...>,publication_year:2024`.
   Use `select=` to keep responses small and write them to a file.
3. **Bibliometrics**: use `group_by=` for aggregations (counts by year, type,
   institution) and the entity's `cited_by_count` / `works_count` fields.
   Interpret metrics cautiously — citation counts are field- and age-biased.
4. **DOI lookup**: `https://api.openalex.org/works/https://doi.org/<DOI>`.
5. **Report** works with title, OpenAlex id and DOI, year, venue, and citation
   count; **list the URLs of every paper used.**
6. **Provenance & review**: record queries and cited ids with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Cite only OpenAlex IDs/DOIs actually returned; report empty results honestly
  and never fabricate ids or metrics.
- Bibliometrics (h-index, citation counts, "impact") are biased across fields and
  time; present them with that caveat, not as quality judgments.
- Open-access status varies per work; respect each item's license.
