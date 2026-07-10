---
name: arxiv-search
description: Search arXiv preprints for a topic, author, or concept and triage the results. Use when the user wants recent primary literature, preprints, or methods papers in physics, math, CS, quantitative biology, or statistics. Uses the plugin's built-in read-only arXiv MCP tool — no credential or install needed.
license: Apache-2.0
---

# arXiv Literature Search (Codex-native)

Codex-native literature search wired to this plugin's built-in read-only MCP
tool. Inspired by Google DeepMind's `literature-search-arxiv`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## How to run

1. **Search** with the plugin MCP tool `science_search_arxiv`:
   - arguments: `query` (topic/author/keywords, ≤500 chars), `limit` (1–10,
     default 5).
   - returns a JSON list of `{id, title, summary, url}` — arXiv id, title,
     abstract, and the abstract-page URL.
2. **Triage** the returned abstracts against the user's actual question. Discard
   off-topic hits; do not pad the list.
3. **Refine** if needed: re-query with more specific terms, an author, or a
   narrower concept. arXiv full-text search is broad, so precise terms help.
4. **Go deeper only when justified**: to read a paper, open its `url` (or the
   `/pdf/` variant) with a fetch tool and ask before large downloads.
5. **Report** each kept paper with title, arXiv id, one-line relevance, and the
   URL. Separate strong matches from tangential ones.
6. **Provenance & review**: record the queries, tool, and cited ids with
   `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- arXiv preprints are **not peer-reviewed**; flag that when it matters and prefer
  the published version where one exists.
- Cite only ids/titles actually returned by the tool — never invent arXiv ids or
  fabricate abstracts.
- The tool is discovery, not full text; base specific claims on the paper you
  actually read, not the abstract alone.
