---
name: pdb-search
description: Search and retrieve experimentally-determined 3D biomolecular structures from the RCSB Protein Data Bank by sequence, structure, ligand, or attribute, and fetch entry metadata or coordinate files. Use when the user wants experimental structures (X-ray, cryo-EM, NMR), not predicted models. Public REST API, no credential needed.
license: Apache-2.0
---

# RCSB Protein Data Bank Search (Codex-native)

Codex-native adaptation of Google DeepMind's `pdb-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public RCSB APIs directly through Codex's own tools.

## When to use / not use

- **Use** for **experimentally-determined** structures and their metadata
  (proteins, nucleic acids, bound ligands), or to search by sequence/structure
  similarity, ligand, or attribute.
- **Do not use** for predicted models (use `$cx-alphafold-structure-analysis`),
  structural-homolog search from a file (use `$cx-foldseek-structural-search`),
  or protein annotation from an accession (use `$cx-uniprot-search`).

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the RCSB
  usage policy (https://www.rcsb.org/pages/usage-policy) and record the notice in
  provenance.
- **Network / install**: read-only public HTTP. Be polite about rate limits.
  Prefer a short `uv run` script or an HTTP fetch tool; if you write helper code,
  run it via `uv run`, never bare `python3`. Ask before large coordinate
  downloads.

## Workflow

1. **Pick the right endpoint**:
   - Search API: `https://search.rcsb.org/rcsbsearch/v2/query` (POST a JSON
     query; set `return_type` to `entry`, `polymer_entity`, `assembly`, etc.).
   - Data API: `https://data.rcsb.org/rest/v1/core/entry/<PDB_ID>` for entry
     metadata (also `polymer_entity`, `nonpolymer_entity`).
   - Coordinates: `https://files.rcsb.org/download/<PDB_ID>.cif`.
2. **Discover attributes** before composing an attribute query — RCSB has many
   similar fields; choose the best match for the user's intent and say which.
3. **Run the query**, writing responses to a file rather than dumping large JSON
   to stdout; parse with `jq` or a short script.
4. **Explain the query** in plain language so the user can catch bad assumptions.
5. **Report** the top structures with PDB ID, title, method, **resolution**,
   organism, and bound ligands; link each entry.
6. **Interpret with the right concepts**: distinguish entity vs instance/chain vs
   assembly; note experimental method and resolution/R-free when assessing
   reliability; a deposited structure is not always the biological assembly.
7. **Hand off** cleanly: to search homologs, download the `.cif` then use
   `$cx-foldseek-structural-search`.
8. **Provenance & review**: record queries, endpoints, and cited PDB IDs with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Cite only PDB IDs actually returned; never invent IDs or metadata.
- Experimental resolution and method bound how much detail is trustworthy; state
  them. Missing residues/loops are common — do not assume completeness.
- These are experimental structures; keep them distinct from predicted models.
