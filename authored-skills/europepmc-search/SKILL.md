---
name: europepmc-search
description: Search Europe PMC for life-science literature and retrieve abstracts, citations, and open-access full text (XML/plain text) by PMCID. Use when the user wants broad biomedical literature discovery or open-access full text. Public API, no credential needed.
license: Apache-2.0
---

# Europe PMC Search (Codex-native)

Codex-native adaptation of Google DeepMind's `literature-search-europepmc` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public Europe PMC REST API directly.

## Gates (ask before proceeding)

- **Terms notice**: on first use, tell the user to review the Europe PMC terms
  (https://europepmc.org/) and to check each retrieved paper's own license;
  record the notice in provenance.
- **Network / install**: read-only public HTTP; keep to ~1 request/second. If you
  write helper code, run it via `uv run`, never bare `python3`.

## Workflow

1. **Search**:
   `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=<n>`.
   Europe PMC covers 40M+ abstracts across many sources (PubMed, PMC, preprints,
   patents). Use its query syntax (fielded terms, `AUTH:`, `PUB_YEAR:`, etc.).
2. **For full text**, restrict to open access (append `OPEN_ACCESS:y` to the
   query) and fetch by PMCID:
   `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC<ID>/fullTextXML`. Only
   open-access articles have retrievable full text.
3. **Citations / references** are available via the
   `.../MED/<PMID>/citations` and `.../references` endpoints when needed.
4. Write responses to a file and parse them; do not dump large XML to stdout.
5. **Report** each kept article with title, id (PMID/PMCID/DOI), source, year,
   one-line relevance, and URL. **List the URLs of every paper used.**
6. **Provenance & review**: record queries and cited ids with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Cite only ids actually returned; never invent PMIDs/PMCIDs/DOIs or abstracts.
- Full text exists only for open-access items; respect each article's license
  before reproducing content.
- Search results are references, not clinical advice.
