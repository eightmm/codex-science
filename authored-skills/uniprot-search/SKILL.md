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
Separate what the database record says from the underlying experimental
evidence; do not infer function beyond the record and evidence supporting its
annotation. Preserve evidence qualifiers and annotation provenance.

## Reference usage

Read [references/uniprot-record-evidence.md](references/uniprot-record-evidence.md) when
classifying annotation claims, mapping identifiers or isoforms, comparing
reviewed status, pinning a UniProt release, or interpreting an empty or
conflicted query result.

## Workflow

1. Normalize the query and include organism/taxon where possible; record
   identifier type, requested fields, evidence cutoff, and any unresolved
   ambiguity. A gene symbol alone does not identify a protein.
2. Search with `science_search_uniprot` (`query` 1–500 characters, optional
   `limit` 1–10, default 5); it returns `{id,title,url}` where `id` is a
   primary accession. The connector is an initial discovery option, not a
   replacement for direct source access. UniProt query syntax such as
   `gene:TP53 AND organism_id:9606` works in both paths. Use
   `https://rest.uniprot.org/uniprotkb/search` with URL-encoded query,
   `format=json`, and `size`, then fetch a selected record from
   `https://rest.uniprot.org/uniprotkb/<ACC>.json` (or `.txt`/`.fasta`). Record
   the serialized query, endpoint, access date/time, status, result count,
   pagination/continuation state, release/version, and response provenance.
3. **Verify/check:** validate response structure and accession format; check
   for API errors, malformed records, missing pages, and truncation before
   interpretation. Bound page-following and retries; record exclusions and
   reasons. An empty response is only no match for this query and snapshot.
4. Resolve accession identity, organism, isoform and primary/secondary mapping;
   distinguish reviewed Swiss-Prot from unreviewed TrEMBL. Prefer a reviewed
   canonical entry only when it matches the requested entity, and record the
   mapping and observed entry status. Fetch details only for selected
   accessions; ask before large batch fetches.
5. Classify each requested annotation as record-reported, experimentally
   supported, computationally supported, conflicting, or unavailable. Inspect
   evidence qualifiers/codes and cited sources; report curation status as a
   record property, not proof of experimental support. Test a known positive
   accession and a deliberately unsupported/negative query when feasible;
   record claim status and control outcomes.
6. Vary synonyms, taxonomy and relevant query filters; record material changes
   in candidate set, reviewed status or annotations. Save query and response
   provenance, artifacts and hashes with `$science-provenance`; use
   `$science-review` before material functional claims.
7. Report accession, protein/gene names, organism, reviewed status, requested
   annotation, evidence/provenance and source URL. For 3D structure use
   `$cx-alphafold-structure-analysis`; for structural homologs use
   `$cx-foldseek-structural-search`.

## Outputs

Return one `uniprot-evidence-reconciliation-v1` record with these required
fields: normalized query and assumptions (`normalized_query`); an evidence
table with accession, isoform/mapping, protein/gene name, organism, reviewed
status, annotation, evidence code/source, URL and inclusion/exclusion reason
(`records`); claim IDs, claim class and status from supported, contradicted,
inconclusive or unavailable (`claims`); exact query, release/entry version,
access time and pagination (`source_snapshot`); response artifact hashes
(`artifact_hashes`); requested sequence, features/domains, subcellular location
and cross-references tied to the selected accession (`requested_fields`);
uncertainty (`uncertainty`), limitations (`limitations`), and smallest
resolving lookup (`next_lookup`); and provenance and independent review
receipts when required (`provenance_receipt` and `review_receipt`).

## Boundaries

- Cite only accessions and annotations actually returned. Never invent records.
- Report organism explicitly; a gene name alone does not establish identity.
- Reviewed status means curated record status, not that each annotation is
  experimentally established. Preserve evidence qualifiers and missingness.
- A missing result may reflect query scope, release, mapping, or coverage; it
  does not establish protein or function absence. Failed or truncated
  responses are unavailable, not negative.
- This skill searches metadata; it does not align sequences or predict
  structure. Stop when organism/accession ambiguity changes the conclusion.
- Respect source terms and redistribution restrictions; use read-only public
  access. `$science-review` is mandatory for material function or mechanism
  claims.
