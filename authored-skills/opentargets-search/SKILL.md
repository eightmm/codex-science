---
name: opentargets-search
description: "Query the Open Targets Platform for target-disease associations, tractability/safety, genetic/omics evidence, and known drugs, for therapeutic target identification. Public GraphQL API, no credential needed."
license: Apache-2.0
---

# Opentargets Search (Codex-native)

Codex-native adaptation of Google DeepMind's `opentargets-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- Open Targets GraphQL `https://api.platform.opentargets.org/api/v4/graphql`

## Workflow

1. POST a GraphQL query for a target (Ensembl gene id) or disease (EFO id) and request association scores and evidence.
2. Resolve identifiers first (gene via `$cx-ensembl-search`, disease via `$cx-ols-search`).
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Association scores are aggregated evidence, not proof of causation or clinical validity.
- Cite only targets/diseases/drugs actually returned.
