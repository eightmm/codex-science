# Synthetic fixture verification evidence

All cases below are offline synthetic software controls. The inherited implementation was already present at dispatch; this is targeted check-removal evidence, not a claim that it was initially broken. No production code change remains.

For every row, a temporary git diff of non-test changes was saved, reverse-applied, and the named test ran alone with exit 1. The patch was reapplied, the same test ran alone with exit 0, and all temporary patches were deleted. Behavioural rows use a reversed diff from the disabled check to the checked implementation; the metadata row removes the new static artifacts. Every run used an outer timeout and the suite call timeout. Bytecode caches stayed in a removed temporary directory. No commit, stash or background process was used.

| Test in tests.test_workflow_power_pack | Removed check or mutation | Reverted exit | Restored exit |
| --- | --- | --- | --- |
| SeededDefectTests.test_observed_power | disable observed-power | 1 | 0 |
| SeededDefectTests.test_own_effect | disable effect-leakage | 1 | 0 |
| SeededDefectTests.test_missing_source | disable missing-source | 1 | 0 |
| SeededDefectTests.test_multiplicity | disable multiplicity-correction | 1 | 0 |
| SeededDefectTests.test_one_sided | disable one-sided-justification | 1 | 0 |
| SeededDefectTests.test_rounding | disable rounding-attrition | 1 | 0 |
| SeededDefectTests.test_attrition | disable rounding-attrition | 1 | 0 |
| SeededDefectTests.test_invalid_power | disable probability-range | 1 | 0 |
| SeededDefectTests.test_invalid_alpha | disable probability-range | 1 | 0 |
| SeededDefectTests.test_wrong_power | disable power-consistency | 1 | 0 |
| SeededDefectTests.test_post_outcome | disable post-outcome-change | 1 | 0 |
| SeededDefectTests.test_adequate | disable claim-boundary | 1 | 0 |
| SeededDefectTests.test_well_powered | disable claim-boundary | 1 | 0 |
| SeededDefectTests.test_clinical_meaning | disable claim-boundary | 1 | 0 |
| SeededDefectTests.test_null_no_effect | disable claim-boundary | 1 | 0 |
| SeededDefectTests.test_causal | disable claim-boundary | 1 | 0 |
| SeededDefectTests.test_review_approval | disable non-evidence | 1 | 0 |
| SeededDefectTests.test_computed_kind | disable non-evidence | 1 | 0 |
| SeededDefectTests.test_computed_result | disable non-evidence | 1 | 0 |
| SeededDefectTests.test_unavailable_evidence | disable unavailable-evidence | 1 | 0 |
| SeededDefectTests.test_empty_evidence | disable claim-support | 1 | 0 |
| SeededDefectTests.test_unavailable_positive | disable unavailable-positive | 1 | 0 |
| SeededDefectTests.test_outside_alias | disable evidence-independence | 1 | 0 |
| SeededDefectTests.test_replicated | disable claim-replication | 1 | 0 |
| PowerTests.test_public_fixtures_hand_calculations_and_read_only_concurrency | replace math.ceil(scale ** 2) with math.floor(scale ** 2) | 1 | 0 |
| PowerTests.test_quantile_public_precision_and_invalid_edges | replace return (low + high) / 2 with return (low + high) / 2 + 0.01 | 1 | 0 |
| PowerTests.test_integer_fields_are_real_integers_everywhere | replace valid = type(value) is int if integer else type(value) in (int, float) with valid = type(value) in (int, float) | 1 | 0 |
| PowerTests.test_read_parse_once_per_inode_and_final_recheck | replace cached = self.artifacts.get(identity) with cached = None | 1 | 0 |
| PowerTests.test_root_swap_between_lstat_and_open | replace if _signature(before)[:2] != _signature(opened)[:2]: with if False: | 1 | 0 |
| PowerTests.test_ancestor_replaced_while_bundle_inode_survives | replace chain == self.chain with chain[-1] == self.chain[-1] | 1 | 0 |
| PowerTests.test_json_hostile_inputs_and_nonallocating_preparse | replace re.finditer(rb with re.findall(rb | 1 | 0 |
| PowerTests.test_transient_ancestor_and_root_symlink_swap_at_open | replace flags = os.O_RDONLY &#124; os.O_NONBLOCK &#124; os.O_NOFOLLOW &#124; os.O_DIRECTORY with flags = os.O_RDONLY &#124; os.O_NONBLOCK &#124; os.O_DIRECTORY | 1 | 0 |
| PowerTests.test_assumption_failure_and_boundary_edges | disable nuisance-range | 1 | 0 |
| PowerTests.test_freeze_exploratory_domain_and_stage_order | disable stage-order | 1 | 0 |
| PowerTests.test_reference_limits_degenerate_inputs_and_binary_upper_half | disable sample-size-limit | 1 | 0 |
| PowerTests.test_claim_wording_types_unavailable_and_evidence_order | disable claim-boundary | 1 | 0 |
| PowerTests.test_prior_source_and_output_aliases | disable evidence-independence | 1 | 0 |
| PowerTests.test_aggregate_and_dimension_limit_edges | disable input-limit | 1 | 0 |
| PowerTests.test_canonical_paths_hashes_and_special_files | disable input-path | 1 | 0 |
| PowerTests.test_replacement_and_growth_during_validation | disable input-changed | 1 | 0 |
| PowerTests.test_cli_success_argument_errors_and_help | restore plain argparse error | 1 | 0 |
| PowerTests.test_skill_quality_reference_and_benchmark_contracts | reverse new non-test skill/reference/benchmark patch | 1 | 0 |

The initial salvaged implementation already passed its scientific-defect refusals; no unsupported before-fix bug is asserted. Each seeded-defect test checks the exact stated code, so a later gate with a different finding cannot substitute for the removed check.

The validator and CLI write nothing. Concurrent validation leaves all bundle bytes unchanged; interruption leaves no bundle record or ref, and may leave a partial caller-captured stdout stream. The added skill, reference, quality, benchmark, README and evidence files are static authoring artifacts; they have no runtime writer. A concurrent author could overwrite a file, or interruption during authoring could leave a partial file, so the owner admits the complete patch and checks JSON parsing and reference audits before integration.
