---
name: interpro-search
description: "Identify protein domains, families, and sites; find proteins sharing a domain/family; explore species distribution; and get domain architectures via InterPro (integrating Pfam, CDD, and more). Public API, no credential needed."
license: Apache-2.0
---

# Interpro Search (Codex-native)

Codex-native adaptation of Google DeepMind's `interpro-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Define the protein or InterPro entry question, organism/taxon, requested domain,
family, site, or architecture, and evidence cutoff. Use canonical UniProt
accessions for protein queries and `IPR` accessions for InterPro entries.
Clarify whether the goal is entry annotation, protein membership, or a domain
comparison; these are different source records. InterPro integrates member
databases such as Pfam and CDD, whose evidence and identifiers remain distinct.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; run helper code with `uv run`, never bare `python3`.
   Ask before installs or large downloads.
2. Normalize the protein accession or entry accession and record the exact
   query. Optionally discover entries with `science_search_interpro` (`query`,
   `limit` 1–10, default 5; records contain `id`, `title`, `type`, `url`). Direct
   API access remains available at `https://www.ebi.ac.uk/interpro/api/`; use it for protein/structure/taxonomy joins and pagination.
3. For an entry use `/entry/interpro/<IPR>`; for protein domains use
   `/entry/all/protein/uniprot/<ACC>`. Follow entry-to-protein relationship
   endpoints for members. Capture URL-encoded parameters, page size, next-page
   token/link, pages read, access time, and release/update information reported
   by the response. Set a result/page cap before enumeration.
4. Check HTTP status and expected JSON fields, identifier format, and page
   completeness. Flag malformed, failed, or truncated responses; retry transient
   failures only a bounded number of times with backoff. Do not substitute a
   web search for a failed API query. Record exact returned records and excluded
   records with reasons. Null or absent annotations are missing, not evidence
   that a domain is biologically absent.
5. Interpret each match with its member database and record type. Preserve
   domain boundaries and architecture order when supplied. Compare candidates
   only within compatible protein sequence and release context.
6. Record query, endpoint, page receipts, access time, and cited identifiers with
   `$science-provenance`; use `$science-review` before material domain/function
   conclusions.

## Outputs

Return normalized protein/entry identifiers and assumptions; a table of
InterPro accession, member database, record type, protein, coordinates or
architecture when returned, source URL, and inclusion/exclusion reason; claim
IDs with supported/contradicted/inconclusive/unavailable status; query and
release/access-time details; uncertainty, limitations, and the smallest
follow-up query that can distinguish alternatives. Save response artifacts and
hashes through `$science-provenance`.

## Boundaries

- Report the member database (Pfam, CDD, etc.) behind each InterPro entry.
- Cite only InterPro/member accessions actually returned; do not infer a
  functional effect from a domain match alone.
- A missing result can reflect query scope, sequence coverage, or source state;
  it does not establish biological absence. Stop if accession identity or
  species changes interpretation.
- Preserve API errors and truncation as unavailable. Respect source terms and
  redistribution constraints. `$science-review` is mandatory for material
  functional or mechanistic claims.
