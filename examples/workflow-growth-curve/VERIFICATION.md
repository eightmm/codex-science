# Synthetic fixture verification

These observations concern synthetic fixtures and software acceptance only. They establish no biological or physical validity and no independent review.

The focused module is `tests/test_workflow_growth_pack.py`: 44 tests, run as two bounded groups on Python 3.12. The first group contains 7 GrowthReferenceTests and 19 GrowthSeededTests; the second contains 3 GrowthClaimTests, 12 GrowthInputTests and 3 GrowthLimitTests. Both groups pass. The complete harness verification command is reserved for owner admission and was not run by the worker.

```bash
timeout 60 env PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_growth_pack.GrowthReferenceTests tests.test_workflow_growth_pack.GrowthSeededTests
timeout 60 env PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_growth_pack.GrowthClaimTests tests.test_workflow_growth_pack.GrowthInputTests tests.test_workflow_growth_pack.GrowthLimitTests
```

Fail-before evidence: the initial accepting-fixture test failed because the growth module was absent. A temporary added-file git patch of all non-test additions was then applied in reverse; all 44 individual test IDs failed with the module absent. The non-test patch was reapplied and the temporary patch deleted. Separately, each of the 19 named seeded tests failed when its finding guard was disabled, one mutation at a time; the original code was restored and all focused tests passed again. These guard-removal checks verify the stated refusal reason; absent-module checks only establish that the new pack is required.

The seeded API and CLI checks cover saturated capacity, omitted subtraction, unlabelled post-outcome window changes, nonpositive corrected log OD, unreliable summary contributors, technical replication, grid mismatch, fitness, resistance, drug effect, mechanism, clinical relevance, review approval, computed evidence, external aliases, unavailable evidence, empty evidence, unavailable positive assertions and missing freeze. Extra focused checks cover hand-derived numbers, zero variance, near-zero relative ties, explicit flags, finite numeric types, CLI argument/help channels, FIFO/directory/symlink/oversized inputs, strict JSON, byte/value/dimension budgets, hardlink caching, one initial and one final read per inode, replaced/growing files, root/ancestor races and concurrent readers.

`python3 scripts/audit_skill_references.py --require-clean` passes with zero findings. The native maturity audit accepts this pack as L4 for synthetic fixture acceptance only. Full catalog regeneration is blocked because `vendor/scientific-agent-skills/skills` is absent in this isolated checkout; no installation or download was attempted. Regenerating only local authored sources succeeds and marks the growth entry active with no reasons. The existing named-skill ranking test passes against that regenerated authored inventory combined with the checked-in vendor snapshot. This fallback does not establish that full inventory regeneration passes. The original tracked inventory was preserved.

No existing record class newly fails validation: these are six new pack-local schemas and no earlier growth writer exists in git history. Owner-owned registry, policy, wrappers, release files, changelog and global gates remain outside this patch. No full fast gate or live scientific validation was run. Runtime calls write no files or refs; repeated or concurrent calls leave every input unchanged. Interruption can truncate stdout but cannot leave a partial input or stored record. Failed controls and negative results remain in supplied immutable artifacts and caller-captured refusals.

## Exact focused test cases

- `GrowthReferenceTests.test_accepting_fixture`
- `GrowthReferenceTests.test_all_seeded_refusals_through_cli`
- `GrowthReferenceTests.test_exploratory_window_is_recomputed`
- `GrowthReferenceTests.test_hand_derived_logistic_descriptors_and_group_errors`
- `GrowthReferenceTests.test_nonpositive_and_degenerate_curves`
- `GrowthReferenceTests.test_relative_ties_and_near_zero_distinct_slopes`
- `GrowthReferenceTests.test_saturation_equality_too_few_and_qc_flags`
- `GrowthSeededTests.test_blank_not_subtracted`
- `GrowthSeededTests.test_clinical`
- `GrowthSeededTests.test_computed_result`
- `GrowthSeededTests.test_drug_effect`
- `GrowthSeededTests.test_empty_evidence`
- `GrowthSeededTests.test_external_alias`
- `GrowthSeededTests.test_fitness`
- `GrowthSeededTests.test_grid_mismatch`
- `GrowthSeededTests.test_mechanism`
- `GrowthSeededTests.test_negative_log_od`
- `GrowthSeededTests.test_post_outcome_window`
- `GrowthSeededTests.test_resistance`
- `GrowthSeededTests.test_review_kind`
- `GrowthSeededTests.test_saturated_capacity`
- `GrowthSeededTests.test_technical_replication`
- `GrowthSeededTests.test_unavailable_evidence`
- `GrowthSeededTests.test_unavailable_positive`
- `GrowthSeededTests.test_unfrozen`
- `GrowthSeededTests.test_unreliable_summary`
- `GrowthClaimTests.test_external_identity_aliases_and_boundary_order`
- `GrowthClaimTests.test_positive_record_kind_and_result_and_unavailable_mixture`
- `GrowthClaimTests.test_wording_families_all_statuses_and_unhashable_fields`
- `GrowthInputTests.test_aggregate_budgets_equality_zero_and_hardlink_cache`
- `GrowthInputTests.test_canonical_paths_hashes_and_symlink_components`
- `GrowthInputTests.test_cli_argument_success_help_and_refusal_channels`
- `GrowthInputTests.test_directory_replaced_after_lstat_and_root_replaced_at_finish`
- `GrowthInputTests.test_input_replaced_and_growing_during_read`
- `GrowthInputTests.test_nonregular_symlink_and_oversized_inputs`
- `GrowthInputTests.test_parent_replaced_while_bundle_inode_is_preserved`
- `GrowthInputTests.test_protocol_freeze_precedes_od_and_repeated_concurrent_calls_write_nothing`
- `GrowthInputTests.test_reads_once_and_rechecks_once_per_inode`
- `GrowthInputTests.test_root_and_ancestor_swap_between_lstat_and_open`
- `GrowthInputTests.test_strict_json_preparse_budget_and_no_findall_allocation`
- `GrowthInputTests.test_well_identity_blank_controls_and_strict_grids`
- `GrowthLimitTests.test_dimension_limits_equal_zero_empty_malformed_and_oversize`
- `GrowthLimitTests.test_every_declared_integer_and_nonfinite_numeric_types`
- `GrowthLimitTests.test_metadata_plan_and_named_failure_coverage`
