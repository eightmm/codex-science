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

Record the variant, gene, or region; species and genome assembly; requested
gnomAD dataset/version; population context; and question (frequency, constraint,
or region variants). Normalize variant representation and check reference and
alternate alleles against the selected assembly. Define in advance whether the
analysis needs an overall or population-specific estimate. A gnomAD frequency
is a population database estimate, not a clinical classification or an
individual's genotype.

## Reference usage

- Read [references/gnomad-frequency.md](references/gnomad-frequency.md) before
  interpreting allele frequency, ancestry groups, allele number, coverage,
  filters, or flags.
- Read [references/gnomad-frequency.md](references/gnomad-frequency.md) before
  assigning claim status, treating an absent result as rare, or comparing
  releases and population strata.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, ask the user
   to review the source's terms of use and wait for confirmation; record the
   notice in provenance. Ask before installs or large downloads. Write large
   responses to a file and parse them; run helper code via `uv run`, never bare
   `python3`. Continue only after required notice and approvals; record them.
   Access remains read-only and rate-limit polite.
2. Normalize variant/gene/region, species, assembly, requested dataset/version,
   and overall or ancestry-group question; if build or dataset identity is
   unresolved, stop and record an unavailable mapping.
3. Read the reference rules and define the claim class and support criterion;
   for frequency claims specify population, AC/AN context, filters, and coverage
   needed before retrieval.
4. POST an exact GraphQL query to `https://gnomad.broadinstitute.org/api` for a
   variant (by ID/rsID), gene, region, or `gnomad_constraint` gene fields (pLI,
   LOEUF, oe), explicitly requesting dataset/version. If using the optional
   Codex Science route, use `science_query_source_v2` with `source="gnomad"`.
   `science_query_source_v2` requires `source` and `parameters`; optional
   top-level fields are `operation`, `page_size`, `max_pages`, and
   `include_snapshot`. Current v2 legacy sources accept required
   `parameters.query` (a non-empty string) and optional `parameters.limit` (an
   integer from 1 to 10). `science_list_source_contracts` lists available
   sources and operations; it does not return a parameter schema. Current v2
   routes refuse `evidence_cutoff`; record the cutoff in your protocol and
   apply it to returned record dates yourself, treating missing dates as
   unresolved. The v2 connector queries a GRCh38 variant in `gnomad_r4`;
   dataset and assembly overrides are refused. This connector is
   fixture-tested experimental, not live-validated. Record exact query,
   endpoint/tool, access time, and returned version.
5. Verify response dataset, assembly, identity, population fields, flags, and
   completeness; record missing, null, no-match, truncation, and failed request
   separately, with excluded records and reasons.
6. Interpret AC and AN with coverage and quality filters for the requested
   population; retain population-specific and global estimates separately and
   record dependencies among shared samples/callsets/releases.
7. When feasible within rate limits (at least once per run, not per lookup), run positive, negative, and nonexistent-variant controls and vary the
   population, release, and quality/coverage assumptions as appropriate;
   record control outcomes and whether the claim changes.
8. **Verify** that status is supported, contradicted, inconclusive, or
   unavailable, that failure is never converted to absence, and that response
   hash, counts, dataset, population fields, uncertainty, and limitations are
   present; preserve query and response or hash-bound artifact, then record
   queries/endpoints/IDs with `$science-provenance` and check claims with
   `$science-review` before presenting.

## Outputs

Produce `gnomad-frequency-evidence-v1` with required fields: normalized
variant/gene/region; species and assembly; dataset and release; claim IDs and
claim class; population or ancestry group; status (`supported`, `contradicted`,
`inconclusive`, or `unavailable`); returned AC, AN, AF and other frequency
fields; coverage, filters, and flags actually returned; constraint metrics and
their context when requested; exact query and endpoint/tool; retrieval time and
response hash/artifact; included/excluded counts and reasons; source/sample
dependencies; uncertainty and limitations; smallest next lookup; and
provenance/review references.

## Boundaries

Report the gnomAD dataset version and population; allele frequency is
population-dependent. Population frequency is not clinical classification;
cite only variants actually returned. gnomAD estimates do not describe an
individual patient's genome and do not establish disease causality or
penetrance. Do not use this workflow for somatic cancer interpretation. Stop if
build or dataset identity is unresolved. Do not infer rarity from no returned
variant when coverage, callability, filters, or query status are unknown. Retry
only bounded transient errors while respecting service responses; never
interpret a failed query as absence. Distinguish unavailable population fields,
explicit nulls, no matching records, truncated responses, and request failure.
