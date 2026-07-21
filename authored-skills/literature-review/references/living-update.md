# Living review updates

Read before advancing an evidence cutoff, replacing a reviewed synthesis, or reusing a prior review receipt.

## Immutable snapshots

Preserve the prior protocol, exact queries, source releases, included and excluded studies, study-family mapping, claim register, and reviewed report. Create a new snapshot rather than editing the old one.

## Update diff

Compare:

- query additions, removals, and changes;
- source availability or release changes;
- added, removed, and modified studies;
- publication-version, correction, and retraction changes;
- eligibility decisions;
- risk-of-bias changes;
- claim status, confidence, and applicability changes.

Use:

```bash
python scripts/diff_literature_review.py previous.json current.json --output diff.json
```

## Invalidation

Invalidate the previous review receipt when covered queries, source snapshots, study table, evidence graph, extraction, claim register, or report bytes change. A narrative that appears unchanged still requires re-review when its evidence dependencies changed.

## Stop rule

Stop the update when every source has reached the declared cutoff, pagination is complete or explicitly bounded, unresolved study identities are visible, and claim-level changes have been reviewed. Source failure is unavailable evidence, not a negative study.
