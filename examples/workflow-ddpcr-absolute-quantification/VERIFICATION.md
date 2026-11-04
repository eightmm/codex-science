# Synthetic ddPCR verification evidence

All examples and results are synthetic fixtures. Checks use local CPU and the standard library, with no network.

The new module has no earlier writer or stored record class in git history. Existing contracts and stored records are unchanged. Before the feature existed there was no callable ddPCR entry point. For fail-before evidence, save the non-test additions as a git patch, reverse-apply it, invoke every test case separately in a fresh interpreter, and reapply the patch in a finally block. All 49 cases fail on the absent module; this establishes missing-feature failure rather than a pre-existing numerical bug. After restoration, all 49 pass through focused suites. The owner runs the complete module command independently.

For stronger seeded-defect evidence, temporarily disable the matching finding guard in _require on disk, run the associated seeded test once in a fresh interpreter, and restore the exact original module bytes. All 18 seeded tests fail as assertions with their guard disabled and pass with it restored. Some retain a later generic refusal; the seeded tests require the distinct stated finding, so those failures also establish refusal-order coverage. The mutations and their findings are enumerated in negative-cases.json.

Hand checks independently solve finite binomial tail equations for 1/2, 2/4, 4/8, 1/20 and 19/20 positives. For 1/2 positives at confidence 0.95, endpoints are 1-sqrt(0.975) and sqrt(0.975). The primary example has pooled lambda ln(2), concentration 12 ln(2), and zero-positive upper concentration -12 ln(0.025)/8. An unequal-denominator example proves pooling sums partitions rather than averaging well concentrations.

Syntax parsing passes for the module, CLI and tests. The reference audit with --require-clean reports zero findings; the native maturity audit with --require-clean passes. The authored-only catalog audit passes and the new skill is active. The named-skill ranking test passes against both the checked-in inventory and an in-memory addition of audited ddPCR metadata. Complete catalog regeneration is blocked by the absent vendor/scientific-agent-skills/skills tree; no installation or download was attempted, and catalog/inventory.json was restored byte-for-byte. Generated wrappers, batch documentation and the full fast gate remain owner integration work. A first catalog invocation without PYTHONPATH failed on import; the corrected invocation exposes the vendor prerequisite.

Two concurrent CLI validations return identical accepted JSON and leave every fixture byte unchanged. The validator writes no files, records or refs; termination between reads leaves input bytes untouched. Test materialization writes only unique temporary bundles; termination during those writes can leave an incomplete temporary bundle, which fails hash/schema checks and is never a published record. Checked-in pack files are immutable inputs at runtime.

Searches cover new functions, record fields, finding/output text, file names and CLI usage in tests, scripts, docs and README files. There is no existing ddPCR consumer to edit. New selection text avoids generic routing terms; references document the complete local schemas, inclusive bounds, relative-only numeric tolerance and claim wording families.

## Focused cases

Each method below belongs to tests.test_workflow_ddpcr_pack.DDPCRPackTests. Test runs are bounded with timeout; subprocess calls use OMS_TEST_CALL_TIMEOUT. The harness retains the complete-module verification command. No operator smoke test is relevant.

- test_all_report_integer_fields_are_strict
- test_artifact_limit_hash_binding_and_freeze_order
- test_binomial_edges_types_and_convergence
- test_bytes_budget_hardlink_and_parse_once
- test_claim_empty_unavailable_replication_and_types
- test_claim_kind_and_result_not_labels
- test_cli_success_refusal_arguments_and_help
- test_collection_limits_before_work
- test_external_alias_path_hash_and_hardlink
- test_file_replacement_and_growth
- test_final_hash_and_root_recheck
- test_fixture_hand_arithmetic_and_exact_tails
- test_identities_missing_empty_and_pooled_limit
- test_integer_fields_and_numeric_rule_bounds
- test_interval_label_cannot_hide_normal_numbers
- test_near_zero_comparison_has_no_absolute_tolerance
- test_parent_swap_preserving_bundle_inode
- test_partition_weighted_pooling_not_mean_concentration
- test_paths_special_files_and_missing
- test_preparse_and_cumulative_json_budget
- test_qc_failures_preserve_unavailable_and_counts
- test_record_key_types_and_empty_evidence_documents
- test_seed_dilution_scaling_ignored
- test_seed_discordant_replicates_pooled
- test_seed_log_of_zero
- test_seed_missing_ntc
- test_seed_normal_interval
- test_seed_ntc_contamination_ignored
- test_seed_overreach_causality
- test_seed_overreach_clinical_relevance
- test_seed_overreach_copy_number
- test_seed_overreach_disease
- test_seed_overreach_gene_dosage
- test_seed_overreach_physical_validity
- test_seed_poisson_correction_omitted
- test_seed_positive_exceeds_total
- test_seed_post_outcome_threshold
- test_seed_saturated_quantified
- test_seed_too_few_partitions
- test_seed_unfrozen_rules
- test_strict_json
- test_threshold_edges_agreement_and_exploratory
- test_transformed_interval_singularity_and_nonfinite
- test_transient_ancestor_and_root_symlink_swaps
- test_unavailable_flags_and_report_method
- test_unavailable_mixed_evidence_all_statuses
- test_wording_families_and_refusal_order
- test_rule_numeric_limit_edges_and_failure_exits
- test_empty_zero_and_equal_resource_limits
