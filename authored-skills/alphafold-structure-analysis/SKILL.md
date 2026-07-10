---
name: alphafold-structure-analysis
description: "Retrieve an AlphaFold predicted structure from the AlphaFold Database for a given UniProt accession and analyze its confidence (pLDDT), intrinsically disordered regions, and rigid domain boundaries (PAE). Use when the user has a UniProt ID and wants structural confidence, disorder assessment, or domain layout. Public data, no credential needed."
license: Apache-2.0
---

# AlphaFold Database Fetch and Analyze (Codex-native)

Codex-native adaptation of Google DeepMind's
`alphafold-database-fetch-and-analyze` skill.

> Attribution: adapted from
> [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
> (Apache-2.0 + CC-BY-4.0). AFDB terms: https://alphafold.ebi.ac.uk/

## When to use / not use

- **Use** when the user provides a **UniProt accession** (e.g. `P04637`) and
  wants confidence metrics, disorder, or domain boundaries.
- **Do not use** when the user has only a protein/gene name or a raw sequence
  (ask them to find the UniProt ID first), wants to search structural homologs
  (use `$cx-foldseek-structural-search`), needs an experimental structure (use a
  PDB skill), or wants to run a new folding prediction.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the AFDB
  terms, and record the notice in provenance.
- **Network / install**: fetching from AFDB is read-only public HTTP. Ask before
  installing any analysis package; run Python via `uv run`, not bare `python3`.

## Workflow

Fetch current model metadata first with `science_search_alphafold` using a
canonical UniProt accession. Prefer its returned versioned URLs over guessing a
model version.

1. **Fetch the structure** for the UniProt ID from the AlphaFold Database:
   the mmCIF model, the Predicted Aligned Error (PAE) JSON, and the entry
   metadata JSON. Endpoint pattern (v6 example):
   `https://alphafold.ebi.ac.uk/files/AF-<ACC>-F1-model_v6.cif` and the matching
   `-predicted_aligned_error_v6.json`; entry metadata via the AFDB API
   `https://alphafold.ebi.ac.uk/api/prediction/<ACC>`. Save all files to an
   output folder under the user's project (absolute path), rate-limited and
   polite. For very large proteins handle fragment fallback (`-F2`, ...).
2. **Analyze pLDDT** from the per-residue confidence (embedded in the mmCIF
   B-factor column, and in metadata). Report the global mean and the fraction in
   each band: very low (<50), low (50-70), confident (70-90), very high (>90).
3. **Analyze domains / PAE.** Detect rigid domain boundaries with a
   sliding-window heuristic over the PAE matrix; report the number of distinct
   domains and their residue ranges. Do not eyeball domains from coordinates —
   derive them from PAE.
4. **Synthesize** one cohesive summary: overall fold confidence, disordered
   regions, and rigid-domain layout, plus supporting metrics.
5. **Mandatory warnings**:
   - If no canonical entry was found and an isoform/fragment was used, or the
     protein is very large (>2700 aa), relay that prominently.
   - If the protein is largely disordered (high <50 fraction / no rigid
     domains), warn against whole-protein downstream analysis (Foldseek,
     docking); if small ordered domains exist, advise restricting analysis to
     those residue ranges.
6. Remind the user that per-residue pLDDT lives in the mmCIF B-factor column.
7. **Provenance & review**: record the accession, file versions, and outputs
   with `$science-provenance`; check claims with `$science-review`.

## Boundaries

- pLDDT and PAE are confidence heuristics, not correctness guarantees; a
  confident fold can still be biologically wrong.
- Report the model version explicitly; AFDB re-releases change coordinates and
  metrics.
