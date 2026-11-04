# Synthetic fixture verification record

This record describes offline software checks of synthetic fixtures only. It is not independent scientific review, observed evidence or acceptance of either measurement method.

## What changed and why

The additive workflow-bland-altman-agreement pack freezes paired-unit rules, admits hash-bound synthetic measurements and recomputes descriptive bias, limits, confidence intervals, regression t tails and moment controls. It refuses unsupported method claims and never marks its output reviewed. Production entry points write no files, refs or records: a second concurrent call reads independently; interruption leaves inputs unchanged and may truncate stdout. The coordinator must capture durable output atomically.

Only the new skill directory, synthetic examples, frozen benchmark, validator, thin CLI and tests are supplied. Existing registry, policy, global schemas, tooling and documentation are unchanged. git log -S ba-rules-v1 on the new validator path has no earlier writer; no existing stored record class gains a new validation bound or review behavior.

Pack-local schemas: ba-pack-v1, ba-rules-v1, ba-pairs-v1, ba-report-v1, ba-evidence-v1 and ba-result-v1. Domain artifacts and separate claim-register entries use existing coordinator contracts.

## Verification actually run

All 45 cases below passed in focused arithmetic, domain, hostile-input, claim-gate, CLI and seeded-defect groups on python3, each test command bounded by timeout 120. CLI subprocesses use the suite OMS_TEST_CALL_TIMEOUT. The full harness command PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_ba_pack was deliberately left to the owner as requested. Syntax checks passed for all three Python files. The final changed near-zero case also verifies scale invariance at measurements of order 1e-100.

The non-test additions were saved as a temporary git patch, reverse-applied, and every new test below was run individually once. All 45 failed with ImportError because the pre-change repository has no Bland–Altman module. The patch was reapplied in a finally block and the temporary directory removed. This is a structural baseline, not a claim that a prior numerical implementation existed. For stronger behavior evidence, each of the 17 seeded tests was also run once after temporarily disabling its specific finding guard in the validator source: every one failed. Original source was restored in a finally block.

python3 scripts/audit_skill_references.py --require-clean passed: 176 skills, 281 references, zero findings. python3 scripts/audit_native_skill_maturity.py --require-clean passed: 120 L3 and 56 L4 skills; this pack computed L4 with no reasons. The catalog entry is active and its description omits generic routing terms.

Default inventory regeneration could not finish because vendor/scientific-agent-skills/skills is missing in this clone. An initial command without PYTHONPATH also failed to import codex_science; rerunning with PYTHONPATH resolved that setup issue. A native-only catalog audit passed (173 skills), but merging every refreshed native entry into the existing inventory failed the existing Slurm routing expectation. This unrelated catalog behavior was not changed. The scoped check added only the freshly audited pack entry to the original inventory and tests.test_catalog.CatalogAuditTests.test_representative_repository_prompts_rank_named_skill_first passed. The original inventory was restored byte-for-byte after each attempt. Full multi-source regeneration and broad release/fast gates were not run successfully; the owner retains generated catalog and release integration.

Consumer searches covered tests, scripts, docs, README files, all new public functions, domain schema names, CLI usage and refusal wording. No pre-existing consumer references this new module. Pack-local prose documents every added record field and named bound. Hand arithmetic checks cover bias 2, SD sqrt(2), slope 13/175, t squared 338/3, 30-pair SD sqrt(50/29), t-based bias and both limit intervals, and natural-log scale quantities. Exact t tails are independently checked against df 1 and df 2 closed forms and a df 29 reference quantile.

## Individual test outcomes

Each listed case passed with the implementation and failed with ImportError under the reversed non-test patch.

- test_bytes_budget_hardlink_and_parse_once
- test_claim_empty_unavailable_replication_and_types
- test_claim_kind_and_result_not_labels
- test_cli_success_refusal_arguments_and_help
- test_collection_limits_before_work
- test_degenerate_and_minimum_pairs
- test_exact_t_closed_form_and_convergence
- test_external_alias_path_hash_and_hardlink
- test_file_replacement_and_growth
- test_final_hash_and_root_recheck
- test_fixture_hand_arithmetic_and_missingness
- test_freeze_precedes_opening_values_and_hash_identity
- test_integer_numeric_types_missingness_and_units
- test_limits_equal_zero_empty_and_malformed
- test_log_scale_and_original_scale_cannot_mix
- test_lstat_directory_identity_swap
- test_near_zero_comparison_has_no_absolute_tolerance
- test_no_detection_and_unit_order_without_extra_pairs
- test_normality_screen_and_bound_edges
- test_parent_swap_preserving_bundle_inode
- test_paths_special_files_and_missing
- test_preparse_and_cumulative_json_budget
- test_replicate_collapse_counts_units
- test_seed_correlation_as_agreement
- test_seed_correlation_text
- test_seed_ignored_proportional_bias
- test_seed_missing_interval
- test_seed_overreach_causality
- test_seed_overreach_clinical_acceptability
- test_seed_overreach_equivalence
- test_seed_overreach_interchangeability
- test_seed_overreach_method_validity
- test_seed_overreach_physical_validity
- test_seed_overreach_truth
- test_seed_post_hoc_bound
- test_seed_repeated_measures
- test_seed_too_few_interval
- test_seed_unfrozen_rules
- test_seed_unpaired_unit
- test_seed_wrong_log_scale
- test_strict_json
- test_thirty_pairs_intervals_by_hand
- test_transient_ancestor_and_root_symlink_swaps
- test_unavailable_mixed_evidence_all_statuses
- test_wording_families_and_refusal_order

## Seeded guard-removal outcomes

Each listed finding was disabled in the validator source for that single case; its test failed, then passed with the guard restored. A later different finding or structural exception also fails the test, protecting refusal ordering and the stated reason.

- correlation-as-agreement: correlation-as-agreement
- wrong-log-scale: difference-scale
- repeated-measures: repeated-measures
- missing-interval: agreement-interval
- too-few-interval: agreement-interval
- ignored-proportional-bias: proportional-bias
- unpaired-unit: unpaired-unit
- post-hoc-bound: post-hoc-bound
- unfrozen-rules: rule-freeze
- overreach-interchangeability: claim-overreach
- overreach-clinical-acceptability: claim-overreach
- overreach-equivalence: claim-overreach
- overreach-method-validity: claim-overreach
- overreach-causality: claim-overreach
- overreach-physical-validity: claim-overreach
- overreach-truth: claim-overreach
- correlation-text: correlation-as-agreement

## Remaining uncertainty

Synthetic acceptance establishes arithmetic and software refusals only. Normality, constant variance, independent units, method calibration, historical freeze timing and true external independence remain assumptions. The English lexical gate is conservative and incomplete. No clinical, physical, equivalence or interchangeability claim is validated, and independent review remains unavailable. The missing vendor checkout blocks full catalog regeneration; the owner must integrate generated inventory, wrappers, release bookkeeping and the changelog. No other implementation blocker remains.
