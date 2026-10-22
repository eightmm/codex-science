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
sequence or structural query, and evidence cutoff. Distinguish entry, polymer
entity, chain/instance, and assembly identifiers. The target is experimentally
determined structure; do not mix predicted models into that set. Define
acceptable experimental method and resolution/validation evidence for the
intended interpretation. A PDB record's metadata is not itself the underlying
experimental evidence or proof of biological function.

## Reference usage

Read [references/pdb-record-evidence.md](references/pdb-record-evidence.md) before
classifying structure claims, comparing methods or validation, mapping chains
and assemblies, handling obsolete/replaced entries, or interpreting empty or
truncated search results.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the RCSB usage policy
   (https://www.rcsb.org/pages/usage-policy) and record the notice in
   provenance. Public HTTP is read-only; respect rate limits. Ask before large
   coordinate downloads.
2. Confirm the route: use this skill for experimentally determined structures
   and metadata, including sequence/structure similarity, ligand, or attribute
   searches. For predicted models use `$cx-alphafold-structure-analysis`, for
   file-based structural homologs use `$cx-foldseek-structural-search`, and
   for accession annotation use `$cx-uniprot-search`; record the selected
   scope. Prefer a short `uv run` script or an HTTP fetch tool; if helper code
   is needed, run it with `uv run`, never bare `python3`.
3. Define target entity, organism, intended inference, method/resolution
   criteria, and query. Discover attributes before an attribute query; name the
   chosen field and record the exact decision threshold and exclusions.
4. Search first with `science_search_pdb` (`query`, `limit` 1–10, default 5;
   returns PDB ID, score and URL). For advanced searches use Search API
   `https://search.rcsb.org/rcsbsearch/v2/query` (POST JSON, set `return_type`
   to `entry`, `polymer_entity`, `assembly`, etc.). Fetch metadata from
   `https://data.rcsb.org/rest/v1/core/entry/<PDB_ID>` (also
   `polymer_entity`, `nonpolymer_entity`) and coordinates from
   `https://files.rcsb.org/download/<PDB_ID>.cif`. Record query JSON, endpoint,
   access time, response release/update, return type and pagination. Write
   large responses to a file and parse with `jq` or a short `uv run` script.
5. **Verify/check:** validate IDs, entry status, response shape and
   completeness; bound pages/retries and mark failed or truncated retrievals
   unavailable. Resolve entity-to-chain/instance and assembly mapping, plus
   obsolete/replaced identifiers, before treating matches as the same target.
   Record result count and exclusions with reasons.
6. Assess each claim from the record's experimental method, resolution and
   validation report (including R-free when relevant), associated experimental
   data and chain coverage. Keep experimental observations distinct from
   deposition metadata and downstream structural interpretation. Compare a
   known positive entry and a negative query when feasible; record claim status,
   metrics and control outcomes.
7. Explain the query in plain language. Vary synonyms, sequence/query
   thresholds, taxonomy and filters; record
   whether candidate identity, method, resolution or conclusion changes. Report
   top structures with title, method, resolution, organism, ligand and URL;
   distinguish unresolved residues and biological assembly assumptions. Save
   query, endpoints, PDB IDs, coordinate hashes and exclusions with
   `$science-provenance`; use `$science-review` before material structural
   interpretation.
8. For structural homolog search, download the selected `.cif` coordinate file
   and pass it to `$cx-foldseek-structural-search`; retain its file hash and
   mapping assumptions.

## Outputs

Return one `pdb-structure-evidence-v1` record with these required fields:
normalized query and entity assumptions (`normalized_query`); an evidence
table with PDB ID, entry/entity/chain/assembly scope, title, method,
resolution/R-free when reported, validation, organism, ligand, URL and
inclusion/exclusion reason (`records`); claim IDs, claim class and status from
supported, contradicted, inconclusive or unavailable (`claims`); exact query,
release/version and access time (`source_snapshot`); artifact hashes and
pagination (`artifact_hashes` and `pagination`); uncertainty (`uncertainty`),
missing-coordinate and applicability limits (`limitations`); the smallest next
structural check (`next_check`); and provenance/review receipts when required
(`provenance_receipt` and `review_receipt`).

## Boundaries

- Cite only returned PDB IDs and metadata; never invent IDs or values.
- Experimental method and resolution bound the structural detail supported;
  missing residues/loops are common and do not imply a complete structure.
- Keep experimental structures separate from predicted models. A deposited
  assembly or ligand pose alone does not establish biological assembly or
  functional state. Stop when entity/chain mapping changes interpretation.
- Empty results mean no match for the query and source snapshot, not absence.
  Preserve API errors and truncation as unavailable.
- Respect the RCSB usage policy and redistribution terms. `$science-review` is
  mandatory for material structural or mechanistic conclusions.
