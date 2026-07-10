---
name: pubmed-search
description: "Search PubMed biomedical literature for a topic, gene, drug, disease, or clinical question and retrieve article details. Use when the user wants peer-reviewed biomedical or clinical references. Uses the plugin's built-in read-only PubMed MCP tool for discovery — no credential or install needed."
license: Apache-2.0
---

# PubMed Literature Search (Codex-native)

Codex-native biomedical literature search wired to this plugin's built-in
read-only MCP tool. Inspired by Google DeepMind's `pubmed-database`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## How to run

1. **Search** with the plugin MCP tool `science_search_pubmed`:
   - arguments: `query` (topic/gene/drug/disease terms, ≤500 chars), `limit`
     (1–10, default 5).
   - returns a JSON list of `{id, title, url}` where `id` is the **PMID** and
     `url` is the PubMed entry. Note: this discovery tool returns **PMIDs and
     links only — no abstract**.
2. **Fetch details** for the PMIDs you keep: open each `url` with a fetch tool,
   or use NCBI E-utilities `efetch`/`esummary`
   (`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&retmode=xml`)
   to get title, authors, journal, year, and abstract. Ask before large batch
   fetches; stay within NCBI rate limits.
3. **Refine** with focused terms, MeSH-style phrasing, or a date/keyword narrow
   when results are too broad.
4. **Report** each kept article with title, PMID, journal/year, one-line
   relevance, and the URL.
5. **Provenance & review**: record queries, tool, and cited PMIDs with
   `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Cite only PMIDs actually returned by the tool; never invent PMIDs, journals,
  or abstracts. Verify the abstract before quoting it.
- Search results are references, **not clinical advice**; do not infer diagnosis,
  dosing, or treatment from them.
- Prefer primary studies and systematic reviews over secondary summaries when the
  user needs evidence strength.
