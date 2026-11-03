# Verification of synthetic diagnostic fixtures

All inputs and expected artifacts are synthetic software fixtures. None is
clinical validation, source verification or independent review.

## Unavailable-evidence review follow-up

- Added `DiagnosticHardeningTests.test_unavailable_support_requires_unavailable_status`:
  either evidence field, both fields, single and mixed support in both orders,
  all eight statuses, and the retained refusal of available-only replication.
- Added `DiagnosticHardeningTests.test_cli_refuses_unavailable_support_without_writes`:
  unsupported claims citing unavailable results return exit 2 and labelled JSON
  on stderr, with empty stdout and unchanged bundle files.
- Both tests failed on the original source. A temporary non-test git diff was
  also reverse-applied; each new test failed individually with exit 1, then the
  diff was reapplied in a finally block and the temporary patch was removed.
- All three test classes passed together: 50 tests under Python 3 with
  `PYTHONPATH=src:tests` and `timeout 120`. All 25 existing negative fixtures
  retain their stated finding codes. The owner-reserved bare module command
  remains for harness admission; the three classes cover the complete module.
- The clean validator returned exit 0 with empty stderr and an exact
  `expected.json` match. CLI `--help` and syntax compilation also passed.
- Both required audits passed with `--require-clean`: 155 skills, zero
  reference findings; this pack still declares and computes L4.
- Existing empty-support, unavailable-positive wording and real-integer field
  checks passed; no additional gap was reproduced in those documented checks.

No numerical limit, payload field or runtime writer changed. History search
`git log --all -S diagnostic-accuracy-evidence-v1 -- src scripts` identifies the
initial pack addition; the validator is read-only and its CLI only emits JSON.
Existing `diagnostic-accuracy-pack-v1` artifacts citing unavailable evidence now
fail `unavailable-evidence` for planned, conflicting, unsupported and withdrawn
claims. Supported and suggestive claims remain refused with this more specific
code; replicated claims also report it before the replication refusal. An
unavailable claim remains admissible. Other existing negative fixture codes and
the clean result are unchanged.

Production calls still write no file, ref or record. New test fixtures use
independent temporary directories and normal unittest cleanup; a hard kill may
leave only test files in temporary storage. No shared runtime write or partial
stored result is introduced. Full-repository and scientific efficacy checks
remain outside this bounded offline review.

## Original pack acceptance checks

- Python 3 focused groups: `DiagnosticComputationTests`,
  `DiagnosticSeededRefusalTests`, `DiagnosticHardeningTests` in exact module
  `tests.test_workflow_diagnostic_pack`; 48 tests total. Groups were invoked
  explicitly with `PYTHONPATH=src:tests` and `timeout 120`.
- Each of the 25 seeded cases was run alone with its named `_require` finding
  guard temporarily disabled in source. Every individual test returned exit 1
  with one assertion failure; all 25 passed after source restoration.
- The new malformed-bundle-path regression failed before its fix with unlabelled
  `ValueError: embedded null byte`, and passed with the `input-path` guard.
- A deterministic root replacement during the final artifact hash reads was
  initially accepted. Its new test failed before moving the visible-root check
  after those reads, then passed with the corrected check order.
- A temporary git diff of all non-test additions was applied in reverse;
  each new test was run individually against that source-absent tree, then
  the patch was reapplied in a finally block. Every test failed without the
  implementation. No git stash, commit or push was used.
- `python3 -m py_compile` passed for the new module, thin CLI and test file.
- `python3 scripts/audit_skill_references.py --require-clean`: no findings.
- `python3 scripts/audit_native_skill_maturity.py --require-clean`: passed;
  this pack declared/computed L4 with five local schemas and 25 seeded cases.
- Catalog named-skill ranking and the native skill decision-contract and
  connector-guidance checks passed (three tests) using a temporary refresh of
  authored-source entries merged with the checked-in inventory. The inventory
  was restored byte-for-byte afterward; this pack was active with no reasons.
- CLI fixture success, labelled refusal, JSON streams, unchanged files and
  `--help` were checked. The CLI takes one `bundle` argument and has no output
  option. Tests use the suite call timeout rather than fixed sleeps.

## Skipped and bounded checks

The owner-reserved full-module verification command was not run; focused groups
cover the new code. No network, GPU, remote compute, installation or dependencies
were used. Full inventory regeneration failed because the vendored
`vendor/scientific-agent-skills/skills` tree is absent in this clone. Its first
attempt also needed `PYTHONPATH=src`; the corrected attempt reached the missing
vendor check. No generated changes remain. Full repository `check.sh fast`,
wrapper generation and documentation count snapshots are left to the owner batch
that regenerates registry/release bookkeeping; this worker may not edit those
files. No live-source or clinical/held-out efficacy check was performed.

## Individual tests

Every method below is in `tests.test_workflow_diagnostic_pack` and was included
in the source-reverted fail-before check and the restored focused-group checks.

### DiagnosticComputationTests

- `test_bootstrap_failure_counts_and_only_specific_error_is_swallowed`
- `test_cli_success_failure_and_no_writes`
- `test_disclosed_unblinding_and_unavailable_claim`
- `test_exact_ties_direction_and_inclusive_threshold`
- `test_fixture_and_hand_calculations`
- `test_predictive_prevalence_edges_and_undefined_denominators`
- `test_training_selection_never_uses_evaluation_labels`

### DiagnosticSeededRefusalTests

- `test_causal`
- `test_clinical_utility`
- `test_computed_kind`
- `test_computed_result`
- `test_constant_scores`
- `test_empty_evidence`
- `test_evaluation_threshold`
- `test_incorporation_bias`
- `test_insufficient_cases`
- `test_insufficient_controls`
- `test_missing_prevalence`
- `test_missing_reference`
- `test_outside_alias`
- `test_physical_validity`
- `test_post_outcome_freeze`
- `test_prevalence_transfer`
- `test_review_approval`
- `test_score_selected_verification`
- `test_screening_recommendation`
- `test_subject_leakage`
- `test_unavailable_positive`
- `test_unblinded_reference`
- `test_undefined_class`
- `test_verification_bias`
- `test_wrong_predictive_value`

### DiagnosticHardeningTests

- `test_root_replacement_during_final_hash_reads`
- `test_total_input_budgets_before_reading`
- `test_bad_bundle_path_is_labelled`
- `test_byte_limit_exact_zero_and_growth`
- `test_claim_and_support_limits_before_record_scans`
- `test_claim_wording_all_statuses_whole_words_and_sources`
- `test_input_replacement_and_hash_recheck`
- `test_integer_fields_and_key_types`
- `test_json_duplicates_nonfinite_roots_depth_strings_and_huge_numbers`
- `test_numeric_and_row_limits`
- `test_paths_hashes_and_special_files`
- `test_protocol_freeze_is_checked_before_case_labels_are_opened`
- `test_read_once_parse_cache_and_final_verification`
- `test_remaining_dimension_edges_and_record_integer_versions`
- `test_replaced_root_at_final_recheck`
- `test_root_and_ancestor_symlink_swap_at_open`

## Individual refusal guard checks

| Synthetic case | Disabled finding guard | Individual result |
| --- | --- | --- |
| evaluation-threshold | `evaluation-threshold` | fails disabled; passes restored |
| verification-bias | `verification-bias` | fails disabled; passes restored |
| score-selected-verification | `verification-bias` | fails disabled; passes restored |
| incorporation-bias | `incorporation-bias` | fails disabled; passes restored |
| subject-leakage | `subject-leakage` | fails disabled; passes restored |
| insufficient-cases | `insufficient-class` | fails disabled; passes restored |
| insufficient-controls | `insufficient-class` | fails disabled; passes restored |
| missing-prevalence | `predictive-prevalence` | fails disabled; passes restored |
| prevalence-transfer | `predictive-prevalence` | fails disabled; passes restored |
| wrong-predictive-value | `predictive-value` | fails disabled; passes restored |
| constant-scores | `constant-scores` | fails disabled; passes restored |
| undefined-class | `undefined-class` | fails disabled; passes restored |
| missing-reference | `missing-reference` | fails disabled; passes restored |
| unblinded-reference | `unblinded-reference` | fails disabled; passes restored |
| post-outcome-freeze | `protocol-freeze` | fails disabled; passes restored |
| clinical-utility | `claim-boundary` | fails disabled; passes restored |
| screening-recommendation | `claim-boundary` | fails disabled; passes restored |
| causal | `claim-boundary` | fails disabled; passes restored |
| physical-validity | `claim-boundary` | fails disabled; passes restored |
| review-approval | `non-evidence` | fails disabled; passes restored |
| computed-kind | `non-evidence` | fails disabled; passes restored |
| computed-result | `non-evidence` | fails disabled; passes restored |
| empty-evidence | `claim-support` | fails disabled; passes restored |
| unavailable-positive | `unavailable-positive` | fails disabled; passes restored |
| outside-alias | `evidence-independence` | fails disabled; passes restored |

## Scope, records and interrupted calls

The original additions were under the six authorized path families and had no
earlier runtime writer. The review follow-up above records the newly refused
`diagnostic-accuracy-pack-v1` artifacts. Local schemas are `diagnostic-accuracy-pack-v1`,
`diagnostic-accuracy-protocol-v1`, `diagnostic-accuracy-cases-v1`,
`diagnostic-accuracy-evidence-v1`, `diagnostic-accuracy-result-v1`.

The validator/CLI writes no file, ref, checkpoint or record. Repeated concurrent
calls use local state and independent seeded RNGs and leave each protocol, case,
evidence and entry file unchanged. A kill between validation operations leaves
those files intact and may leave partial stdout in the caller's capture; no
half-written bundle or result is created here. The coordinator must capture any
result atomically outside the input bundle and register its hash separately.
Fixtures, expected artifacts, plan, metadata and benchmark records are immutable
checked-in inputs, not runtime writer targets. The review leaves the checked-in
JSON fixtures, expected result, plan and benchmark records unchanged.

Hash/timestamp/blinding declarations do not independently verify historical
freezing, actual blinding, source accuracy, missing upstream subjects or genuine
external independence. The English lexical claim filter is deliberately
conservative, incomplete and rejects negations. Review remains unavailable;
source, record and method review and rigor classification belong to the
coordinator. Nominal intervals and predictive-value transport assumptions do not
establish screening recommendations or clinical utility.
