# Synthetic fixture acceptance record

What changed: 58 new files add the batch-effect assessment conductor, five-stage
references and existing plan shape, L4 quality declaration, CPU-only benchmark,
read-only validator/CLI, balanced and confounded synthetic fixtures, 27 complete
negative fixtures and tests. No existing source, contract, registry or dependency
is changed. All example data are redistributable synthetic fixtures.

Why: technical batch structure must be assessed under a hash-frozen design before
biological comparisons; confounding cannot establish absent batch structure or
adjusted attribution. Arithmetic, scientific interpretation and independent review
remain separate states.

Evidence: the balanced fixture yields batch R-squared 2/3, F 12; group R-squared
1/6, F 6/5; batch/group centroid scores 2/3 and 1/10; pseudo-F 12; and a seeded,
within-group permutation p-value 0.075. QC distance is 4 times square root of 5.
The confounded fixture has exact rank 2 for 3 columns and returns unassessable
with null metrics. See expected.json and confounded.expected.json for full JSON.

Implementation anchors: src/codex_science/batch_effect_assessment_pack.py holds
pinned ancestor/file descriptors, shared inode/byte/JSON budgets, exact rational
rank, frozen arithmetic controls, unavailable evidence and wording gates.
scripts/validate_batch_effect_assessment_pack.py provides the one-bundle JSON CLI,
including argument refusals; help is plain stdout. SKILL.md, references/stages.md,
references/plan.json, references/index.json, quality.json and agents/openai.yaml
under authored-skills/workflow-batch-effect-assessment define routing and handoff.
benchmarks/workflow-batch-effect-assessment/tasks.json freezes CPU-only questions.

Verification: the three focused classes in tests/test_workflow_batch_pack.py pass
53 tests with PYTHONPATH set to src:tests and python3 -m unittest. The exact full
module command is reserved for the admission harness, as directed by the brief.
Each test listed below was run once with the non-test add-file patch reversed:
all 53 failed because implementation was absent. The patch was reapplied and all
53 passed. The temporary patch was deleted. Each of the 27 seeded tests was also
run individually after removing its named refusal guard from the source: all 27
failed as required, then passed with guards restored. No git stash was used.

A further refusal-order regression first failed because citing the study's own
matrix as external evidence raised invalid-record before evidence-independence.
Moving the identity refusal before evidence-schema parsing fixes that test;
no existing record class changes validation behavior.

Syntax compilation and JSON/Markdown checks pass. The reference audit with
require-clean passes with zero major findings and two minor missing-link findings:
the task forbids Markdown link syntax, so required reference paths are plain text.
The native maturity audit with require-clean passes and admits L4. The existing
named-skill catalog routing test passes on the checked-in inventory, and also
with freshly regenerated authored records combined in memory with cached vendor
records. The new pack is catalog-active with no reasons. Two existing native
instruction contract tests pass. No network, GPU, install or remote work was run.

Skipped/blocked: the exact full catalog regeneration command cannot complete
because vendor/scientific-agent-skills/skills is absent from this isolated clone.
An initial attempt without PYTHONPATH also failed to import the source package;
using PYTHONPATH exposed the vendor prerequisite. Scoped authored regeneration
succeeds. Existing inventory bytes were restored after each attempt. Wrappers,
release bookkeeping, native policy, documentation counts and the changelog are
owner-managed and untouched. The broad fast gate is not run because admission
requests focused tests and those owner updates/vendor sources are absent. Public
or live checks are outside this offline task. There is no implementation blocker.

Local schemas: batch-effect-pack-v1, batch-effect-rules-v1,
batch-effect-matrix-v1, batch-effect-evidence-v1, batch-effect-result-v1.
No global schema, payload, MCP interface or earlier stored record class changes.
History search for the new pack schema found no earlier writer.

Concurrency/crash behavior: the validator writes no file, ref, record or input.
Every input artifact is admitted by immutable path/hash and descriptor identity;
hardlink aliases share parsing and final hash reads. A concurrent call has an
independent snapshot; an input or ancestor replacement is refused. A killed call
leaves inputs unchanged and may leave incomplete stdout, which must be discarded.
All newly authored files are static pack/code/test/fixture artifacts; publication
and checkpoint writes remain with the coordinator, not the validator.

Remaining uncertainty: synthetic arithmetic acceptance cannot prove source
identity, historical freeze timing, independence, biological validity or batch
removal. Exact rank follows decimal input representations. The conservative
English lexical gate is incomplete and refuses negations too. QC with no
cross-batch pairs remains unavailable. The coordinator owns rigor and independent
record, source and method review. The reference supports only frozen label-free
complete/nonconstant filtering and unadjusted one-way metrics.

Tests exercised:

BatchComputationTests:

- test_balanced_fixture_and_hand_arithmetic
- test_confounded_fixture_is_unassessable
- test_degenerate_and_extremely_small_values
- test_exact_rank_covariates_and_single_batch_rule
- test_failed_permutations_count_and_unexpected_errors_propagate
- test_inclusive_detection_and_qc_thresholds
- test_missingness_transform_exploratory_and_unavailable_qc
- test_permutation_implementation_preserves_every_group

BatchRefusalTests:

- test_identity_shape_and_rule_failures
- test_integer_fields_and_boolean_controls_are_strict
- test_negative_manifest_matches_real_cases
- test_positive_record_and_outside_identity_checks
- test_seeded_adjusted_text
- test_seeded_biological_signal
- test_seeded_causal
- test_seeded_clinical
- test_seeded_collinear_adjustment
- test_seeded_computed_kind
- test_seeded_computed_result
- test_seeded_confounded_absence
- test_seeded_confounded_text
- test_seeded_corrected
- test_seeded_differential_expression
- test_seeded_empty_evidence
- test_seeded_group_filter
- test_seeded_late_freeze
- test_seeded_mechanism
- test_seeded_outside_alias
- test_seeded_physical_validity
- test_seeded_post_outcome_threshold
- test_seeded_removed
- test_seeded_replicated
- test_seeded_review_approval
- test_seeded_review_truth
- test_seeded_sample_drop
- test_seeded_unavailable_batch
- test_seeded_unavailable_evidence
- test_seeded_unavailable_positive
- test_seeded_unstratified_permutation
- test_unavailable_citations_all_statuses_and_mixed_support
- test_unhashable_and_wrong_field_types_are_labelled
- test_wording_families_and_boundary_refusal_order

BatchBoundaryTests:

- test_aggregate_byte_node_and_artifact_limits
- test_artifact_replacement_and_growth_are_detected
- test_cli_success_refusals_help_and_no_writes
- test_duplicate_deep_nonobject_nonfinite_and_huge_json
- test_empty_zero_malformed_and_limit_dimensions
- test_hardlink_alias_is_read_and_parsed_once
- test_json_string_depth_and_container_limits
- test_parent_swap_preserving_bundle_inode_and_final_root_swap
- test_paths_files_and_sparse_oversize_are_refused
- test_root_and_transient_ancestor_swaps_are_refused
- test_rule_freeze_precedes_any_matrix_open

Proposed CHANGELOG bullet:

- Add workflow-batch-effect-assessment with frozen design controls, exact confounding refusals, group-stratified batch metrics, hardened read-only validation and synthetic acceptance fixtures.
