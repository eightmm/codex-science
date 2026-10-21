---
name: pymol-visualize
description: "Visualize, analyze, and render protein/molecular structures with PyMOL: images, structural alignment/superposition, distance/contact measurement, binding-site highlighting, and coloring by B-factor/pLDDT. Not for docking, MD, or sequence-only analysis. Local tool."
license: Apache-2.0
---

# Pymol Visualize (Codex-native)

Codex-native adaptation of Google DeepMind's `pymol` skill ([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0). Uses the public API directly through Codex's own tools.

## Decision contract

Define whether the deliverable is a rendering or a structural measurement, the structure identity/source, comparison set, selections, alignment reference, and intended claim. Record claim IDs and a falsifier for any measurement-based conclusion. Visualization is descriptive; it cannot validate a model or support inference beyond the input coordinates.

## Workflow

### Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

### Endpoints

- PyMOL (open-source) run locally

1. Confirm a structure file is available (fetch via `$cx-pdb-search` or `$cx-alphafold-structure-analysis`). Record identifier, source, chain/state, and whether coordinates are experimental or predicted.
2. Drive PyMOL with a script (load, select, color, orient, ray, png); ask before installing PyMOL and run it via `uv run`. Pin the tool version and save the script, settings, input identity, and output path.
3. For alignment or distances, prespecify atom selections and reference; report units, atom sets, missing atoms, and alternate alignments where interpretation depends on them. Verify selections and measured values against the loaded structure.
4. Preserve input and derived image/measurement separately. **Provenance & review**: record queries, endpoints, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Outputs

Return normalized structure identity, source and version, PyMOL script/config, selections, measured values with units when applicable, rendered file paths, validation status, exclusions, limitations, claim IDs with supported/contradicted/inconclusive/unavailable status, and smallest falsifiable next action. Hash artifacts through `$science-provenance`.

## Boundaries

This renders/analyzes existing coordinates; it does not dock or simulate. State the source and confidence of the structure (experimental vs predicted; pLDDT lives in the B-factor column). A rendered view is not an independent validation. Coordinate provenance, missing residues, alignment choice, and visual selection can change interpretation; expose them. Stop if the requested conclusion needs unsupported structural evidence.
