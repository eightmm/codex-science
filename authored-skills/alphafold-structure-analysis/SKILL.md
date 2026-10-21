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

## Decision contract

Role: analyzer, with retrieval of the requested AlphaFold Database record.

Use when the user provides a UniProt accession (for example, `P04637`) and wants confidence metrics, disorder, or domain boundaries. Do not use when the user has only a protein/gene name or raw sequence (ask them to find the UniProt ID first), wants structural homolog search (use `$cx-foldseek-structural-search`), needs an experimental structure (use a PDB skill), or wants a new folding prediction. Record accession, canonical/isoform intent, requested analysis, claim IDs, evidence cutoff, and the limits of confidence-based inference.

## Workflow

1. On first use in a workspace, tell the user to review AFDB terms and record the notice in provenance. Fetching from AFDB is read-only public HTTP. Ask before installing any analysis package; run Python via `uv run`, not bare `python3`.
2. Fetch current model metadata first with `science_search_alphafold` using a canonical UniProt accession. Prefer its returned versioned URLs over guessing a model version.
3. Fetch the mmCIF model, Predicted Aligned Error (PAE) JSON, and entry metadata JSON. Preserve endpoint patterns: v6 example `https://alphafold.ebi.ac.uk/files/AF-<ACC>-F1-model_v6.cif` and matching `-predicted_aligned_error_v6.json`; metadata via `https://alphafold.ebi.ac.uk/api/prediction/<ACC>`. Save files under an absolute output folder in the user's project, rate-limited and polite. For very large proteins handle fragment fallback (`-F2`, ...). Record access time, returned version/URLs, hashes, and response validity.
4. Analyze pLDDT from the mmCIF B-factor column and metadata. Report global mean and fraction in each band: very low (<50), low (50-70), confident (70-90), very high (>90). Check residue numbering, missing values, and sequence coverage before calculating; retain missingness as missing.
5. Derive rigid-domain boundaries from PAE with a stated sliding-window heuristic; report domain count and residue ranges. Do not eyeball domains from coordinates. Synthesize fold confidence, disordered regions, domain layout, and supporting metrics.
6. Prominently relay if no canonical entry was found and an isoform/fragment was used, or the protein is very large (>2700 aa). If largely disordered (high <50 fraction / no rigid domains), warn against whole-protein downstream analysis (Foldseek, docking); if small ordered domains exist, advise restricting analysis to those residue ranges. Remind the user that per-residue pLDDT lives in the mmCIF B-factor column.
7. Record accession, file versions, outputs, exclusions, and hashes with `$science-provenance`; use `$science-review` before material structural conclusions.
If retrieval or analysis fails, classify the failure, preserve it, do not retry invalid identifiers, and bound transient retries. Retain cancellation and failure logs.

## Outputs

Return a machine-readable evidence table with claim ID/status (`supported`, `contradicted`, `inconclusive`, or `unavailable`), accession and model version, canonical/isoform/fragment scope, fetched files and hashes, residue coverage, pLDDT summaries, PAE method/domain ranges, missingness, and limitations. Include excluded or unavailable records and reasons, uncertainty, the concise interpretation, and the smallest falsifiable next action.

## Boundaries

pLDDT and PAE are confidence heuristics, not correctness guarantees; a confident fold can still be biologically wrong. AFDB re-releases change coordinates and metrics, so report model version explicitly. Do not infer experimental structure, function, disorder mechanism, or clinical relevance from these metrics alone. Stop if the accession is ambiguous or response data fail validation; report unavailable/inconclusive rather than substituting a guessed identifier or version.
