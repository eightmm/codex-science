# Living review updates

Read before advancing an evidence cutoff, replacing a reviewed synthesis, or reusing a prior review receipt.

## Immutable snapshots

Preserve the prior protocol, exact queries, source releases, included and excluded studies, study-family mapping, claim register, and reviewed report. Create a new snapshot rather than editing the old one.

## Update diff

`build_literature_snapshot.py` records top-level `schema_version`, `protocol_id`, `question`, `question_framework`, `evidence_cutoff`, `studies`, `claims`, and `queries`. Its record fields are:

- Studies: `study_id`, `title`, `persistent_id`, `eligibility`, and `exclusion_reason` for excluded studies.
- Claims: `id`, `status`.
- Queries: `query_id`, `source`, `query`, and, when present in the query log, `status`, `accessed_at`.

A diff of two built snapshots reports query additions, removals, and changes to those query fields; study additions, removals, and changes to title, persistent identifier, eligibility, or exclusion reason; and claim additions, removals, and status changes. Rows are matched by `query_id`, `study_id`, and claim `id`; changing one appears as removal and addition.

Publication-state changes (including publication-version, correction, and retraction), risk-of-bias changes, effect-estimate changes, claim text/confidence/applicability changes, and query response-digest changes are not visible in a built-snapshot diff. Compare those fields directly in the study table, claim register, and query log. The receipt invalidation rule below still applies to changes omitted from the diff.

Use:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/diff_literature_review.py" previous.json current.json --output diff.json
```

Build extraction output with `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/build_study_table.py" --run-dir <run-dir> --extraction <file>`.

## Invalidation

Invalidate the previous review receipt when covered queries, source snapshots, study table, evidence graph, extraction, claim register, or report bytes change. A narrative that appears unchanged still requires re-review when its evidence dependencies changed.

## Stop rule

Stop the update when every source has reached the declared cutoff, pagination is complete or explicitly bounded, unresolved study identities are visible, and claim-level changes have been reviewed. Source failure is unavailable evidence, not a negative study.
