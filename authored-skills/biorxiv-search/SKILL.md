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
verify the returned DOI and version before linking records; do not merge distinct
versions or published articles without evidence.

## Workflow

1. **Gates (ask before proceeding).** On first use, tell the user to review the
   bioRxiv terms (`https://api.biorxiv.org/`,
   `https://www.biorxiv.org/content/about-biorxiv`) and each paper's own license;
   record this notice in provenance. Network access is read-only; be polite
   about rate limits. If writing helper code, use `uv run`, never bare
   `python3`.
2. Select the smallest route. By DOI use
   `https://api.biorxiv.org/details/biorxiv/<DOI>` (use `medrxiv` for medRxiv).
   By date/category use
   `https://api.biorxiv.org/details/biorxiv/<YYYY-MM-DD>/<YYYY-MM-DD>/<cursor>`
   and keep the range narrow (1–4 weeks). The API has **no server-side keyword
   search**. For topic-only discovery use `$cx-pubmed-search`,
   `$cx-europepmc-search`, `$cx-openalex-search`, or `$cx-arxiv-search` to find
   candidate DOIs, then verify them here; do not scan months/years locally.
3. Serialize and save the exact URL/query, access time, cursor, date bounds,
   category filter, response count, and reported version/date. Page until the
   source signals completion or the bounded requested range is exhausted. Keep
   returned and category/date-excluded records with reasons. Capture the
   release/version or update metadata actually present; do not invent it.
4. Validate response structure and required DOI/title/date fields; detect a
   truncated or malformed body before interpreting it. On rate limits or
   transient errors, wait and retry at most twice; do not widen the range
   silently. Preserve null/missing fields as unknown, not negative findings.
   Mark exhausted/unavailable retrieval explicitly.
5. Report each preprint with title, DOI, date, category, version, and URL.
   Check for a published-DOI link without conflating publication state. Save
   query, records, exclusions, and hashes with `$science-provenance`; use
   `$science-review` before material conclusions.

## Outputs

Return normalized DOI or date/category, exact query and access time, reported
version/update time, included and excluded records with reasons, and a table of
title, DOI, date, category, version, URL, publication state, and claim IDs.
Classify claims supported, contradicted, inconclusive, or unavailable; state
uncertainty, shared-study dependencies, limitations, next falsifiable action,
and artifact paths/hashes.

## Boundaries

- Preprints are **not peer-reviewed**; flag that and prefer the published
  version when one exists (check for a published-DOI link).
- Cite only DOIs actually returned; never invent DOIs or abstracts.
- Respect each preprint's individual license before reproducing content.
- A topic-only query, broad archive scan, missing DOI, or incomplete page set
  cannot support a negative search conclusion; stop or use a keyword-capable
  source. Metadata and abstracts do not establish full-text claims.
