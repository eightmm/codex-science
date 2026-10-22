---
name: gtex-search
description: "Retrieve quantitative RNA expression and variant eQTL data from GTEx across 54 non-diseased tissue sites. Use for tissue expression profiles or eQTL lookups; not for disease tissue, causal claims, or calibrated expression comparisons. Public API, no credential needed."
license: Apache-2.0
---

# Gtex Search (Codex-native)

Codex-native adaptation of Google DeepMind's `gtex-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Endpoints

- GTEx API `https://gtexportal.org/api/v2`

## Decision contract

State gene or variant, tissue, organism, genome/gene identifier version when supplied, expression or eQTL question, evidence cutoff, and intended inference. Normalize genes to a GENCODE/Ensembl identifier and variants to an explicit build and allele representation. Distinguish tissue expression from variant association; neither alone establishes a disease mechanism or causality. Define the claim as measured bulk-tissue RNA abundance or a variant-expression association in the queried GTEx release and sampled donors; do not interpret it as cell-specific expression, protein abundance, function, or causal effect.

## Reference usage

- Read [references/gtex-measurement-and-dependence.md](references/gtex-measurement-and-dependence.md) before selecting expression metrics, comparing tissues, interpreting eQTLs, or assigning claim status. It defines measurement semantics, donor and tissue dependencies, covariates, controls, and applicability limits.
- Read [references/gtex-sensitivity-and-failures.md](references/gtex-sensitivity-and-failures.md) before filtering, grouping tissues, testing robustness, or reporting missing/zero values. It defines threshold sensitivity, release checks, failure detection, and the output evidence boundary.

## Workflow

1. **Gates (ask before proceeding).** On first workspace use, tell the user to review GTEx terms, ask whether to proceed, and record the notice and response in provenance; proceed only after acknowledgment. Before network access, keep access read-only and polite about rate limits; write large responses to a file and parse them. If helper code is needed, run it via `uv run`, never bare `python3`. Ask before installs or large downloads. Record gate disposition.
2. Resolve gene and variant identity: map ambiguous symbols to returned GENCODE/Ensembl IDs, preserve version suffixes, and require an explicit reference build and allele representation for variants. If identity is ambiguous, stop or retain alternatives. Record mappings and unresolved candidates.
3. Choose the documented expression or eQTL endpoint that answers the question; `science_search_gtex` is an additional gene-resolution lookup, not a replacement for direct API retrieval. Serialize exact endpoint and parameters. Record query, filters, pages, access time, and source release/version reported by the response.
4. Validate response schema, identifiers, tissue, numeric values, units, and response extent. Record returned and excluded rows with reasons; keep null, absent field, zero, filtered, and no-match states distinct. Detect truncation and record page coverage and counts; malformed or incomplete coverage makes the result unavailable or inconclusive.
5. Interpret expression as measured bulk-tissue RNA abundance and eQTL as association only. Record units/normalization, donor and sample counts when supplied, tissue ontology mapping, relevant covariates, and source-dependence links. Compare tissues only with their sample and assay context intact, and do not count portal views or tissues as independent replication; do not infer cell-specific, protein, disease, or causal claims.
6. Run a known broadly expressed housekeeping-gene and known tissue-restricted-gene sanity check in the same release and compatible tissue context when comparable records are available. Record expected/observed pattern and whether the control is applicable; a failed control triggers investigation, not silent threshold adjustment.
7. Vary expression/eQTL thresholds and tissue grouping where a conclusion depends on them. Treat a status, rank, or tissue-order change under a reasonable alternative as fragile; record each setting and changed claim.
8. On transient errors, retry a bounded number of times with backoff and respect throttling. If still unavailable, stop or use a documented equivalent direct GTEx endpoint for the same data type; never substitute web snippets as structured evidence. Do not invent a rate limit or version. Report only conclusions supported by complete, release-pinned evidence.

## Outputs

Return one `gtex-expression-evidence-v1` record set with: claim identifier (`claim_id`); claim class and status (`claim_class`, `status`); normalized gene or variant and mapping/build (`gene_id`, `variant_id`, `identifier_mapping`, `genome_build`); tissue and ontology mapping (`tissue`, `tissue_ontology_id`); endpoint and serialized query (`endpoint`, `query`); GTEx release and access time (`release`, `accessed_at`); returned measurements and units/normalization (`measurements`, `units`, `normalization`); sample and donor counts when supplied (`sample_count`, `donor_count`); record IDs, exclusions, missingness, and coverage (`record_ids`, `exclusions`, `missingness`, `coverage`); uncertainty, controls, sensitivity, applicability, and limitations (`uncertainty`, `controls`, `sensitivity`, `applicability_domain`, `limitations`). Save raw response or bounded extract, query ledger, and hashes via `$science-provenance`; use `$science-review` before presenting a material expression or eQTL interpretation.

## Boundaries

- Report the GTEx release version and tissue; expression is tissue- and sample-dependent.
- Cite only genes/variants actually returned.
- GTEx non-diseased tissue measurements do not establish disease-state expression, protein abundance, causal variant effects, or clinical relevance. Association is not colocalization or causality.
- Preserve the source's terms notice, read-only network boundary, `uv run` helper rule, install approval, and large-download approval stated above.
