---
name: ols-search
description: Search EMBL-EBI Ontology Lookup Service (OLS) for biomedical ontology terms, definitions, and hierarchies across 250+ ontologies (GO, DOID, HP, UBERON, CL). Use for term search, term details, or navigating parents/children/ancestors. Public API, no credential needed.
license: Apache-2.0
---

# Ols Search (Codex-native)

Codex-native adaptation of Google DeepMind's `embl-ebi-ols` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- OLS4 API `https://www.ebi.ac.uk/ols4/api` (docs at `/ols4/api-docs`)

## Workflow

1. Search a term with `/ols4/api/search?q=<term>` (optionally scope by `ontology=`).
2. Fetch details and navigate the hierarchy (parents, children, ancestors) via the term IRI endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Always report the ontology and term IRI/CURIE (e.g. `GO:0006915`); labels alone are ambiguous.
- Cite only terms actually returned.
