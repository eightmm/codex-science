---
name: uniprot-search
description: Search UniProtKB for proteins by name, gene, organism, or keyword and retrieve accessions plus functional annotation. Use when the user wants protein metadata, function, sequence, or identifier mapping. Uses the plugin's built-in read-only UniProt MCP tool for discovery — no credential or install needed.
license: Apache-2.0
---

# UniProt Protein Search (Codex-native)

Codex-native protein search wired to this plugin's built-in read-only MCP tool.
Inspired by Google DeepMind's `uniprot-database`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## How to run

1. **Search** with the plugin MCP tool `science_search_uniprot`:
   - arguments: `query` (protein/gene/organism/keyword, ≤500 chars; UniProt query
     syntax like `gene:TP53 AND organism_id:9606` works), `limit` (1–10,
     default 5).
   - returns a JSON list of `{id, title, url}` — `id` is the **primary
     accession**, `title` the recommended protein name, `url` the entry page.
2. **Disambiguate**: if several accessions match, prefer the reviewed
   (Swiss-Prot) canonical entry for the intended organism; state which you chose.
3. **Fetch details** for a kept accession from the UniProt REST API, e.g.
   `https://rest.uniprot.org/uniprotkb/<ACC>.json` (or `.txt`/`.fasta`) for
   function, subcellular location, domains/features, cross-references, and
   sequence. Ask before large batch fetches.
4. **Report** the accession, protein and gene names, organism, and the requested
   annotation, with the entry URL.
5. **Hand off** cleanly: for 3D structure of an accession use
   `$cx-alphafold-structure-analysis`; for structural homologs use
   `$cx-foldseek-structural-search`.
6. **Provenance & review**: record queries, tool, and cited accessions with
   `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Cite only accessions actually returned by the tool; never invent accessions or
  annotation. Distinguish reviewed (Swiss-Prot) from unreviewed (TrEMBL) entries.
- Report the organism explicitly — gene names are ambiguous across species.
- This tool searches metadata; it does not align sequences or predict structure.
