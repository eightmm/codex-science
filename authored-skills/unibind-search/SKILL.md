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

## Reference usage

Read [references/unibind-evidence.md](references/unibind-evidence.md) before interpreting UniBind sites, comparing datasets or releases, evaluating direct-TFBS predictions, or making binding or regulatory claims. It defines the evidence chain, dependency and release rules, controls, sensitivity checks, and assay-specific limits.

## Workflow

1. **Gates (ask before proceeding).** Before first workspace use, stop and ask the user to review source terms; record the notice in provenance. Keep public network access read-only and rate-limited; use `uv run` for helper code, never bare `python3`; ask before installs or large downloads. Record the gate outcome.
2. Normalize TF identity/synonyms, species, biosample/cell line, assembly, intended claim, assay criteria, and cutoff; ask if a material choice changes retrieval or interpretation. Record normalized inputs and unresolved identity mappings.
3. Discover datasets using direct UniBind API filters for species/cell line/TF. Use bundled `science_search_unibind` only as an additional bounded dataset search (`query`, optional `limit`); retain direct API access for dataset details and coordinate retrieval. Record route and filters.
4. Retrieve the smallest relevant dataset metadata first and select only datasets meeting prespecified context and assay criteria. Record the query, accession, species, cell line, assay, assembly, source release/version, access time, and exclusion reasons.
5. Download BED/FASTA coordinates only when needed and ask before large downloads. Record file format, size/extent, and hash; verify completeness, coordinate schema, dataset identity, and assembly. Preserve null metadata, no match, filtered records, and unavailable files as distinct states.
6. Trace each predicted direct-TFBS interval to its originating ChIP-seq dataset, peak evidence, prediction method/model and motif version where reported. Keep the original peak, UniBind prediction, and any sequence motif match as separate evidence objects; link shared experiments, samples, and reused matrices as dependencies.
7. Check a well-characterized promoter/enhancer or known binding region from a relevant assay as a positive control and shuffled sequences or matched random genomic background as a negative/background control. Record control provenance, motif threshold/background when used, and results; controls test processing, not the query site's function.
8. Vary motif threshold, cell type/biosample, and genomic window size where the method permits; record whether sites, ranking, or claim status change. Mark a context-sensitive result fragile and inconclusive. Keep related datasets from shared experiments linked rather than counting them as independent replications.
9. Verify evidence status, uncertainty, assembly, release, dependencies, and applicability against `references/unibind-evidence.md`; use bounded transient retries and no motif substitution for failed evidence retrieval. Record failures and the smallest falsifiable next assay or query.

## Outputs

Return one `unibind-site-evidence-v1` record with normalized TF/species/cell context (`tf_identity`, `species`, `biosample`), dataset and assay (`datasets`, `assays`), assembly (`assembly`), query and source provenance (`query_ledger`, `source_release`), returned and excluded records/files with reasons (`included`, `excluded`), coordinate or sequence artifact paths and hashes (`artifacts`), response/file extent and missingness (`response_extent`, `missingness`), claim IDs and status (`claims`), shared experiments and matrix dependencies (`dependencies`), controls and sensitivity results (`controls`, `sensitivity`), uncertainty and applicability (`uncertainty`, `applicability`), limitations (`limitations`), and smallest falsifiable next analysis (`next_action`). Use only `supported`, `contradicted`, `inconclusive`, or `unavailable` for claim status. Record artifacts through `$science-provenance`; use `$science-review` before material binding or regulatory claims.

## Boundaries

- State the genome assembly of the coordinates; UniBind sites are experimentally derived, not motif predictions.
- Cite only datasets actually returned.
- Binding-site coordinates are assay and cell-context-specific; they do not alone prove regulatory direction, target gene, causality, or disease relevance. Do not combine assemblies or count files from one experiment as independent replications. Preserve terms notice, read-only network limits, `uv run`, install approval and large-download approval above.
