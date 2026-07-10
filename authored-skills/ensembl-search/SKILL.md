---
name: ensembl-search
description: "Resolve gene/transcript/protein IDs, fetch genomic or protein sequences, retrieve gene structure (exons), and predict variant consequences (VEP) via the Ensembl REST API. Use as an ID translator, sequence source, and variant-effect tool. Public API, no credential needed."
license: Apache-2.0
---

# Ensembl Search (Codex-native)

Codex-native adaptation of Google DeepMind's `ensembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- Ensembl REST `https://rest.ensembl.org` (GRCh37 at `https://grch37.rest.ensembl.org`)

## Workflow

1. Resolve IDs with `/lookup/id/<id>` or `/xrefs/symbol/<species>/<symbol>`; fetch sequence with `/sequence/id/<id>`.
2. Predict variant consequences with `/vep/<species>/hgvs/<hgvs>` or `/vep/<species>/region`.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- State the species and assembly (GRCh38 vs GRCh37) explicitly.
- Cite only Ensembl IDs actually returned; VEP predictions are computational.
