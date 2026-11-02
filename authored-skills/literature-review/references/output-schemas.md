# Output schemas

Read before building `evidence_graph.json`, `studies.json`, `claims.json`, `queries.jsonl`, lane receipts, `snapshot.current.json`, or the `reference-use-ledger`. The validators enforce these shapes; this file only lists them.

## Allowed values and cross-checks

Allowed values (each field is checked by its named validator):
- `evidence_graph.json / edges[].relation`: `supports`, `contradicts`, `depends_on`, `duplicates`, `derived_from`, `shares_cohort`, `shares_samples`, `propagated_from`, `training_overlap`.
- `evidence_graph.json / nodes[].type`: `claim`, `study`, `dataset`, `artifact`, `execution`, `query`, `model`, `cohort`, `sample`, `portal`.
- `claims.json / claims[].status`: `planned`, `supported`, `replicated`, `suggestive`, `conflicting`, `unsupported`, `withdrawn`, `unavailable`.
- `queries.jsonl / each record.status`: `complete`, `partial`, `failed`, `unavailable`.
- `studies.json / studies[].evidence_type`: `primary`, `secondary`, `preprint`, `registry`, `dataset`, `computed`.
- `lanes/*.json / confidence`: `high`, `moderate`, `low`, `very-low`, `unrated`.
- `snapshot.current.json / question_framework`: `PICO`, `PECO`, `PICOT`, `SPIDER`, `custom`.
- `snapshot.current.json / studies[].eligibility`: `include`, `exclude`, `awaiting-full-text`.
- `studies.json / studies[].relationships[].type`: `preprint_of`, `published_as`, `corrected_by`, `retracted_by`, `secondary_analysis_of`, `protocol_for`, `registry_for`; enforced by `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/resolve_study_families.py" <records.json> [--output <report.json>]`.
- `risk-of-bias artifact / domains[].judgment and overall_judgment`: `low`, `some-concerns`, `high`, `unclear`, `not-applicable`.
Support-excerpt text in `studies.json` must be 20..2000 characters, supplied as a non-blank string and measured before stripping whitespace. The set of `type: study` node IDs in `evidence_graph.json` must equal the study IDs in `studies.json`.
Support-excerpt shape: in `studies.json`, optional `support_excerpts[].locator` must be an object; the validator defines no required keys. An integer (not boolean) `line` must be within the source's line count when the source is available. The study-table builder additionally requires that line to intersect the quoted source text.

Excluded studies (`included: false`) remain graph nodes for provenance, including cohort dependencies, but the builder emits no `supports` or `contradicts` edges for them; review also ignores such edges from excluded studies in existing graphs. Claims cannot be the source of `supports` or `contradicts` edges, including in `--extra` input. Legacy schema 1 cycles in other relations remain accepted. Schema 2 graph parsing normalizes node IDs and edge endpoints to trimmed strings before computing independence components.

Study-table builds require every screening and extraction `record_id` to belong to the hash-bound `candidates.json` pool. When screening supplies an `evidence_artifact`, its current bytes must match the recorded `evidence_sha256`, even when extraction quotes another source. Title-stage inclusion may have null screening evidence; extraction excerpts must still supply a valid `source_artifact`. Extraction `fields` remains an extension object: all nested numeric values must be finite; `sample_size`, `effect_estimate`, and `standard_error` cannot be booleans. Other extension field types remain unrestricted.

Reference-use-ledger shape: `reference-use-ledger.json` requires top-level `schema_version: 1` and a non-empty `uses` list; the `record_reference_use.py` command builds a valid ledger. A top-level `skill`, when present, must be a non-blank string. Each use must be an object with `schema_version: 1` and non-empty string `reference_id`, `path`, `sha256`, `read_reason`, and `loaded_at`; `path` must stay under `references/` and `sha256` must contain 64 hexadecimal characters. A use may omit `skill` only when a valid top-level `skill` supplies its inherited value. Without a top-level `skill`, every use must supply its own. An explicitly present per-use `skill` must be a non-blank string; null, blank, and non-string values never inherit. Validation does not insert inherited fields into the supplied payload. Each use may include `used_for`, `sections`, and `search_terms` as lists or tuples of strings; they default to empty lists.

Reference schema versions must be integers, never booleans. Required text fields must be strings; null and missing values do not supply text except for an omitted per-use `skill` inherited as above. Reference-index `skill` names cannot contain path separators or `..`; `reference_lookup.py --receipt-dir` refuses escaping receipt destinations before writing receipts. Reference-use receipts record skill-reference provenance, not bibliographic verification.

Optional `resolve_citations.py` existence lookups report `unavailable` when a supplied response DOI differs from the requested DOI (case-insensitive) or an arXiv identity differs after ignoring version suffixes. Legacy offline DOI fixture names with ambiguous slash/underscore substitutions require a response DOI. Conflicting expected metadata for one normalized identifier in a run's study table produces `metadata_check: mismatch` regardless of row order. These checks do not establish citation relevance or support.

## Protocol commitment ledger

`protocol.json` may declare an optional `commitment_ledger` namespace (`schema_version: 1`, `procedures: [...]`). When declared, the validator checks unique procedure IDs; supported `target_set` forms (`{"unit":"record","source_artifact":"screening.json","selection":"included"|"all"}` and `{"unit":"study","source_artifact":"studies.json","selection":"included"}`); integer (not bool) `denominator` and `completed_count`; `target_ids` equal the resolved membership from the source artifact; `completed` IDs unique members with `evidence_artifact` as a registered, hash-verified manifest path; and that `completed_count == len(completed)` equals `denominator` when complete. When `completed_count < denominator`, a non-empty `deviation` with `reason` and either non-empty `affected_claims` (each `claim_id` exists in `claims.json`, `limitation` non-empty and appearing verbatim in `report.md`) or a non-empty `no_claim_impact_reason` is required. Validated fields: `schema_version`, `procedures[].id`, `target_set`, `target_ids`, `denominator`, `completed[].target_id`, `completed[].evidence_artifact`, `completed_count`, and the `deviation` fields `reason`, `affected_claims[].claim_id`, `affected_claims[].limitation` and `no_claim_impact_reason` (either non-empty `affected_claims` or `no_claim_impact_reason`). Descriptive only, never checked: `procedure`, `affected_claims[].narrowed_text`, `affected_claims[].narrowed_inference` and `affected_claims[].report_artifact`. A `deviation` present on a complete ledger (`completed_count == denominator`) is validated the same way. `evidence_artifact` may be any registered, hash-verified artifact path except the `protocol.json` that declares the ledger; one artifact may evidence several targets. Claim ids come from `claims.json` when it is registered, otherwise from the manifest `claims`; `claim_id` is compared after stripping surrounding whitespace. Limitation text is searched in the manifest's registered `report` artifact (not in `affected_claims[].report_artifact`) after NFC-normalising both sides and collapsing runs of whitespace to one space, so line wrapping and composed or decomposed accents do not matter; HTML comments (`<!-- ... -->`, an unterminated one hides the rest) and fenced code blocks (``` or ~~~ fences, an unclosed one hides the rest) are removed from the report text first, so the limitation must appear in the report prose (an empty comment `<!-->` or `<!--->` ends at once, and a backtick fence whose info string contains a backtick is not a fence); the match stays case-sensitive, and a limitation with fewer than 10 non-space characters is refused. `schema_version` must be the integer `1` (not a boolean or `1.0`), `affected_claims` when present must be a list, and extra keys in `target_set` must be scalars (strings, numbers, booleans or null; objects and lists are refused). A `report.md` that is not UTF-8 is refused with an error naming it. A study-unit procedure is blocked while any included record in `screening.json` has no extracted included row in `studies.json`; use a record-unit `target_set` or extract every included record. A UTF-8 byte order mark before the `protocol.json` content is tolerated when the ledger is loaded. A valid deviation reaches the reviewer packet as informational context (read-only `protocol_commitment_context`), never as a blocking deterministic finding. Old runs without the key, or with an empty `procedures` list, keep existing behavior. The historical top-level `deviations` key is ignored.

Minimal validating example:

```json
{
  "commitment_ledger": {
    "schema_version": 1,
    "procedures": [
      {
        "id": "backward-references",
        "procedure": "One bounded backward reference pass per included study",
        "target_set": {"unit":"study","source_artifact":"studies.json","selection":"included"},
        "target_ids": ["S1","S2"],
        "denominator": 2,
        "completed": [{"target_id":"S1","evidence_artifact":"sources/S1-reference-pass.md"}],
        "completed_count": 1,
        "deviation": {
          "reason": "The reference list for S2 was unavailable.",
          "affected_claims": [{"claim_id":"C1","narrowed_text":"The examined evidence supports the bounded result.","narrowed_inference":"Independence remains unresolved.","limitation":"Backward reference screening covered 1 of 2 included studies.","report_artifact":"report.md"}],
          "no_claim_impact_reason": ""
        }
      }
    ]
  }
}
```
