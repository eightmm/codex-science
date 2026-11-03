# Synthetic target-assessment fixtures

Every identifier, source response, cohort, measurement, statement and decision
in this directory is invented, redistributable fixture data. No real clinical
claim, live connector query or reviewed scientific result is represented.

`synthetic/` is a complete offline replay bundle. Its expected CLI result is
`expected-validation.json`. A passed record check leaves review pending; its
go means only the proposed smallest research experiment in the invented system.
The open major control liability is retained and would require independent
method review. Promoting it to critical refuses go.

Run from the repository root:

```sh
python3 scripts/validate_target_assessment_pack.py examples/workflow-target-assessment-dossier/synthetic
```

The module `tests.test_workflow_target_assessment` replays every JSON case under
`negative/` through both the public Python entry point and the CLI. Each case
names its synthetic base, file/pointer replacements, expected finding and reason.
Tests apply replacements in a temporary copy, refresh the legitimate handoff
hashes, and check the semantic refusal rather than merely a stale hash. All
source responses are recorded snapshots; tests block socket creation.

The six stage records use pack-local schemas documented in
`authored-skills/workflow-target-assessment-dossier/references/stages.md`.
`claims.json` and `checkpoint.json` reuse existing contracts. The checkpoint is
a valid legacy schema-v1 fixture and does not claim runtime execution or review.

The validator and CLI write no files. Concurrent validation or interruption
leaves all fixture records unchanged. Test copies are private temporary bundles
removed after each test, including after a failure; concurrent test runs do not
share writes. Checked-in examples and frozen benchmark questions are read-only
during replay. No review receipt is generated or self-attested.

See [verification evidence](VERIFICATION.md) for the focused checks, individual
test inventory, refusal-removal probes and the owner integration dependency.
