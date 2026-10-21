---
name: quickgo-search
description: "Query QuickGO and the Evidence & Conclusion Ontology (ECO): map genes to GO biological processes, molecular functions, and cellular components; find genes for a GO term; and explore the GO hierarchy. Public API, no credential needed."
license: Apache-2.0
---

# Quickgo Search (Codex-native)

Codex-native adaptation of Google DeepMind's `quickgo-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Specify the gene/protein or GO concept, organism, annotation question, evidence
cutoff, and whether annotations, ontology terms, ancestors, or descendants are
needed. Preserve gene-product accessions and GO identifiers (`GO:<digits>`).
For annotations retain aspect (BP/MF/CC), evidence code, qualifiers, reference,
assigned-by source, and taxon where returned. Do not equate an annotation with
direct experimental validation.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; run helper code via `uv run`, never bare `python3`.
   Ask before installs or large downloads.
2. Normalize gene-product and GO identifiers, including organism/taxon. The
   optional `science_search_quickgo` connector accepts `query` and `limit` (1–10,
   default 5), returning GO `id`, `title`, `aspect`, and URL. Direct API base:
   `https://www.ebi.ac.uk/QuickGO/api` (service paths include
   `/annotation/search?geneProductId=<ACC>` and `/ontology/go/terms/<GO_ID>`).
3. Serialize filters explicitly: taxon, aspect, evidence code, qualifier, and
   source as relevant. Record the exact encoded query, endpoint, page size,
   cursor/page links, pages read, access time, and release/update information
   reported by the response. Bound pages and records before expanding hierarchy.
4. Validate HTTP status, JSON shape, identifiers, and completion metadata. Mark
   truncation or failed pages; retry transient errors a bounded number of times
   with backoff. Preserve null fields and distinguish no matching annotation
   from an unavailable or incomplete query. Record returned annotations and
   excluded records with reasons.
5. Traverse ontology relationships only for the requested direction and depth;
   retain relation type and source identifiers. Do not treat a propagated
   ancestor annotation as independent evidence. Record evidence codes without
   collapsing their different evidential meanings.
6. Save query, filters, page receipts, and response artifacts with
   `$science-provenance`; check material functional claims with `$science-review`.
   For drug targets use `$cx-opentargets-search` as a separate evidence source.

## Outputs

Return normalized gene-product, taxon, and GO identifiers; an annotation or
ontology table with aspect, evidence code, qualifier, reference, assigned-by,
page/source URL, and inclusion/exclusion reason; claim IDs marked
supported/contradicted/inconclusive/unavailable; query/release/access time;
uncertainty, limitations, and the smallest next query. Preserve raw response
artifacts and hashes through `$science-provenance`.

## Boundaries

- Report GO id, aspect (BP/MF/CC), and evidence code; evidence quality varies.
- Cite only GO ids/accessions actually returned. A missing row is not evidence
  that a function is absent. Do not infer causality or organism-specific
  phenotype from ontology membership alone.
- Stop when taxon or identifier ambiguity materially changes the result.
  Preserve incomplete retrieval as unavailable, not negative. Respect terms and
  redistribution limits. `$science-review` is mandatory for material function
  or mechanism claims.
