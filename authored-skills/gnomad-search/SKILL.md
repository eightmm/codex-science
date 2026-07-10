---
name: gnomad-search
description: "Query gnomAD for variant allele frequency/rarity, gene constraint metrics (pLI, LOEUF), variants in a region or gene, and structural variants. Use to assess variant rarity or loss-of-function intolerance. Not for individual patient genomes or somatic cancer variants. Public GraphQL API, no credential needed."
license: Apache-2.0
---

# Gnomad Search (Codex-native)

Codex-native adaptation of Google DeepMind's `gnomad-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- gnomAD GraphQL `https://gnomad.broadinstitute.org/api`

## Workflow

1. POST a GraphQL query for a variant (by ID/rsID), a gene, or a region; request the gnomAD version/dataset explicitly.
2. For constraint, request `gnomad_constraint` fields (pLI, LOEUF, oe) on the gene.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the gnomAD dataset version and population; allele frequency is population-dependent.
- Population frequency is not clinical classification; cite only variants actually returned.
