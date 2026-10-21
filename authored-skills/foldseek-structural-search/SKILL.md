---
name: foldseek-structural-search
description: "Find structurally similar proteins by submitting a 3D coordinate file (.pdb, .cif, or .mmcif) to the Foldseek web API and search databases such as PDB, AlphaFold, CATH, and MGnify. Use ONLY when the user provides a physical structure file and wants structural homologs. Public data, no credential needed."
license: Apache-2.0
---

# Foldseek Structural Search (Codex-native)

Codex-native adaptation of Google DeepMind's `foldseek-structural-search` skill.

> Attribution: adapted from [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills) (Apache-2.0 + CC-BY-4.0). Foldseek: https://search.foldseek.com/search and https://github.com/steineggerlab/foldseek

## Decision contract

Identify the query structure, biological state/chain, search objective, database set, evidence cutoff, and whether the desired claim is structural similarity, homology, or function. Assign claim IDs and state what independent evidence could falsify stronger interpretations. The query must be a physical coordinate file; do not substitute sequence or accession search.

## Workflow

### Hard requirement

Foldseek searches by **3D shape only**. It cannot search by sequence, protein name, or accession. If the user gives anything other than a path to a `.pdb`, `.cif`, or `.mmcif` file, **halt** and tell them to obtain a structure first (e.g. via `$cx-alphafold-structure-analysis` for a UniProt ID).

### Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the Foldseek terms, and record the notice in provenance.
- **Network / install**: submission is read-only public HTTP. Ask before installing any client package; run Python via `uv run`, not bare `python3`.

1. Validate the file exists and ends in `.pdb`, `.cif`, or `.mmcif`; record chain, model, and structure source. Otherwise halt.
2. Default to the standard database set. If the user names databases, allow only: `afdb50`, `afdb-swissprot`, `pdb100`, `BFVD`, `mgnify_esm30`, `cath50`, `gmgcl_id`, `bfmd`, `afdb-proteome`. Any other database → halt and show this allowlist.
3. Submit the structure to the Foldseek API, poll until the job completes, and save two outputs under the user's project with descriptive names: `<name>_foldseek_results.json` (full payload) and `<name>_foldseek_results.md` (a Markdown hits table). Preserve exact submitted parameters and job outcome.
4. Validate response shape, completion state, truncation, and returned-record count. Read the `.md` table for the summary; do not hand-parse the raw JSON or the 3D coordinates. Record returned records and excluded/filtered records with reasons; distinguish empty result from request failure.
5. Interpret the top 3-5 meaningful matches: `Prob` near 1.0 → high confidence of a true structural homolog; `Q-Cov` high → the match covers most of the query shape, not just a local motif; `E-value / Seq identity` → evolutionary context. Do not treat these fields as proof of function.
6. Report names/functions from target annotations and the variety of families/functions across the hit list. **Provenance & review**: record query file, databases, response and outputs with `$science-provenance`; check claims with `$science-review`.

## Outputs

Return normalized query/database choices, exact parameters and query time, a hits table with identifiers, metrics, annotation and returned/excluded status, claim IDs with supported/contradicted/inconclusive/unavailable status, uncertainty and limitations, and smallest falsifiable next action. Provide both saved output paths and artifact hashes.

## Boundaries

Structural similarity suggests, but does not prove, functional or evolutionary relationship; state confidence honestly. On API error, malformed/truncated response, or missing file, report it plainly and do not fabricate results. Similarity alone cannot establish orthology or function. Never claim search completeness from one database/query.
