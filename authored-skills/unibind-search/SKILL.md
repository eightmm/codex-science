---
name: unibind-search
description: "Query UniBind for experimentally validated transcription-factor binding sites: retrieve TF-DNA datasets, download binding-site coordinates (BED/FASTA), and list datasets by species, cell line, or TF. Public API, no credential needed."
license: Apache-2.0
---

# Unibind Search (Codex-native)

Codex-native adaptation of Google DeepMind's `unibind-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- UniBind API `https://unibind.uio.no/api/v1/`

## Workflow

1. List datasets filtered by species/cell line/TF, then download the binding-site coordinates (BED/FASTA) for local analysis.
2. Report the TF, cell line, and dataset provenance.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- State the genome assembly of the coordinates; UniBind sites are experimentally derived, not motif predictions.
- Cite only datasets actually returned.
