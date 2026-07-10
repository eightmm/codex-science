---
name: biorxiv-search
description: "Fetch bioRxiv and medRxiv preprint metadata by DOI, or browse a narrow date range with a category, for life-science and medical preprints. Use when you already have a DOI or an approximate date plus category — not for open-ended keyword discovery. Public API, no credential needed."
license: Apache-2.0
---

# bioRxiv / medRxiv Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-biorxiv` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public bioRxiv API directly.

## Read first: this is a date archive, not a search engine

The bioRxiv API has **no server-side keyword search**. Choose by what you know:

- **DOI** (from a citation): fetch metadata directly. Fast and reliable.
- **Approximate date + category**: browse a **narrow (1–4 week)** range with a
  category.
- **Only a topic/keywords**: do **not** discover here. Use a keyword-capable
  skill first (`$cx-pubmed-search`, `$cx-europepmc-search`, `$cx-openalex-search`,
  `$cx-arxiv-search`) to find DOIs, then return here for preprint metadata.

> Anti-pattern: never scan months/years and filter locally by keyword — it
> triggers thousands of calls, timeouts, and API blocks.

## Gates (ask before proceeding)

- **Terms notice**: on first use, tell the user to review the bioRxiv terms
  (https://api.biorxiv.org/, https://www.biorxiv.org/content/about-biorxiv) and
  to check each retrieved paper's own license; record the notice in provenance.
- **Network / install**: read-only public HTTP; be polite about rate limits. If
  you write helper code, run it via `uv run`, never bare `python3`.

## Workflow

1. **By DOI**: `https://api.biorxiv.org/details/biorxiv/<DOI>` (use `medrxiv` for
   medRxiv). Returns title, authors, date, category, version, and abstract.
2. **By date + category**:
   `https://api.biorxiv.org/details/biorxiv/<YYYY-MM-DD>/<YYYY-MM-DD>/<cursor>`;
   page with the cursor and filter by category over a narrow window. Write
   responses to a file and parse them.
3. **Report** each preprint with title, DOI, date, category, and URL; note the
   version.
4. **Provenance & review**: record DOIs/queries with `$science-provenance`; check
   claims with `$science-review`.

## Boundaries

- Preprints are **not peer-reviewed**; flag that and prefer the published version
  when one exists (check for a published-DOI link).
- Cite only DOIs actually returned; never invent DOIs or abstracts.
- Respect each preprint's individual license before reproducing content.
