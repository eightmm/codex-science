---
name: hpa-search
description: Retrieve protein expression levels and spatial/subcellular localisation from the Human Protein Atlas (HPA). Use for tissue/cell expression and localisation of a human protein. Public API, no credential needed.
license: Apache-2.0
---

# Hpa Search (Codex-native)

Codex-native adaptation of Google DeepMind's `human-protein-atlas-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- HPA entry JSON `https://www.proteinatlas.org/<ENSG_ID>.json`
- HPA search/download `https://www.proteinatlas.org/api/search_download.php` (columns + `format=json`)

## Workflow

1. Resolve the gene to its Ensembl gene id (use `$cx-ensembl-search`), then fetch the entry JSON.
2. Report tissue expression, subcellular location, and reliability/score fields.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- HPA expression is semi-quantitative with reliability scores; report the reliability, not just the level.
- Cite only genes actually returned.
