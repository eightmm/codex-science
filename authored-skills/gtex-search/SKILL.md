---
name: gtex-search
description: Retrieve quantitative RNA expression and variant eQTL data from GTEx across 54 non-diseased tissue sites. Use for tissue expression profiles or eQTL lookups. Public API, no credential needed.
license: Apache-2.0
---

# Gtex Search (Codex-native)

Codex-native adaptation of Google DeepMind's `gtex-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- GTEx API `https://gtexportal.org/api/v2`

## Workflow

1. Query gene expression by tissue via the expression endpoints (resolve the GENCODE/Ensembl gene id first).
2. Query eQTLs for a gene/variant/tissue via the association endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the GTEx release version and tissue; expression is tissue- and sample-dependent.
- Cite only genes/variants actually returned.
