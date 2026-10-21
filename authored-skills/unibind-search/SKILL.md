---
name: unibind-search
description: "Query UniBind for experimentally validated transcription-factor binding sites: retrieve TF-DNA datasets, download binding-site coordinates (BED/FASTA), and list datasets by species, cell line, or TF. Public API, no credential needed. Use for assay-specific binding evidence, not universal occupancy."
license: Apache-2.0
---

# Unibind Search (Codex-native)

Codex-native adaptation of Google DeepMind's `unibind-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- UniBind API `https://unibind.uio.no/api/v1/`

## Decision contract

Specify transcription factor, species, cell line/biosample, dataset or assay criteria, genomic assembly and the intended statement. Normalize the TF identity and retain synonyms and organism mapping. UniBind datasets represent assay-derived, context-specific binding evidence; do not infer universal binding or regulatory function.

## Workflow

1. List datasets filtered by species/cell line/TF, then download the binding-site coordinates (BED/FASTA) for local analysis.
2. Report the TF, cell line, and dataset provenance.
3. The bundled `science_search_unibind` connector performs a bounded dataset search (`query`, optional `limit`) as an additional discovery route; retain direct UniBind API access for dataset details and coordinate retrieval. Preserve the API endpoint above.
4. Record serialized query and filters, returned dataset/accession, species, cell line, assay, assembly, source release/version, file format, access time, and file hash. Validate dataset identity, coordinate schema and assembly before analysis. Record exact rows/files returned and exclusions with reasons; distinguish null metadata, no match, filtered records and unavailable files. Check response and file truncation/completeness.
5. Ask before large downloads. Use bounded retries and respect rate limits; on failure, retain the error and mark the source unavailable rather than substituting a motif prediction. Keep repeated samples and datasets from shared experiments linked.

## Outputs

Return normalized TF/species/cell context, dataset and assay, assembly, query/source provenance, records/files returned and excluded, coordinate or sequence artifact paths and hashes, and missingness. Assign claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; report uncertainty, applicability and limitations plus the smallest falsifiable next analysis. Record artifacts through `$science-provenance`; use `$science-review` before material binding or regulatory claims.

## Boundaries

- State the genome assembly of the coordinates; UniBind sites are experimentally derived, not motif predictions.
- Cite only datasets actually returned.
- Binding-site coordinates are assay and cell-context-specific; they do not alone prove regulatory direction, target gene, causality, or disease relevance. Do not combine assemblies or count files from one experiment as independent replications. Preserve terms notice, read-only network limits, `uv run`, install approval and large-download approval above.
