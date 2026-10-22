---
name: pymol-visualize
description: "Visualize, analyze, and render protein/molecular structures with PyMOL: images, structural alignment/superposition, distance/contact measurement, binding-site highlighting, and coloring by B-factor/pLDDT. Not for docking, MD, or sequence-only analysis. Local tool."
license: Apache-2.0
---

# Pymol Visualize (Codex-native)

Codex-native adaptation of Google DeepMind's `pymol` skill ([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0). Uses the public API directly through Codex's own tools.

## Decision contract

Define whether the deliverable is a rendered image or a structural measurement; identify structure source, comparison set, selections, alignment reference, intended claim, and claim IDs. State a falsifier for any measurement-based conclusion. Classify rendered appearance separately from coordinate-derived measurements and from experimental or mechanistic claims. Visualization is descriptive and cannot validate a model or support inference beyond the input coordinates.

## Reference usage

Read [references/pymol-rendering-and-measurement.md](references/pymol-rendering-and-measurement.md) before rendering a claim-bearing figure, measuring or comparing structures, coloring by confidence/B-factor, or interpreting visible contacts. It specifies reproducible scene records, visual controls, sensitivity checks, and the evidence boundary of an image.

## Workflow

1. **Gate:** On first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. For network access use read-only public access, respect rate limits, write large responses to a file and parse them, run helper code via `uv run` (never bare `python3`), and ask before installs or large downloads. Record notice and any approval or stop decision.
2. Define rendering or measurement claim; proceed only when structure identity/source, comparison set, intended use, atom selections, alignment reference, and any falsifier are specified. Record the claim contract and evidence cutoff.
3. Obtain or select the structure using `$cx-pdb-search` or `$cx-alphafold-structure-analysis` when needed; proceed only when identifier, source/release, chain/state, and experimental versus predicted provenance are recorded. Keep private structures local and record source terms notice and input hash.
4. Use the local open-source PyMOL endpoint and public API through Codex's own tools. If PyMOL installation is needed, ask first and run via `uv run`. Pin the tool version; script `load`, `select`, `color`, `orient`, `ray`, and `png` choices. Record the script, settings, selections, input identity, version, and output path.
5. For alignment or distance measurements, prespecify atom selections and reference; proceed only when selected atoms resolve and units are explicit. Verify selections and measured values against the loaded structure; record atom sets, missing atoms, alternate alignments, and discrepancies.
6. Inspect the scene for selection completeness, clipping, color scale meaning/range, and cartoon smoothing; compare with an alternate view or unsmoothed/unclipped control when the claim depends on appearance. Record the control and any visual changes that alter interpretation.
7. Vary plausible chain/model/alternate-location selections, alignment reference, clipping, color limits, and cartoon smoothing when relevant; downgrade a claim if the result depends on an unreported visual or selection choice. Record sensitivity and uncertainty. Preserve input and derived image/measurement separately.
8. Record queries, endpoints, cited identifiers, script/configuration, and hashes with `$science-provenance`; check claims with `$science-review` before presenting. Report supported, contradicted, inconclusive, or unavailable status and smallest falsifiable next action.

## Outputs

Return `pymol-visualization-evidence-v1` with required fields: claim identifier (`claim_id`); claim class (`claim_class`: rendered appearance, coordinate measurement, or comparison); normalized structure/source/release identity and provenance (`structure_id`, `source`, `release`, `structure_provenance`); input hash (`input_hash`); PyMOL version and script/configuration (`pymol_version`, `script`, `settings`); selections and alignment reference (`selections`, `alignment_reference`); rendered paths (`rendered_paths`); measured values and units when applicable (`measurements`); selection/scene validation (`validation`); visual controls and sensitivity (`controls`, `sensitivity`); exclusions (`exclusions`); claim status (`status`: supported, contradicted, inconclusive, or unavailable); uncertainty and limitations (`uncertainty`, `limitations`); and smallest falsifiable next action (`next_action`). Hash artifacts through `$science-provenance`.

## Boundaries

This renders/analyzes existing coordinates; it does not dock or simulate. State the source and confidence of the structure (experimental vs predicted; pLDDT lives in the B-factor column). A rendered view is not an independent validation. Coordinate provenance, missing residues, alignment choice, and visual selection can change interpretation; expose them. Stop if the requested conclusion needs unsupported structural evidence.

## Source basis

This workflow uses PyMOL as a molecular graphics and coordinate-analysis system; scene and measurement claims remain conditional on the supplied structure and reproducible selections. The structure metadata conventions follow wwPDB/PDBx/mmCIF. Predicted-model confidence fields are reported according to their source model's documentation, not reinterpreted as experimental B-factors.
