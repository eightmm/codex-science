# Synthetic gene-set fixture

All files in this directory are synthetic fixtures, redistributable under the repository license. G01 through G30 are fake identifiers, not biological genes. No network or real gene-set database is used. `collection.json` has version synthetic-sets-v1 and is hash-bound from frozen `rules.json` before its bytes are read.

Run `python3 scripts/validate_gene_set_overrepresentation_pack.py examples/workflow-gene-set-overrepresentation/pack.json`. It prints read-only JSON. `expected.json` is the exact expected result. `negative-cases.json` holds 36 individual mutation recipes and their refusal codes, exercised by `tests/test_workflow_enrichment_pack.py` through Python and CLI. The tests refresh dependent hashes so domain defects are not hidden by a stale-hash refusal; the rule-freeze case deliberately retains its mismatch.

The universe contains exactly 30 upstream tested rows. Six selected genes give planted p=25/593775 and redundant p=1/593775. Raw-only p=24525/593775 is below .05 but full-family BH q exceeds .05. Empty overlap gives p=1. The size-one set stays untested. Significant planted/redundant sets have Jaccard 5/6 and count as one finding. This demonstrates numerical admission only, never activation, regulation, causality, a pathway mechanism or physical/clinical validity. Independent review and evidence remain unavailable.

Fixtures and expected artifacts are immutable inputs to the validator. Repeated/concurrent calls write nothing; interruption creates no partial artifact. A coordinator must register new outputs separately and preserve previous identities.
