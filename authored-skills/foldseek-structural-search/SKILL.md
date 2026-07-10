---
name: foldseek-structural-search
description: "Find structurally similar proteins by submitting a 3D coordinate file (.pdb, .cif, or .mmcif) to the Foldseek web API and search databases such as PDB, AlphaFold, CATH, and MGnify. Use ONLY when the user provides a physical structure file and wants structural homologs. Public data, no credential needed."
license: Apache-2.0
---

# Foldseek Structural Search (Codex-native)

Codex-native adaptation of Google DeepMind's `foldseek-structural-search` skill.

> Attribution: adapted from
> [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
> (Apache-2.0 + CC-BY-4.0). Foldseek: https://search.foldseek.com/search and
> https://github.com/steineggerlab/foldseek

## Hard requirement

Foldseek searches by **3D shape only**. It cannot search by sequence, protein
name, or accession. If the user gives anything other than a path to a `.pdb`,
`.cif`, or `.mmcif` file, **halt** and tell them to obtain a structure first
(e.g. via `$cx-alphafold-structure-analysis` for a UniProt ID).

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  Foldseek terms, and record the notice in provenance.
- **Network / install**: submission is read-only public HTTP. Ask before
  installing any client package; run Python via `uv run`, not bare `python3`.

## Workflow

1. **Validate input.** Confirm the file exists and ends in `.pdb`, `.cif`, or
   `.mmcif`. Otherwise halt (see hard requirement).
2. **Validate databases.** Default to the standard set. If the user names
   databases, allow only: `afdb50`, `afdb-swissprot`, `pdb100`, `BFVD`,
   `mgnify_esm30`, `cath50`, `gmgcl_id`, `bfmd`, `afdb-proteome`. Any other
   database → halt and show this allowlist.
3. **Submit** the structure to the Foldseek API, poll until the job completes,
   and save two outputs under the user's project with descriptive names:
   `<name>_foldseek_results.json` (full payload) and `<name>_foldseek_results.md`
   (a Markdown hits table).
4. **Read the `.md` table** for your summary; do not hand-parse the raw JSON or
   the 3D coordinates.
5. **Interpret the top 3-5 meaningful matches**:
   - **Prob** near 1.0 → high confidence of a true structural homolog.
   - **Q-Cov** high → the match covers most of the query shape, not just a
     local motif.
   - **E-value / Seq identity** → evolutionary context.
6. **Functional synthesis**: report the specific protein names/functions of the
   top homologs (from the target annotations) and summarize the *variety* of
   families/functions across the hit list.
7. Tell the user where both output files are so later steps can reuse them.
8. **Provenance & review**: record the query file, databases, and outputs with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Structural similarity suggests, but does not prove, functional or evolutionary
  relationship; state confidence honestly.
- On API error or missing file, report it plainly and ask the user to verify the
  path — do not fabricate results.
