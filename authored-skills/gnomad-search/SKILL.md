---
name: gnomad-search
description: "Query gnomAD for variant allele frequency/rarity, gene constraint metrics (pLI, LOEUF), variants in a region or gene, and structural variants. Use to assess variant rarity or loss-of-function intolerance. Not for individual patient genomes or somatic cancer variants. Public GraphQL API, no credential needed."
license: Apache-2.0
---

# Gnomad Search (Codex-native)

Codex-native adaptation of Google DeepMind's `gnomad-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract
Record the variant, gene or region; species and genome assembly; requested gnomAD dataset/version; population context; and the question (frequency, constraint, or region variants). Normalize variant representation and check reference/alternate alleles against the selected assembly. Define in advance whether the analysis needs an overall or population-specific estimate.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use gnomAD GraphQL `https://gnomad.broadinstitute.org/api`. POST a GraphQL query for a variant (by ID/rsID), a gene, or a region; request the gnomAD version/dataset explicitly. For constraint, request `gnomad_constraint` fields (pLI, LOEUF, oe) on the gene. Validate that the response's dataset, assembly and variant identity match the request and retain the exact query. The optional Codex Science route is `science_query_source_v2` with `source="gnomad"`; its top-level arguments are `source`, `parameters`, optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. This connector is fixture-tested experimental; use only parameter fields returned by `science_list_source_contracts` and do not imply it is live-validated.

Record endpoint/tool, access time, response hash, returned and excluded record counts/reasons, dataset version, and population fields. Distinguish unavailable population fields, nulls, no matching records, truncated responses, and request failure. Retry only bounded transient errors while respecting service responses; never interpret a failed query as absence. Record queries, endpoints, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Outputs
Return normalized variant/gene/region and assembly, dataset/version, population-specific allele counts and frequency fields actually returned, constraint metrics and their source context, query evidence, and inclusion/exclusion counts. State uncertainty, ancestry/population limitations, missingness, and a falsifiable next lookup or analysis. Save the query and response or hash-bound artifact.

## Boundaries
Report the gnomAD dataset version and population; allele frequency is population-dependent. Population frequency is not clinical classification; cite only variants actually returned. gnomAD estimates do not describe an individual patient's genome and do not establish disease causality or penetrance. Do not use this workflow for somatic cancer interpretation; stop if build or dataset identity is unresolved.
