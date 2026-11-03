# Synthetic fixture verification record

This is a software acceptance record for synthetic fixtures, not scientific evidence or independent review. All 47 test selections below passed in three focused groups: 15 arithmetic/design/type cases, 15 file/claim/CLI hardening cases and 17 seeded defects. Each run was bounded with timeout 180; CLI subprocesses use the suite call timeout. The exact module-wide harness command was deliberately left for owner admission, as requested.

## Fail-before evidence

A git diff of every non-test addition was saved to a temporary patch, reversed with git apply, and each test selection run once separately. All 47 selections failed on the pre-implementation tree because factorial_doe_pack is absent at HEAD. This demonstrates the absent entry point; it does not claim the test bodies reached their behavior assertions on HEAD. The patch was reapplied and removed afterward.

Each of the 17 seeded defect tests also failed when its finding-specific guard was removed, one at a time, and passed with the implementation restored. The temporary mutation bypassed only the matching labelled requirement. Some defects then encountered a later, differently labelled gate; exact refusal identity remains part of the tested contract. This is separate from the absent-module baseline.

The response-total caching regression additionally failed against the pre-fix implementation: each factorial condition was summed ten times instead of once. With cached totals, every condition is summed exactly once. The numerical expectations remain unchanged.

## Checks actually run

- Python 3 py_compile for the new validator, CLI and test module: passed.
- Both public fixture CLI invocations: arithmetic-only with review unavailable, exit 0.
- Missing, extra and unknown CLI arguments: JSON invalid-arguments refusal on stderr, exit 2. Help: plain usage on stdout, exit 0.
- python3 scripts/audit_skill_references.py --require-clean: zero findings.
- python3 scripts/audit_native_skill_maturity.py --require-clean: passed, zero findings.
- Default full catalog regeneration: blocked because this clone lacks vendor/scientific-agent-skills/skills. No download or installation was attempted.
- An authored-only sources configuration in temporary storage was audited through scripts/audit_skills.py; the new pack was active with no reasons. tests.test_catalog.CatalogAuditTests.test_representative_repository_prompts_rank_named_skill_first passed against an in-memory combination of those fresh authored records and the existing checked-in vendor inventory. This is a bounded substitute for full vendor regeneration. No generated catalog change was retained.
- git diff --check: passed. Existing tracked files are unchanged.
- git log -S for doe-pack-v1 across writers/tests/scripts and the new writer path returned no prior writer history; no earlier stored record class newly fails validation.
- Full repository fast checks, wrapper generation and the exact module-wide admission command were not run; owner regeneration/admission remains separate.

## Passing test selections

All names below belong to tests.test_workflow_doe_pack.DOEPackTests.

- test_bytes_budget_hardlink_and_parse_once
- test_centre_curvature_zero_crossing_and_negative
- test_claim_empty_unavailable_replication_and_types
- test_claim_kind_and_result_not_labels
- test_cli_success_refusal_arguments_and_help
- test_empty_design_lists_and_numeric_bounds
- test_external_alias_path_hash_and_hardlink
- test_file_replacement_and_growth
- test_final_hash_and_root_recheck
- test_fraction_fixture_hand_alias_sets
- test_full_fixture_hand_contrasts_pure_error_and_curvature
- test_full_k_four_and_k_one
- test_integer_fields_types_and_degenerate_error
- test_integer_report_and_interval_fields
- test_lstat_ancestor_swap_and_root_swap
- test_maximum_design_and_replicate_limits
- test_near_zero_comparison_has_no_absolute_tolerance
- test_negative_generator_sign_and_exploratory_coding
- test_new_dimension_limits_before_work
- test_no_replicates_and_significance_wording
- test_parent_swap_preserving_bundle_inode
- test_paths_special_files_and_missing
- test_preparse_and_cumulative_json_budget
- test_response_totals_cached_once_per_condition
- test_seed_curvature_ignored
- test_seed_inconsistent_generator
- test_seed_interval_without_replicates
- test_seed_overreach_causal_effect
- test_seed_overreach_clinical_action
- test_seed_overreach_efficacy
- test_seed_overreach_mechanism
- test_seed_overreach_optimal_conditions
- test_seed_overreach_physical_validity
- test_seed_overreach_process_validity
- test_seed_overreach_scale_up
- test_seed_post_hoc_levels
- test_seed_separate_aliases
- test_seed_unbalanced_columns
- test_seed_unbalanced_replicates
- test_seed_unfrozen_rules
- test_seed_wrong_run_order
- test_strict_json
- test_t_quantiles_against_closed_forms
- test_table_identity_counts_resolution_and_response_types
- test_transient_ancestor_and_root_symlink_swaps
- test_unavailable_mixed_evidence_all_statuses
- test_wording_families_and_refusal_order

## Seeded refusal identity checks

- unbalanced-columns: non-orthogonal; guard removed -> regression failed; restored -> passed.
- unbalanced-replicates: unbalanced-replicates; guard removed -> regression failed; restored -> passed.
- inconsistent-generator: fraction-generators; guard removed -> regression failed; restored -> passed.
- separate-aliases: alias-separation; guard removed -> regression failed; restored -> passed.
- interval-without-replicates: inference-without-replicates; guard removed -> regression failed; restored -> passed.
- wrong-run-order: run-order; guard removed -> regression failed; restored -> passed.
- curvature-ignored: curvature-omitted; guard removed -> regression failed; restored -> passed.
- post-hoc-levels: post-hoc-coding; guard removed -> regression failed; restored -> passed.
- unfrozen-rules: rule-freeze; guard removed -> regression failed; restored -> passed.
- overreach-optimal-conditions: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-mechanism: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-causal-effect: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-scale-up: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-process-validity: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-physical-validity: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-clinical-action: claim-overreach; guard removed -> regression failed; restored -> passed.
- overreach-efficacy: claim-overreach; guard removed -> regression failed; restored -> passed.

## Concurrency, interruption and uncertainty

The validator and CLI write no files, refs or records. A second call reads its own pinned snapshot; interruption leaves supplied files unchanged and may truncate stdout. A caller must capture durable result artifacts atomically. The checked-in rules, tables, reports, expected artifacts, references and benchmark definitions are immutable synthetic fixture inputs. Validation does not update them, even on refusal.

L4 denotes offline fixture coverage only. Historical freeze timing, actual randomisation, source independence, error-model assumptions, physical validity and independent scientific review remain unverified. Claim wording is a conservative English lexical gate and is incomplete for paraphrases and other languages. The result always reports review unavailable.
