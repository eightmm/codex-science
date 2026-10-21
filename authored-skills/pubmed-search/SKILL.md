---
name: pubmed-search
description: "Search PubMed biomedical literature for a topic, gene, drug, disease, or clinical question and retrieve article details. Use when the user wants peer-reviewed biomedical or clinical references; PubMed indexing does not guarantee peer review. Uses the plugin's built-in read-only PubMed MCP tool for discovery — no credential or install needed."
license: Apache-2.0
---

# PubMed Literature Search (Codex-native)

Codex-native biomedical literature search wired to this plugin's built-in
read-only MCP tool. Inspired by Google DeepMind's `pubmed-database`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## Decision contract

Record the biomedical question, population, intended use, evidence cutoff,
publication criteria, and permitted inference. PubMed is a bibliographic index;
state the search scope and do not imply comprehensive retrieval. Normalize and
retain PMIDs as strings. Assign claim IDs only when synthesizing source text.

## Workflow

1. Search with `science_search_pubmed(query, limit)`: `query` is topic/gene/
   drug/disease terms up to 500 characters; `limit` is 1–10, default 5. The
   result is a JSON list of `{id, title, url}` where `id` is PMID. This discovery
   tool returns PMIDs and links only, no abstract and no pagination.
2. For kept PMIDs, fetch details by opening returned URLs or use NCBI E-utilities
   `efetch`/`esummary`, including
   `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&retmode=xml`.
   Ask before large batch fetches and follow current NCBI rate limits. Record
   exact query, tool/API, access time, returned IDs, fetch parameters, response
   count, and any source-reported update time. Use a bounded page/batch size and
   record whether all requested records arrived.
3. Normalize each PMID and validate returned IDs against requested IDs. Parse
   title, authors, journal, year, abstract, publication type, and status only
   when present. Preserve missing abstracts or fields as unknown. Keep included
   and excluded PMIDs with reasons. Retry transient failures at most twice with
   backoff; preserve errors and mark unavailable instead of treating them as
   negative evidence or silently switching sources.
4. Refine with focused terms, MeSH-style phrasing, or date/keyword restrictions
   when broad. Report title, PMID, journal/year, relevance, and URL. Verify an
   abstract before quoting; check full text and license before using it for a
   claim.
5. Save query, result IDs, fetched records, exclusions, and hashes with
   `$science-provenance`; use `$science-review` before material claims.

## Outputs

Return normalized question, exact query/cutoff, tool/API, returned and fetched
counts, completeness status, included/excluded IDs with reasons, and a table of
PMID, title, journal/year, publication type, URL, relevance, and claim IDs.
Classify claims supported, contradicted, inconclusive, or unavailable; include
source dependencies, missingness, uncertainty, limitations, next falsifiable
action, and artifact paths/hashes. Label abstract-only evidence.

## Boundaries

- Cite only PMIDs actually returned by the tool; never invent PMIDs, journals,
  or abstracts. Verify the abstract before quoting it.
- Search results are references, **not clinical advice**; do not infer diagnosis,
  dosing, or treatment from them.
- Prefer primary studies and systematic reviews over secondary summaries when the
  user needs evidence strength.
- Indexing does not itself establish peer review. Missing abstracts, failed
  fetches, empty results, and incomplete batches are not negative evidence.
