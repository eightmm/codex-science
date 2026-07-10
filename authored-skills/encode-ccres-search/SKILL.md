---
name: encode-ccres-search
description: Query the ENCODE Registry of candidate cis-Regulatory Elements (cCREs) via the SCREEN GraphQL API, and ENCODE experiments/files via the ENCODE Portal REST API, across human cell types. Public APIs, no credential needed.
license: Apache-2.0
---

# Encode Ccres Search (Codex-native)

Codex-native adaptation of Google DeepMind's `encode-ccres-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- SCREEN GraphQL `https://factorbook.api.wenglab.org/graphql`
- ENCODE Portal REST `https://www.encodeproject.org/` (append `?format=json`)

## Workflow

1. For regulatory annotations, query cCREs by region/cell type via the SCREEN GraphQL endpoint.
2. For raw experimental data (ChIP-seq peaks, etc.), query the ENCODE Portal REST search with `?format=json` and restrict fields.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the genome assembly and biosample/cell type; regulatory calls are cell-type specific.
- Cite only ENCODE accessions actually returned.
