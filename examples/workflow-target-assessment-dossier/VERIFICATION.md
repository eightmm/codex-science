# Synthetic fixture verification

All evidence below concerns offline software checks on invented fixture data.
It is not a live target assessment, biological experiment or independent review.

## Changed files and behavior

The initial pack added the files described below. The review fixes update its
validator, tests, stage reference and example documentation; no registry,
shared helper, schema, writer or public entry point changes.
The skill, progressive references, pending plan and agent metadata are under
`authored-skills/workflow-target-assessment-dossier/`. Synthetic snapshots,
six stage outputs, legacy checkpoint, separate claim register, expected result,
14 negative cases and explanatory documents are under
`examples/workflow-target-assessment-dossier/`. Frozen questions and zero-network,
zero-GPU budgets are in `benchmarks/workflow-target-assessment-dossier/tasks.json`.

`src/codex_science/target_assessment_pack.py` exposes the read-only validator;
`scripts/validate_target_assessment_pack.py` provides the thin JSON CLI.
`tests/test_workflow_target_assessment.py` exercises the public entry points.
Those files and entry points were introduced by the initial pack.

Pack-local schema names are `target-assessment-pack-v1`,
`target-assessment-snapshots-v1`, `target-assessment-stage-v1` and the frozen
task manifest `target-assessment-benchmark-v1`. Existing claim-register,
manifest-plan and checkpoint fields are reused without modification.
History searches `git log --all -S target-assessment-pack-v1 -- src scripts`
and the corresponding snapshot and stage schema searches find the introduction
commits `06cc7ce` and `51b7b37`; the pack module and CLI only read these records.
There is no earlier pack runtime writer to constrain this explicit input limit.
Existing global claim-register and checkpoint writers and validators are unchanged.
Pack validation now refuses any referenced file above 64 MiB, including those
sidecars. Stage memo and claim-register entries marked supported now fail when
they cite computed or review-approval records; supported descriptive text also
fails for the four documented efficacy words. Snapshot records remain preserved.

## Review-fix checks

Five added tests cover the review/computed evidence bypass, descriptive efficacy
wording, non-regular inputs before opening, the inclusive 64 MiB limit and exact
hashed bytes, and unsafe replacements during the final change check. All five
failed against the original source before the fix. The evidence test includes
the exact reproduction, `Independent review confirmed this target is effective.`,
as a supported descriptive claim citing a review-approval record, with matching
literal source and claim-register text. Neutral statements also exercise the
record-kind restriction independently of the word check. FIFO tests guard the
read call so the old code fails immediately instead of hanging the test runner;
the fixed CLI is also exercised against a real FIFO with the suite call timeout.

The boundary test accepts exactly 67,108,864 bytes of valid JSON plus whitespace,
refuses one byte more before opening, refuses growth beyond the limit after
reading, and keeps empty and malformed JSON labelled `PACK_FORMAT`.
The original clean replay and all 14 negative finding codes remain unchanged.

The focused seven-test run and the complete pack module passed: 35 tests in
4.037 seconds for the latter. The full module was required because both initial
reads and final change checks use the loader. The clean example CLI returned
the unchanged expected JSON with review pending. Both required `--require-clean`
audits exited 0: reference audit 140 skills, 189 references and zero findings;
maturity audit L3 120, L4 20 and zero findings. Syntax compilation and
`git diff --check` passed. Audit JSON output was large and display-truncated;
the exit statuses, findings and summary sections were visible.

These checks remain CPU-only, offline and stdlib-only. The loader keeps its
existing read interface, with regular-file and size preflight plus an actual-byte
size check. It does not provide an atomic filesystem snapshot or prevent an
adversarial replacement between preflight and opening.

## Initial implementation check results (historical)

`PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_target_assessment`
ran 30 tests: OK. Test commands were bounded with `timeout 180`; subprocess
calls inherit the suite's `OMS_TEST_CALL_TIMEOUT`, defaulting to 60 seconds.
The existing native authored-connector guidance test also passed (31 tests in
the final focused invocation). Syntax compilation passed for all three new
Python files; consumer/prose searches covered the added functions, record keys,
findings and file names across tests, scripts, docs, README files and CLI help.

`python3 scripts/audit_skill_references.py --require-clean` passed with 136
skills, 180 references, zero findings and zero major findings.
`python3 scripts/audit_native_skill_maturity.py --require-clean` passed with
L0 0, L1 0, L2 0, L3 120, L4 16. L4 is synthetic acceptance only.

The targeted existing native-quality status-document test fails on its two
document subtests: the new skill changes totals to 136 skills / L4 16 while
`docs/IMPLEMENTATION_STATUS.md` and `docs/ROADMAP.md` retain 135 / L4 15.
Those files are outside worker scope and remain untouched. The owner must
regenerate batch status totals along with inventory/wrappers and release notes.
The combined owner admission command and full repository fast suite were not
run here; no live, public, network or GPU checks were run.

## Initial tests and fail-before evidence (historical)

The initial public-entry-point probe failed with ModuleNotFoundError because
the validator did not exist. After implementation, a temporary non-test diff
was saved, reversed with `git apply --reverse`, and every individual test below
was invoked once: all 30 failed on the missing public module. The full non-test
patch was then reapplied and the temporary patch deleted. This establishes
absence-before; it is not the semantic refusal evidence.

For every seeded negative case, its corresponding check call was individually
removed, its single test was run, and the original source was restored in a
finally block. All 14 tests marked M below failed with `ValueError not raised`.
The expression context test was also checked this way (15 mutation probes in
total). Each seeded case exercises both Python and CLI with intact checks,
including refreshed hashes, a named refusal and no CLI traceback.

- `test_synthetic_replay`: expected synthetic result, pending review, Python/CLI.
- `test_identity_mismatch` (M): isoform mismatch.
- `test_cohort_dependence` (M): shared cohort counted twice.
- `test_availability_overclaim` (M): availability called druggability.
- `test_potency_mixing` (M): IC50/Ki/percent inhibition and mixed units.
- `test_missing_record` (M): empty response called no association.
- `test_modality_direction` (M): opposite modality without rationale.
- `test_critical_liability` (M): go with open critical liability.
- `test_memo_overclaim` (M): claim stronger than its citation.
- `test_association_causality` (M): associational-to-causal promotion.
- `test_numerical_validity` (M): numerical-to-physical validity promotion.
- `test_review_truth` (M): approval-to-truth promotion.
- `test_patient_advice` (M): patient treatment recommendation.
- `test_failed_control` (M): removed failed and negative controls.
- `test_self_review` (M): producer self-attests review.
- `test_identity_fields_and_empty_ledger`: all six identity fields and empty ledger.
- `test_independence_edges`: empty/zero/equal/above-limit and malformed counts.
- `test_transitive_source_dependency`: three-source dependency chain.
- `test_unknown_and_distinct_cohorts`: unresolved cohorts and true separation.
- `test_expression_context_edges` (M): missing context and donor-count bounds.
- `test_explicit_direction_rationale`: missing, empty and cited rationale.
- `test_liability_decision_edges`: go/hold/no-go and open/closed severity cases.
- `test_potency_edges_and_normalisation`: empty groups and explicit normalization.
- `test_potency_types_units_and_invalid_values`: finite values, zero and unit mismatch.
- `test_hash_order_and_path_refusals`: stale hash, order and path boundaries.
- `test_malformed_and_missing_inputs_are_labelled`: invalid JSON and missing bundle.
- `test_malformed_nested_records_are_labelled`: malformed nested records via both entry points.
- `test_symlink_and_broken_handoff`: symlink and incomplete input binding.
- `test_concurrent_validation_and_changed_input`: two readers and mid-read editing.
- `test_pack_contract_and_frozen_tasks`: reference/maturity contracts, plan shape and budgets.

## Concurrency, interruption and uncertainty

Every added project file is static source, instruction, test or fixture content;
replay does not rewrite any of them. The validator reads each referenced file's
bytes once per read, checks its declared hash, and rechecks all read files before
success. Two concurrent calls leave bundle contents unchanged. Termination
between reads leaves no partial bundle, receipt or lock. CLI output is stdout;
termination may leave the caller a partial JSON stream, which must be discarded.
Private test copies are cleaned up by TemporaryDirectory, including on failures.
An abrupt kill before test cleanup can leave only its private temporary copy,
possibly between snapshot, memo, sidecar or hash updates; concurrent tests use
different temporary directories and checked-in fixtures are unchanged.
No external record, ref, checkpoint or receipt is written by this implementation.

The checks cannot certify truthful source annotations, cohort completeness,
normalization accuracy, biological direction, semantic completeness or efficacy.
Literal attribution is conservative and refuses otherwise valid paraphrases.
Independent source/method review and coordinator admission remain necessary.
