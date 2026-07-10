---
name: pubchem-search
description: Query PubChem by name, CID, or SMILES; retrieve properties; run similarity/substructure searches; and get bioactivity. Use for cheminformatics on a specific chemical, drug, or molecule. Public PUG-REST API, no credential needed.
license: Apache-2.0
---

# Pubchem Search (Codex-native)

Codex-native adaptation of Google DeepMind's `pubchem-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- PubChem PUG-REST `https://pubchem.ncbi.nlm.nih.gov/rest/pug`

## Workflow

1. Resolve name/SMILES to a CID (`/compound/name/<name>/cids/JSON`), then fetch properties (`/compound/cid/<cid>/property/<props>/JSON`).
2. For similarity/substructure, use the `/compound/fastsimilarity_2d` or `/fastsubstructure` endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the CID and canonical/isomeric SMILES; a name can map to multiple CIDs (salts, stereoisomers).
- Cite only CIDs actually returned; never invent structures or properties.
