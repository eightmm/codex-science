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

Specify the gene/protein or GO concept, organism, annotation question,
evidence cutoff, and whether the target is an annotation, ontology term,
ancestor, or descendant. Preserve gene-product accessions and GO identifiers
(`GO:<digits>`). For annotations retain aspect (BP/MF/CC), evidence code,
qualifier, reference, assigned-by source, and taxon where returned. Distinguish
curated experimental evidence from IEA electronic inference. A GO annotation
is an assertion about a gene product and term; it does not alone establish
causal mechanism, phenotype in a condition, or direct experimental validation.

## Reference usage

Read [references/quickgo-evidence.md](references/quickgo-evidence.md) before
filtering annotations, traversing ontology relations, or interpreting functional
claims. Use its evidence-code classes, true-path propagation rules,
independence checks, controls, sensitivity criteria, and limits; record chosen
filters, ontology release, and reference use with the retrieval receipt.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Keep access public and read-only, respect rate limits, write large responses
   to files for parsing, run helper code via `uv run` (never bare `python3`),
   and ask before installs or large downloads; record the gate outcome.
2. Classify the request as annotation retrieval, ontology traversal,
   enrichment-oriented gene retrieval, or interpretation; define evidence
   threshold and intended claim, narrowing causal or phenotype claims when GO
   membership cannot support them.
3. Normalize gene-product and GO identifiers and taxon. Optional
   `science_search_quickgo` accepts `query`, `limit` 1–10 (default 5), and
   returns GO ID, title, aspect, and URL. Direct base is
   `https://www.ebi.ac.uk/QuickGO/api` (for example,
   `/annotation/search?geneProductId=<ACC>` and `/ontology/go/terms/<GO_ID>`);
   preserve original IDs and mapping alternatives.
4. Serialize taxon, aspect, evidence-code, qualifier, and source filters; IEA
   filtering corresponds to ECO:0000501 and its descendants. Pin
   reported QuickGO/GO release and record endpoint, encoded query, page size,
   page links, pages read, access time, and result limits. Bound pages and
   records before expanding the hierarchy.
5. Validate status, identifiers, fields, and all pages. Retain null fields and
   excluded records with reasons; retry transient failures a bounded number of
   times with backoff. Mark failed or incomplete retrieval unavailable, not a
   negative annotation result.
6. Traverse ontology relationships only for the requested direction and depth;
   retain relation type. For returned annotations preserve evidence code,
   reference, assigned-by, qualifier, taxon, aspect, and source; count each
   source assertion once. A `NOT` qualifier is not positive evidence and
   propagates to descendants, not ancestors.
7. Use a well-annotated gene product expected to carry the selected term as a
   positive retrieval control. Query an obsolete or nonexistent GO ID as a
   negative control; do not use a random gene set for plain annotation retrieval.
   Vary evidence-code filters and report material claim changes.
8. Report uncertainty and applicable taxa/contexts, save raw responses and
   query receipts through `$science-provenance`, and use `$science-review` for
   material functional claims. For drug targets, use `$cx-opentargets-search`
   as a separate evidence source; record the distinct handoff.

## Outputs

Return one `quickgo-annotation-evidence-v1` record with required fields: claim
identifier (`claim_id`); claim class (`claim_class`); status (`status`:
supported, contradicted, inconclusive, or unavailable); gene-product IDs
(`gene_product_ids`); taxon (`taxon`); GO IDs and aspect (`go_terms`, `aspect`);
evidence code and class (`evidence_code`, `evidence_class`); qualifier,
reference, and assigned-by (`qualifier`, `reference`, `assigned_by`); ontology
relation and propagation lineage (`relation`, `propagation_lineage`); filters,
query, and release (`filters`, `query`, `release`); included/excluded records
and reasons (`records`, `excluded_records`); controls and sensitivity
(`controls`, `sensitivity`); uncertainty and applicability (`uncertainty`,
`applicability`); source URLs, access time, and artifact hashes (`source_urls`,
`accessed_at`, `artifact_hashes`). List the smallest falsifiable next query
(`next_query`) separately and preserve raw responses with `$science-provenance`.

## Boundaries

- Report GO ID, aspect (BP/MF/CC), and evidence code; evidence classes differ.
  Cite only GO IDs and accessions actually returned.
- Missing rows do not establish absent function. Do not infer causality or an
  organism-specific phenotype from ontology membership alone.
- Ancestor propagation follows ontology relations and is not an independent
  experimental annotation. IEA is electronic inference, not experimental
  validation.
- Stop when taxon or identifier ambiguity materially changes interpretation.
  Preserve incomplete retrieval as unavailable, not negative. Respect terms
  and redistribution limits. `$science-review` is mandatory for material
  function or mechanism claims.
- For drug-target questions, consult `$cx-opentargets-search` separately; do not
  merge its claims with GO annotation evidence without an explicit evidence map.
