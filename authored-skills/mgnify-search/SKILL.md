---
name: mgnify-search
description: "Discover public microbiome and metagenomics studies through MGnify. Use for biome, sample, assembly, taxonomic, functional, or public microbiome dataset questions; not for unadjusted cross-study abundance comparisons."
license: MIT
---

# MGnify Search

## Decision contract

State the microbiome question, host and organism, biome, sample or study unit, assay, geography/time context when relevant, evidence cutoff, and whether the goal is discovery or comparison. Preserve the distinction among study, sample, analysis, assembly, and taxon identifiers. Define any comparison and its required harmonization before inspecting outcomes.

Treat a database record as a reported submission or pipeline annotation, not experimental demonstration. A taxonomic profile supports a statement about the pipeline-assigned profile; a functional profile supports a statement about predicted/annotated sequence content. Neither alone demonstrates absolute abundance, activity, phenotype, or causation. Carry claim identifiers and one status vocabulary: `supported`, `contradicted`, `inconclusive`, or `unavailable`.

## Reference usage

Read [MGnify evidence interpretation](references/mgnify-evidence-interpretation.md) before interpreting profiles, comparing studies, assigning claims, or deciding whether an analysis is applicable. Read [MGnify retrieval and sensitivity](references/mgnify-retrieval-sensitivity.md) before direct API retrieval, selecting controls, or varying pipeline, taxonomy, or database settings.

## Workflow

1. Define discovery versus comparison, target units, eligibility and a negative query/control; stop comparison if required harmonization cannot be specified. Record the question and rules.
2. Search with `science_search_mgnify` using biome, host, disease, location, assay or accession; retain exact query and returned count. Record tool, query and access time.
3. Verify study, sample, analysis or assembly level, biome ontology, host, sequencing method, public status and per-analysis pipeline version; exclude mismatched units with reasons. Record source fields and exclusions.
4. For detail beyond study discovery, use the [MGnify API](https://www.ebi.ac.uk/metagenomics/api/v1/); the bundled connector accepts `query` and optional `limit`. Validate response schema, identifiers, pagination and completeness before using records. Record endpoint, parameters, pages and hashes.
5. Keep study, sample and analysis accessions distinct; retain repeated subjects, sites and longitudinal samples as dependent observations. Record cohort and sample links.
6. Pin reported data release, pipeline and reference database versions; treat profile changes across versions as possible method effects. If versions are absent or cannot be reconciled, mark the comparison `inconclusive` or `unavailable` and record why.
7. Run a known-accession positive control and a deliberately impossible/negative query; require expected retrieval and explicit empty-result behavior before interpreting the batch. Record control queries and outcomes.
8. Vary pipeline version when available, taxonomy filters, and database selection; call conclusions fragile when claim status, eligible records, or direction of a reported contrast changes. Record each setting and change.
9. Distinguish missing metadata, null values, no results, explicit filters and unavailable endpoints; retry transient failures a bounded number of times, obey throttling, and never substitute generic search for failed structured retrieval. Record failure state.
10. Classify each claim, state uncertainty and applicability limits, preserve query, records, exclusions and hashes with `$science-provenance`, then use `$science-review` before cross-study or biological interpretation. Record claim IDs, status and the smallest falsifiable next analysis.

## Outputs

Return `mgnify-evidence-reconciliation-v1` with required fields: question and eligibility; serialized query, endpoint/tool, filters and access time; release, pipeline and reference-database versions; claim ID, claim class and status (`supported`, `contradicted`, `inconclusive`, `unavailable`); study/sample/analysis/assembly identifiers; evidence table; returned and excluded records with reasons; cohort/dependency links; missingness; controls and sensitivity settings/results; uncertainty and applicability limits; smallest falsifiable next analysis; provenance artifact hashes; review handoff state. Preserve records and hashes through `$science-provenance`; use `$science-review` before cross-study or biological interpretation.

## Boundaries

Do not compare abundance across studies without accounting for extraction, sequencing, pipeline, compositionality, batch, and sampling design. Do not read relative abundance as absolute abundance or treat taxonomic/functional profiles as direct proof of organism activity or host causality. Preserve repeated-subject and longitudinal structure; stop if identifiers, biome, pipeline, or measurement units cannot be reconciled. A study search result alone is discovery, not experimental demonstration.

Source basis: [MGnify API](https://www.ebi.ac.uk/metagenomics/api/v1/).
