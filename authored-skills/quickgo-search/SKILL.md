---
name: quickgo-search
description: "Query QuickGO and the Evidence & Conclusion Ontology (ECO): map genes to GO biological processes, molecular functions, and cellular components; find genes for a GO term; and explore the GO hierarchy. Public API, no credential needed."
license: Apache-2.0
---

# Quickgo Search (Codex-native)

Codex-native adaptation of Google DeepMind's `quickgo-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- QuickGO API `https://www.ebi.ac.uk/QuickGO/api`

## Workflow

Search GO terms first with `science_search_quickgo`; use QuickGO directly for
annotations, evidence filters, and ontology traversal.

1. Look up GO annotations for a gene/protein (`/annotation/search?geneProductId=<ACC>`) or a GO term (`/ontology/go/terms/<GO_ID>`).
2. Navigate ancestors/descendants via the ontology relationship endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the GO id, aspect (BP/MF/CC), and evidence code; evidence quality varies.
- Cite only GO ids / accessions actually returned. For drug targets use `$cx-opentargets-search`.
