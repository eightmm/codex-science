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
Support-excerpt text in `studies.json` must be 20..2000 characters. The set of `type: study` node IDs in `evidence_graph.json` must equal the study IDs in `studies.json`.
Support-excerpt shape: in `studies.json`, optional `support_excerpts[].locator` must be an object; the validator defines no required keys. An integer `line` must point into the quoted text.

Reference-use-ledger shape: `reference-use-ledger.json` requires top-level `schema_version: 1`, non-empty `skill`, and a non-empty `uses` list; the `record_reference_use.py` command builds a valid ledger. Each use must be an object with `schema_version: 1` and non-empty `skill`, `reference_id`, `path`, `sha256`, `read_reason`, and `loaded_at`; `path` must stay under `references/` and `sha256` must contain 64 hexadecimal characters. Each use may include `used_for`, `sections`, and `search_terms` as lists or tuples of strings; they default to empty lists.

## Protocol commitment ledger

`protocol.json` may declare an optional `commitment_ledger` namespace (`schema_version: 1`, `procedures: [...]`). When declared, the validator checks unique procedure IDs; supported `target_set` forms (`{"unit":"record","source_artifact":"screening.json","selection":"included"|"all"}` and `{"unit":"study","source_artifact":"studies.json","selection":"included"}`); integer (not bool) `denominator` and `completed_count`; `target_ids` equal the resolved membership from the source artifact; `completed` IDs unique members with `evidence_artifact` as a registered, hash-verified manifest path; and that `completed_count == len(completed)` equals `denominator` when complete. When `completed_count < denominator`, a non-empty `deviation` with `reason` and either non-empty `affected_claims` (each `claim_id` exists in `claims.json`, `limitation` non-empty and appearing verbatim in `report.md`) or a non-empty `no_claim_impact_reason` is required. A valid deviation reaches the reviewer packet as informational context (read-only `protocol_commitment_context`), never as a blocking deterministic finding. Old runs without the key, or with an empty `procedures` list, keep existing behavior. The historical top-level `deviations` key is ignored.

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
