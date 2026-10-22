---
name: interpro-search
description: "Identify protein domains, families, and sites; find proteins sharing a domain/family; explore species distribution; and get domain architectures via InterPro (integrating Pfam, CDD, and more). Public API, no credential needed."
license: Apache-2.0
---

# InterPro Search (Codex-native)

Codex-native adaptation of Google DeepMind's `interpro-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Define the protein or InterPro-entry question, organism/taxon, requested
domain/family/site/architecture, and evidence cutoff. Use canonical UniProt
accessions for protein queries and `IPR` accessions for InterPro entries.
Clarify whether the goal is entry annotation, protein membership, or domain
comparison; these are different source records. InterPro integrates member
databases such as Pfam and CDD, whose methods, evidence and identifiers remain
distinct. A database match is not itself experimental evidence of function.

## Reference usage

Read [references/interpro-record-evidence.md](references/interpro-record-evidence.md)
before interpreting an integrated entry or member-database match, comparing
protein membership or architecture, pinning a release, or treating a missing
match as biological absence.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in
   provenance. Use public read-only access and respect rate limits. Ask before
   installs or large downloads.
2. Normalize the protein accession or entry accession; record exact query,
   organism/taxon, requested fields and whether the task concerns entry
   annotation, protein membership or comparison. Optionally discover entries
   with `science_search_interpro` (`query`, `limit` 1–10, default 5; records
   contain `id`, `title`, `type`, `url`).
3. Use the InterPro API at `https://www.ebi.ac.uk/interpro/api/`: for an entry
   use `/entry/interpro/<IPR>`; for protein domains use
   `/entry/all/protein/uniprot/<ACC>`; follow entry-to-protein relationship
   endpoints for members. Capture URL-encoded parameters, endpoint, page size,
   next-page token/link, pages read, access time, and reported release/update.
   Set a page/result cap before enumeration. For large responses, write to a
   file and parse with `uv run`; never run bare `python3` helper code.
4. **Verify/check:** check HTTP status, expected JSON fields, identifier format
   and pagination completeness. Bound transient retries with backoff; flag
   malformed, failed or truncated responses unavailable. Record returned and
   excluded records with reasons; null or absent annotation means missing, not
   biological absence.
5. Resolve protein identity, sequence/isoform and taxonomy; classify each
   record by InterPro integrated entry versus member-database signature. Retain
   member database, signature accession, evidence/provenance and coordinates;
   do not collapse distinct methods into one independent confirmation. Check a
   known positive entry/protein and a negative query when feasible; record
   claim status and control outcomes.
6. Vary synonyms, taxonomy, page/result caps and relevant filters; record
   changes in membership, architecture or conclusion. Compare only compatible
   sequences and pinned releases. Preserve domain boundaries and architecture
   order when supplied.
7. Save exact queries, endpoint/page receipts, release/access time, cited IDs,
   response artifacts and hashes through `$science-provenance`; use
   `$science-review` before material domain/function conclusions.

## Outputs

Return one `interpro-domain-evidence-v1` record with these required fields:
normalized protein/entry identifiers and assumptions (`normalized_query`); a
table of InterPro accession, member database/signature, record type, protein,
coordinates/architecture, evidence/provenance, URL and inclusion/exclusion
reason (`records`); claim IDs, claim class and status from supported,
contradicted, inconclusive or unavailable (`claims`); exact query, release and
access time (`source_snapshot`); page receipts, artifact hashes and exclusions
(`pagination`, `artifact_hashes` and `exclusions`); uncertainty
(`uncertainty`) and limitations (`limitations`); the smallest
alternative-discriminating query (`next_query`);
and provenance/review receipts when required (`provenance_receipt` and
`review_receipt`).

## Boundaries

- Report the member database (Pfam, CDD, etc.) behind each InterPro entry.
- Cite only returned InterPro/member accessions; do not infer functional effect
  from a domain match alone.
- InterPro integration may group related signatures; member databases sharing
  source sequences, methods or annotation are dependent evidence, not
  independent replications.
- A missing result can reflect query scope, sequence coverage, integration or
  source release; it does not establish biological absence. Preserve API
  errors/truncation as unavailable. Stop if accession identity or species
  changes interpretation.
- Respect source terms and redistribution constraints. `$science-review` is
  mandatory for material functional or mechanistic claims.
