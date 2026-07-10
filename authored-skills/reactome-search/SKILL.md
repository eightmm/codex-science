---
name: reactome-search
description: Query Reactome Content and Analysis Services: pathway enrichment of a gene list, identifier mapping, reaction participants, pathway hierarchy, and knowledgebase search. Use for pathway analysis and enrichment. Public API, no credential needed.
license: Apache-2.0
---

# Reactome Search (Codex-native)

Codex-native adaptation of Google DeepMind's `reactome-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- Reactome ContentService `https://reactome.org/ContentService`
- Reactome AnalysisService `https://reactome.org/AnalysisService`

## Workflow

1. For enrichment, POST the identifier list to `/AnalysisService/identifiers/` and read results by token.
2. For content, query pathways/reactions/participants via the ContentService endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the species and the analysis token; enrichment p-values depend on the background.
- List not-found/unmapped identifiers honestly; cite only stable ids actually returned.
