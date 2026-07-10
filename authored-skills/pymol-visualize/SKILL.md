---
name: pymol-visualize
description: "Visualize, analyze, and render protein/molecular structures with PyMOL: images, structural alignment/superposition, distance/contact measurement, binding-site highlighting, and coloring by B-factor/pLDDT. Not for docking, MD, or sequence-only analysis. Local tool."
license: Apache-2.0
---

# Pymol Visualize (Codex-native)

Codex-native adaptation of Google DeepMind's `pymol` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- PyMOL (open-source) run locally

## Workflow

1. Confirm a structure file is available (fetch via `$cx-pdb-search` or `$cx-alphafold-structure-analysis`).
2. Drive PyMOL with a script (load, select, color, orient, ray, png); ask before installing PyMOL and run it via `uv run`.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- This renders/analyzes existing coordinates; it does not dock or simulate.
- State the source and confidence of the structure (experimental vs predicted; pLDDT lives in the B-factor column).
