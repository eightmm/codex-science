---
name: string-ppi-search
description: "Query STRING for protein-protein interactions, interaction confidence/evidence, interaction partners, and functional enrichment. Use for PPI networks and enrichment of a protein set. Public API, no credential needed."
license: Apache-2.0
---

# String Ppi Search (Codex-native)

Codex-native adaptation of Google DeepMind's `string-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- STRING API `https://string-db.org/api` (e.g. `json/network`, `json/interaction_partners`, `json/enrichment`)

## Workflow

Resolve a protein first with `science_search_string`; use STRING directly for
species-constrained networks, partners, enrichment, and multi-protein queries.

1. Map identifiers first (`/json/get_string_ids`), then request the network/partners with a `species` id and a `required_score` threshold.
2. For enrichment, POST the identifier set to `/json/enrichment`.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the species and confidence threshold; STRING combines predicted and experimental evidence.
- Interactions include predictions; distinguish evidence channels. Cite only ids actually returned.
