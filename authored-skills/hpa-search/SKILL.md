---
name: hpa-search
description: "Retrieve protein expression levels and spatial/subcellular localisation from the Human Protein Atlas (HPA). Use for tissue/cell expression and localisation of a human protein; not for causal or clinical claims. Public API, no credential needed."
license: Apache-2.0
---

# Hpa Search (Codex-native)

Codex-native adaptation of Google DeepMind's `human-protein-atlas-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Endpoints

- HPA entry JSON `https://www.proteinatlas.org/<ENSG_ID>.json`
- HPA search/download `https://www.proteinatlas.org/api/search_download.php` (columns + `format=json`)

## Decision contract

Specify the human gene/protein, tissue or cell type, evidence type (RNA, protein, or localization), source cutoff, and whether the deliverable is a descriptive expression summary or a cross-assay comparison. Resolve the gene to an Ensembl gene ID and retain the symbol-to-ID mapping. Do not equate RNA and protein measurements. Define claims as assay-specific observation in the named HPA release and tissue/cell context; a localization annotation, RNA measurement, protein staining pattern, or antibody reliability score does not establish function, disease causality, or clinical relevance.

## Reference usage

- Read [references/hpa-assay-and-reliability.md](references/hpa-assay-and-reliability.md) before interpreting an RNA, protein, localization, or antibody result. It defines assay-specific claim classes, normalization, reliability, and source dependence.
- Read [references/hpa-controls-and-sensitivity.md](references/hpa-controls-and-sensitivity.md) before filtering by tissue, score, or reliability; comparing assays; or handling missing results. It defines controls, threshold sensitivity, failure detection, and applicability limits.

## Workflow

1. **Gates (ask before proceeding).** On first workspace use, tell the user to review HPA terms, ask whether to proceed, and record the notice and response in provenance; proceed only after acknowledgment. Before network access, keep access read-only and polite about rate limits; write large responses to a file and parse them. If helper code is needed, run it via `uv run`, never bare `python3`. Ask before installs or large downloads. Record gate disposition.
2. Resolve the gene with `$cx-ensembl-search`; retain symbol-to-Ensembl mapping and ambiguous alternatives. Stop if gene identity is unresolved. Record mapping evidence.
3. Choose one or more suitable direct HPA routes: entry JSON or search/download. Preserve these API paths when `science_search_hpa` is used as an additional gene lookup; it does not replace structured retrieval. Serialize all parameters, including requested columns and `format=json`, and record access time and returned release/version.
4. Validate returned Ensembl ID, tissue/cell labels, assay, units, reliability, score, and response extent. Record exact rows and excluded rows with reasons; distinguish absent field, null, no match, and filtered row. Record counts, pages, and truncation; incomplete coverage is not a negative result.
5. Assign separate RNA-abundance, protein-detection, subcellular-localization, and antibody-reliability claims. For each, preserve the source metric (TPM, nTPM, rank, call, or other returned value), units, antibody/reliability annotation, and sample/tissue context only when supplied. Never convert RNA to protein evidence.
6. Run a known housekeeping-gene and known tissue-restricted-gene check in the same release, tissue, and assay context when available. Record expected/observed pattern and applicability; a control mismatch triggers identity, assay, coverage, and reliability review.
7. Vary expression/score cutoffs, reliability inclusion, and tissue grouping when a conclusion depends on them. Treat status or tissue ranking that changes under a reasonable alternative as fragile; record each setting and changed claim.
8. Retry transient failures a bounded number of times, respect throttling, and preserve endpoint errors. Use the other documented HPA endpoint only if it answers the same question. Do not replace failed structured retrieval with unrelated search results; report unavailable or inconclusive evidence honestly.

## Outputs

Return one `hpa-expression-evidence-v1` record set with: claim identifier (`claim_id`); claim class and status (`claim_class`, `status`); normalized gene ID and symbol mapping (`gene_id`, `symbol_mapping`); tissue/cell and ontology mapping (`tissue`, `cell_type`, `ontology_id`); assay and evidence type (`assay`, `evidence_type`); endpoint and serialized query (`endpoint`, `query`); HPA release and access time (`release`, `accessed_at`); observed value, units/normalization, score, and antibody reliability (`value`, `units`, `normalization`, `score`, `antibody_reliability`); sample counts when supplied (`sample_count`); record IDs, exclusions, missingness, and coverage (`record_ids`, `exclusions`, `missingness`, `coverage`); uncertainty, controls, sensitivity, applicability, and limitations (`uncertainty`, `controls`, `sensitivity`, `applicability_domain`, `limitations`). Save response extracts, query ledger, and hashes using `$science-provenance`. Use `$science-review` before material expression or localization claims.

## Boundaries

- HPA expression is semi-quantitative with reliability scores; report the reliability, not just the level.
- Cite only genes actually returned.
- HPA records do not establish protein function, disease causality, or clinical actionability; do not generalize across tissues, cell types, antibodies, or assays. Stop when gene identity or requested tissue/assay cannot be resolved.
- Preserve the terms notice, read-only network boundary, `uv run` helper rule, install approval, and large-download approval above.
