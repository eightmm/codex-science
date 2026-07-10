---
name: interpro-search
description: "Identify protein domains, families, and sites; find proteins sharing a domain/family; explore species distribution; and get domain architectures via InterPro (integrating Pfam, CDD, and more). Public API, no credential needed."
license: Apache-2.0
---

# Interpro Search (Codex-native)

Codex-native adaptation of Google DeepMind's `interpro-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- InterPro API `https://www.ebi.ac.uk/interpro/api/`

## Workflow

Search InterPro entries first with `science_search_interpro`; use the direct API
for protein/structure/taxonomy joins and pagination.

1. Look up an entry (`/entry/interpro/<IPR>`) or the domains of a protein (`/entry/all/protein/uniprot/<ACC>`).
2. Find members of a family or proteins with a domain via the entry->protein relationship endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the member database (Pfam, CDD, etc.) behind each InterPro entry.
- Cite only InterPro/member accessions actually returned.
