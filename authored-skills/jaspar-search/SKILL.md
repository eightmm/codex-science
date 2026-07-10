---
name: jaspar-search
description: Retrieve transcription-factor binding profiles (PFMs/PWMs) from JASPAR, resolve gene symbols to JASPAR matrix IDs, and get TF metadata in multiple formats (MEME, TRANSFAC, PFM, JASPAR). Public API, no credential needed.
license: Apache-2.0
---

# Jaspar Search (Codex-native)

Codex-native adaptation of Google DeepMind's `jaspar-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- JASPAR API `https://jaspar.elixir.no/api/v1/`

## Workflow

1. Resolve a TF symbol to a matrix id via `/matrix/?search=<TF>`, then fetch `/matrix/<MA_ID>/` in the desired format.
2. Report the matrix id, TF name, collection, and version.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the JASPAR release/collection (e.g. CORE) and matrix version.
- Cite only matrix IDs actually returned.
