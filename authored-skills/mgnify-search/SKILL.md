---
name: mgnify-search
description: "Discover public microbiome and metagenomics studies through MGnify. Use for biome, sample, assembly, taxonomic, functional, or public microbiome dataset questions; not for unadjusted cross-study abundance comparisons."
license: MIT
---

# MGnify Search

## Decision contract

State the microbiome question, host and organism, biome, sample or study unit, assay, geography/time context when relevant, evidence cutoff, and whether the goal is discovery or comparison. Preserve the distinction among study, sample, analysis, assembly, and taxon identifiers. Define any comparison and its required harmonization before inspecting outcomes.

## Workflow

1. Call `science_search_mgnify` with a biome, host, disease, location, assay, or accession query.
2. Verify study/sample/analysis level, biome ontology, host, sequencing method, pipeline version, and public status.
3. Preserve sample and study identifiers; do not collapse repeated subjects, sites, or longitudinal samples.
4. Record accession, release, pipeline, query, and files used with `$science-provenance`.
5. Record serialized query and endpoint/tool, filters, access time, source release/update reported by the response, returned counts, pages and hashes. The bundled connector accepts `query` and optional `limit`; use the [MGnify API](https://www.ebi.ac.uk/metagenomics/api/v1/) directly when retrieving sample, analysis or file-level records beyond study discovery. Validate identifiers, response schema and completeness; list records returned and excluded with reasons.
6. Treat missing metadata, null values, no results, explicit filters and unavailable endpoints as distinct. Retry transient failures a bounded number of times, obey throttling, and do not replace a failed structured query with generic search results. Link shared studies, cohorts, pipelines and samples as dependencies.

## Outputs

Return normalized query, study/sample/analysis identifiers, biome/host/assay/pipeline context, exact query and release provenance, evidence table, returned/excluded records, missingness, and uncertainty/applicability limits. Assign claim IDs and `supported`, `contradicted`, `inconclusive`, or `unavailable` status for the stated claim. Include the smallest falsifiable next analysis. Save query, selected records, exclusions and hashes through `$science-provenance`; use `$science-review` before cross-study or biological interpretation.

## Boundaries

Do not compare abundance across studies without accounting for extraction, sequencing, pipeline, compositionality, batch, and sampling design. Do not treat taxonomic or functional profiles as direct proof of organism activity or host causality. Preserve repeated-subject and longitudinal structure; stop if identifiers, biome, pipeline, or measurement units cannot be reconciled. A study search result alone is discovery, not scientific validation.

Source basis: [MGnify API](https://www.ebi.ac.uk/metagenomics/api/v1/).
