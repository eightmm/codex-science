---
name: gtex-search
description: "Retrieve quantitative RNA expression and variant eQTL data from GTEx across 54 non-diseased tissue sites. Use for tissue expression profiles or eQTL lookups; not for disease tissue, causal claims, or calibrated expression comparisons. Public API, no credential needed."
license: Apache-2.0
---

# Gtex Search (Codex-native)

Codex-native adaptation of Google DeepMind's `gtex-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- GTEx API `https://gtexportal.org/api/v2`

## Decision contract

State gene or variant, tissue, organism, genome/gene identifier version when supplied, expression or eQTL question, evidence cutoff, and intended inference. Normalize genes to a GENCODE/Ensembl identifier and variants to an explicit build and allele representation. Distinguish tissue expression from variant association; neither alone establishes a disease mechanism or causality.

## Workflow

1. Inspect the identifier and resolve ambiguous gene symbols to the returned GENCODE/Ensembl gene ID. Preserve the mapping and any version suffix.
2. Query gene expression by tissue through the documented expression endpoints; query eQTL associations through the association endpoints for the requested gene/variant/tissue. The bundled read-only `science_search_gtex` is an additional gene-resolution lookup, not a replacement for direct API calls needed to retrieve expression or eQTL values. Use the exact endpoint and serialized parameters for the selected operation; record query, filters, pages, access time, and release/version reported by the response.
3. Validate response schema, identifier and tissue matches, numeric fields and units. Record every returned row and every excluded row with its reason. Preserve nulls, unavailable fields, zero-valued measurements, filtered results, and no-match results separately. Detect truncation and report page coverage and returned counts.
4. On transient errors, use bounded retries with backoff and respect server throttling. If the endpoint remains unavailable, stop or use a documented equivalent direct GTEx endpoint for the same data type; never substitute web snippets as structured evidence. Do not invent a rate limit or version.
5. Compare tissues only with their sample and assay context intact. Keep GTEx records dependent on the same underlying cohort; do not count portal views or tissues as independent replication.

## Outputs

Return normalized gene/variant, build, tissue, exact query and endpoint, source release, access time, and a machine-readable table of returned measurements, units, sample/tissue fields available, record IDs, exclusions, and missingness. Assign claim IDs and `supported`, `contradicted`, `inconclusive`, or `unavailable` status; state uncertainty, applicability, and limitations. Save raw response or bounded extract, query ledger, and hashes via `$science-provenance`; use `$science-review` before presenting a material expression or eQTL interpretation.

## Boundaries

- Report the GTEx release version and tissue; expression is tissue- and sample-dependent.
- Cite only genes/variants actually returned.
- GTEx's non-diseased tissue measurements do not establish disease-state expression, protein abundance, causal variant effects, or clinical relevance. Association is not colocalization or causality. Preserve the source's terms notice, read-only network boundary, `uv run` helper rule, install approval, and large-download approval stated above.
