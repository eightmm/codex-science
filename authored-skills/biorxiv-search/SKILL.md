---
name: biorxiv-search
description: "Fetch bioRxiv and medRxiv preprint metadata by DOI, or browse a narrow date range with a category, for life-science and medical preprints. Use when you already have a DOI or an approximate date plus category — not for open-ended keyword discovery. Public API, no credential needed."
license: Apache-2.0
---

# bioRxiv / medRxiv Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-biorxiv` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public bioRxiv API directly.

## Decision contract

Record whether the request is DOI metadata lookup or narrow date/category
browsing, the evidence cutoff, and whether preprints are acceptable. This is a
date archive, not a keyword search engine. Normalize a DOI as supplied and
verify the returned DOI and version before linking records; do not merge
distinct versions or published articles without evidence. Keep metadata claims
separate from paper findings and restrict inference to the text actually read.

## Reference usage

Read [references/preprint-archive-evidence.md](references/preprint-archive-evidence.md)
before selecting a route, paging, deduplicating versions, or making claims from
archive metadata. Read applicability and failure guidance before treating a
bounded date/category scan as informative; read controls and sensitivity
guidance before claiming robust retrieval.

## Workflow

1. **Gates (ask before proceeding).** On first use, pause and ask the user to
   review the bioRxiv terms (`https://api.biorxiv.org/`,
   `https://www.biorxiv.org/content/about-biorxiv`) and each paper's own license;
   wait for acknowledgment before continuing and record the notice in
   provenance. Network access is read-only; be polite about rate limits. If
   writing helper code, use `uv run`, never bare `python3`.
2. Determine whether the input is DOI lookup or date/category browsing; record
   the cutoff, category/range, preprint acceptability, and permitted inference.
   Reject topic-only discovery here and record the need for a keyword-capable
   source.
3. Choose the smallest route: DOI via
   `https://api.biorxiv.org/details/biorxiv/<DOI>` (use `medrxiv` for medRxiv),
   or a 1–4 week date/category range via
   `https://api.biorxiv.org/details/biorxiv/<YYYY-MM-DD>/<YYYY-MM-DD>/<cursor>`.
   A DOI from a citation can be fetched directly; date/category browsing needs
   an approximate date and category. The API has no server-side keyword search.
   Do not scan months/years or widen the range silently; broad local scans can
   trigger thousands of calls, timeouts, and API blocks.
4. For topic discovery, route to `$cx-pubmed-search`, `$cx-europepmc-search`,
   `$cx-openalex-search`, or `$cx-arxiv-search` to find candidate DOIs, then
   verify them here. Record exact URL/query, access time, cursor, date bounds,
   category, response count, and source-reported version/date.
   Preserve only version/update metadata actually reported; never invent it.
5. Page until source completion or the bounded range is exhausted. Validate
   response structure and DOI/title/date fields; detect malformed or truncated
   bodies before interpretation; write responses to a file and parse them.
   Retry rate limits or transient errors at most twice after waiting; preserve
   missing fields as unknown and mark exhaustion or unavailability explicitly.
6. Verify each returned DOI and version before linking; retain all records and
   date/category exclusions with reasons. Do not conflate distinct versions,
   published articles, or records that share an underlying study.
7. Check one known DOI/date-category record as a positive control and a
   nonmatching date/category case as a negative control; record outcomes. Vary
   date bounds, category, cursor/page cap, and DOI route one at a time; record
   which records change and label conclusions fragile when completeness changes.
8. Report title, DOI, date, category, version, URL, authors, abstract, and any
   published-DOI link actually returned. Distinguish metadata from full text;
   respect the individual license before reproducing text.
9. Save query, records, exclusions, shared-study dependencies, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.
   Verify page completion, version identity, and claim-to-text support.

## Outputs

Return `preprint-archive-evidence-v1` with normalized DOI or date/category;
exact query/access time and reported update/version; included/excluded records
with reasons; title, authors, date, category, version, abstract, DOI, URL,
publication state, and claim IDs; completeness/dependencies; uncertainty and
limitations; supported, contradicted, inconclusive, and unavailable claims;
next falsifiable action; artifact paths and hashes. Label metadata- and
abstract-only evidence.

## Boundaries

- Preprints are **not peer-reviewed**; flag that and prefer a published version
  when one exists, checking the returned published-DOI link.
- Cite only DOIs actually returned; never invent DOIs or abstracts.
- Respect each preprint's individual license before reproducing content.
- Topic-only queries, broad archive scans, missing DOI, and incomplete page
  sets cannot support a negative conclusion. Metadata and abstracts do not
  establish full-text claims.
