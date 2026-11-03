# Synthetic fixture verification

All evidence below concerns offline software checks on invented fixture data.
It is not a live target assessment, biological experiment or independent review.

## Changed files and behavior

All files in this patch are new. No registry or existing source was edited.
The skill, progressive references, pending plan and agent metadata are under
`authored-skills/workflow-target-assessment-dossier/`. Synthetic snapshots,
six stage outputs, legacy checkpoint, separate claim register, expected result,
14 negative cases and explanatory documents are under
`examples/workflow-target-assessment-dossier/`. Frozen questions and zero-network,
zero-GPU budgets are in `benchmarks/workflow-target-assessment-dossier/tasks.json`.

`src/codex_science/target_assessment_pack.py` exposes the read-only validator;
`scripts/validate_target_assessment_pack.py` provides the thin JSON CLI.
`tests/test_workflow_target_assessment.py` exercises the public entry points.
Previously none of these files or entry points existed.

Pack-local schema names are `target-assessment-pack-v1`,
`target-assessment-snapshots-v1`, `target-assessment-stage-v1` and the frozen
task manifest `target-assessment-benchmark-v1`. Existing claim-register,
manifest-plan and checkpoint fields are reused without modification.
History search `git log -S target-assessment-pack-v1 --
src/codex_science/target_assessment_pack.py` found no earlier writer in this
checkout. No existing stored record class is newly rejected or reviewed
differently by an existing validator.

## Focused check results

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

## Each test and fail-before evidence

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
No external record, ref, checkpoint or receipt is written by this implementation.

The checks cannot certify truthful source annotations, cohort completeness,
normalization accuracy, biological direction, semantic completeness or efficacy.
Literal attribution is conservative and refuses otherwise valid paraphrases.
Independent source/method review and coordinator admission remain necessary.
