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
Keep descriptive claims about records distinct from empirical claims about
health effects; causal or clinical claims require designs and evidence beyond
retrieval and must remain conditional on reviewed source text.

## Reference usage

Read [references/pubmed-evidence.md](references/pubmed-evidence.md) before
screening evidence, describing source coverage, or synthesizing claims. Read its
query and record-lineage sections when changing terms, deduplicating, or
combining records across databases; read controls and sensitivity sections
before reporting a bounded search as robust.

## Workflow

1. Define population, question, intended use, cutoff, eligible publication
   types, and claim classes; record unresolved choices that could change
   retrieval.
2. Select PubMed for bibliographic discovery, state why it fits the question,
   and identify whether complementary sources are needed; record the source
   scope and expected blind spots.
3. Search with `science_search_pubmed(query, limit)`: `query` is topic/gene/
   drug/disease terms up to 500 characters; `limit` is 1–10, default 5. Record
   the exact query, tool, access time, returned IDs, and count. This discovery
   tool returns `{id, title, url}` only, with no abstract and no pagination.
4. For kept PMIDs, fetch details from returned URLs or NCBI E-utilities
   `efetch`/`esummary`, for example
   `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=<PMID>&retmode=xml`;
   ask before large batch fetches and follow current NCBI rate limits. Record
   endpoint, parameters, response count, reported update time, and whether all
   requested records arrived; use a bounded page/batch size.
5. Normalize PMIDs as strings and validate returned IDs against requested IDs;
   parse title, authors, journal, year, abstract, publication type, and status
   only when present. Preserve missing abstracts or fields as unknown and retain
   included and excluded PMIDs with reasons. Retry transient failures at most
   twice with backoff; retain errors and mark unavailable without silent source
   substitution.
6. Check a known relevant record as a positive retrieval control and a clearly
   out-of-scope term as a negative control; record their outcomes and revise a
   query that fails either check.
7. Refine broad queries with focused terms, MeSH-style phrasing, or date/keyword
   restrictions. Vary one element at a time; record added/removed eligible records and label
   conclusions fragile when those choices change the evidence set materially.
8. Verify abstracts before quoting, and full text and license before using it
   for a claim; report title, PMID, journal/year, relevance, and URL. Label
   abstract-only support and distinguish source statements from inference.
9. Save queries, records, exclusions, dependencies, and hashes with
   `$science-provenance`; use `$science-review` before material claims. Verify
   that IDs, counts, exclusions, and claim statuses agree, and record failures
   or the reason the search remains incomplete.

## Outputs

Return `pubmed-evidence-v1` with normalized question and cutoff; exact query,
tool/API, access time and source-reported update time; returned/fetched counts
and completeness; included/excluded IDs with reasons; a table of PMID, title,
journal/year, publication type, URL, relevance, and claim IDs; dependency groups;
missingness and uncertainty; supported, contradicted, inconclusive, and
unavailable claims; limitations; next falsifiable action; and artifact
paths/hashes. Label abstract-only evidence.

## Boundaries

- Cite only PMIDs actually returned by the tool; never invent PMIDs, journals,
  or abstracts. Verify the abstract before quoting it.
- Search results are references, **not clinical advice**; do not infer
  diagnosis, dosing, or treatment from them.
- Prefer primary studies and systematic reviews over secondary summaries when
  the user needs evidence strength.
- Indexing does not itself establish peer review. Missing abstracts, failed
  fetches, empty results, and incomplete batches are not negative evidence.
- Respect full-text licenses. Stop or downgrade when source text, population,
  or publication status cannot be verified.
