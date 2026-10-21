---
name: uniprot-search
description: "Search UniProtKB for proteins by name, gene, organism, or keyword and retrieve accessions plus functional annotation. Use when the user wants protein metadata, function, sequence, or identifier mapping. Uses the plugin's built-in read-only UniProt MCP tool for discovery — no credential or install needed."
license: Apache-2.0
---

# UniProt Protein Search (Codex-native)

Codex-native protein search wired to this plugin's built-in read-only MCP tool.
Inspired by Google DeepMind's `uniprot-database`
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0);
the MCP integration is Codex Science's own.

## Decision contract

Return source-grounded UniProtKB records for the requested protein, gene,
organism, sequence, or annotation question. Record the organism/taxon, query,
identifier type, evidence cutoff, and requested fields. Treat gene symbols as
species-dependent and resolve ambiguous names before selecting an accession.
Do not infer function beyond the retrieved record or the evidence supporting
its annotation.

## Workflow

1. Normalize the query and include an organism or taxon where possible. The
   built-in `science_search_uniprot` accepts `query` (1–500 characters) and
   optional `limit` (1–10, default 5); it returns `{id,title,url}` records,
   where `id` is a primary accession. This connector is an initial search
   option, not a replacement for direct source access. UniProt query syntax such as `gene:TP53 AND organism_id:9606` works in both paths.
2. Search with the MCP tool or UniProt REST API. For direct access, use
   `https://rest.uniprot.org/uniprotkb/search` with URL-encoded query, `format=json`,
   and `size`; fetch a selected record at
   `https://rest.uniprot.org/uniprotkb/<ACC>.json` (or `.txt`/`.fasta`).
   Preserve the exact serialized query, endpoint, access time, response status,
   result count, page/continuation state, and any release/update information
   reported by the response. Follow pagination only to a declared bounded limit.
3. Validate response structure and accession format; detect API errors,
   malformed records, and truncation before interpreting. Record returned
   accessions and excluded candidates with reasons. Empty results mean no
   matching records were returned for this query, not that the protein or
   function is absent.
4. Disambiguate candidates by organism and reviewed status. Prefer a reviewed
   (Swiss-Prot) canonical entry only when it matches the requested entity;
   distinguish reviewed from unreviewed (TrEMBL) records. Fetch details only
   for selected accessions; ask before large batch fetches.
5. Report accession, protein and gene names, organism, reviewed status, requested
   annotation, source URL, and null or missing fields explicitly. Keep sequence,
   domains/features, subcellular location, and cross-references tied to the
   selected accession. For 3D structure use `$cx-alphafold-structure-analysis`;
   for structural homologs use `$cx-foldseek-structural-search`.
6. Save query and response provenance with `$science-provenance`; use
   `$science-review` before presenting material functional claims.

## Outputs

Provide normalized query and assumptions; an evidence table with accession,
name, organism, reviewed status, fields, URL, and inclusion/exclusion reason;
claim IDs marked supported, contradicted, inconclusive, or unavailable;
query/release/access-time and pagination details; uncertainty, limitations, and
the smallest next lookup that could resolve ambiguity. Preserve response or
record artifacts and hashes through `$science-provenance`.

## Boundaries

- Cite only accessions and annotations actually returned. Never invent records.
- Report organism explicitly; a gene name alone does not establish identity.
- A reviewed entry is curated status, not proof that every annotation is
  experimentally established. Preserve evidence qualifiers and missingness.
- This skill searches metadata; it does not align sequences or predict structure.
- Stop when organism or accession ambiguity changes the conclusion. Keep failed
  or truncated responses unavailable, not negative. Respect source terms and
  redistribution restrictions; use only read-only public access. `$science-review`
  is mandatory for material function or mechanism claims.
