---
name: hpa-search
description: "Retrieve protein expression levels and spatial/subcellular localisation from the Human Protein Atlas (HPA). Use for tissue/cell expression and localisation of a human protein; not for causal or clinical claims. Public API, no credential needed."
license: Apache-2.0
---

# Hpa Search (Codex-native)

Codex-native adaptation of Google DeepMind's `human-protein-atlas-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- HPA entry JSON `https://www.proteinatlas.org/<ENSG_ID>.json`
- HPA search/download `https://www.proteinatlas.org/api/search_download.php` (columns + `format=json`)

## Decision contract

Specify the human gene/protein, tissue or cell type, evidence type (RNA, protein, or localization), source cutoff, and whether the deliverable is a descriptive expression summary or a cross-assay comparison. Resolve the gene to an Ensembl gene ID and retain the symbol-to-ID mapping. Do not equate RNA and protein measurements.

## Workflow

1. Resolve the gene to its Ensembl gene id (use `$cx-ensembl-search`), then fetch the entry JSON.
2. Report tissue expression, subcellular location, and reliability/score fields.
3. Use the entry JSON endpoint or search/download endpoint above as appropriate; preserve these direct API paths even when using the bundled `science_search_hpa` connector as an additional gene lookup. Serialize all parameters, including requested columns and `format=json`; record access time and release/version reported by the response.
4. Validate returned Ensembl ID, tissue/cell labels, assay, reliability and score fields. Record exact returned records and rows excluded for identifier, tissue, or assay mismatch. Keep absent fields, null values, no match, and filtered rows distinct. Record response extent, page/row counts, and truncation; do not interpret an incomplete response as complete coverage.
5. Retry transient failures a bounded number of times, respect server throttling, and preserve endpoint errors. If a source route fails, use the other documented HPA endpoint only if it answers the same question. Do not replace a failed structured request with an unrelated search result.

## Outputs

Return normalized gene ID, symbol mapping, tissue/cell, assay, exact endpoint/query, source release, record IDs, observed fields and units, returned/excluded counts with reasons, and missingness. Assign claim IDs with `supported`, `contradicted`, `inconclusive`, or `unavailable` status. Report uncertainty, applicability and limitations; save response extracts, query ledger and hashes using `$science-provenance`. Use `$science-review` before material expression or localization claims.

## Boundaries

- HPA expression is semi-quantitative with reliability scores; report the reliability, not just the level.
- Cite only genes actually returned.
- HPA records do not establish protein function, disease causality, or clinical actionability; do not generalize across tissues, cell types, antibodies, or assays. Stop when gene identity or requested tissue/assay cannot be resolved. Preserve the terms notice, read-only network boundary, `uv run` helper rule, install approval, and large-download approval above.
