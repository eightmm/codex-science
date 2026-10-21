---
name: pdb-search
description: "Search and retrieve experimentally-determined 3D biomolecular structures from the RCSB Protein Data Bank by sequence, structure, ligand, or attribute, and fetch entry metadata or coordinate files. Use when the user wants experimental structures (X-ray, cryo-EM, NMR), not predicted models. Public REST API, no credential needed."
license: Apache-2.0
---

# RCSB Protein Data Bank Search (Codex-native)

Codex-native adaptation of Google DeepMind's `pdb-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public RCSB APIs directly through Codex's own tools.

## Decision contract

Specify the macromolecule/ligand, organism, requested structure evidence,
sequence or structural query if any, and evidence cutoff. Distinguish entry,
polymer entity, chain/instance, and assembly identifiers. The target evidence
is experimentally determined structure; do not mix predicted models into that
set. Define what structural resolution or method is adequate for the intended
interpretation.

## Workflow

1. **Use when:** retrieving experimentally-determined structures and metadata
   (proteins, nucleic acids, bound ligands), or searching by sequence/structure
   similarity, ligand, or attribute. **Do not use** for predicted models (use
   `$cx-alphafold-structure-analysis`), structural-homolog search from a file
   (use `$cx-foldseek-structural-search`), or protein annotation from an
   accession (use `$cx-uniprot-search`).
2. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the RCSB usage policy
   (https://www.rcsb.org/pages/usage-policy) and record the notice in provenance.
   Public HTTP is read-only; be polite about rate limits. Prefer a short
   `uv run` script or an HTTP fetch tool; if you write helper code, run it via
   `uv run`, never bare `python3`. Ask before large coordinate downloads.
3. Search first with `science_search_pdb` (`query`, `limit` 1–10, default 5),
   which returns PDB ID, score and URL. For advanced queries use Search API
   `https://search.rcsb.org/rcsbsearch/v2/query` (POST JSON; set `return_type`
   to `entry`, `polymer_entity`, `assembly`, etc.). Fetch metadata through Data
   API `https://data.rcsb.org/rest/v1/core/entry/<PDB_ID>` (also
   `polymer_entity`, `nonpolymer_entity`) and coordinates from
   `https://files.rcsb.org/download/<PDB_ID>.cif`.
4. Discover attributes before composing an attribute query: choose the best
   matching field and state it. Record query JSON, endpoint, return type,
   pagination, access time, response-reported release/update, result count, and
   exclusions. Write large responses to a file and parse with `jq` or a short
   `uv run` script. Validate IDs, status, response shape, and truncation; bound
   pages/retries, and preserve failed or incomplete retrieval as unavailable.
5. Explain the query in plain language. Report top structures with PDB ID, title,
   method, resolution, organism, bound ligands, and entry URL. Distinguish
   entity vs instance/chain vs assembly; note experimental method and
   resolution/R-free when assessing reliability; a deposited structure is not
   always the biological assembly. Missing residues/loops are common; do not
   assume completeness.
6. To search homologs, download the `.cif` then use
   `$cx-foldseek-structural-search`. Record queries, endpoints, cited PDB IDs,
   coordinate-file hashes, and exclusions with `$science-provenance`; use
   `$science-review` before material structural interpretation.

## Outputs

Return normalized query and entity assumptions; evidence table with PDB ID,
entry/entity/chain/assembly scope, title, method, resolution/R-free where
reported, organism, ligand, URL, and inclusion/exclusion reason; claim IDs
marked supported/contradicted/inconclusive/unavailable; query/release/access
time and artifact hashes; uncertainty, missing-coordinate and applicability
limits; and the smallest next structural check.

## Boundaries

- Cite only PDB IDs actually returned; never invent IDs or metadata.
- Experimental resolution and method bound trustworthy detail; state them.
  Missing residues/loops are common — do not assume completeness.
- Keep experimental structures distinct from predicted models. A deposited
  assembly or ligand pose does not by itself establish the biological assembly
  or functional state. Stop when entity/chain mapping changes the conclusion.
- Respect the RCSB usage policy and redistribution terms. `$science-review` is
  mandatory for material structural or mechanistic conclusions.
