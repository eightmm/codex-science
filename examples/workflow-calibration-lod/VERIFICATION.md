# Synthetic fixture verification

All data and negative variants in this directory are synthetic fixtures.
Verification checks software and arithmetic only. No real assay or independent
scientific review was performed. No previous runtime wrote these new pack-local
record classes (`git log -S calibration-lod-pack-v1` on the new writer is empty).

The 60 cases in `tests.test_workflow_cal_pack.CalibrationPackTests` were run in
bounded, foreground Python 3 groups: 31 seeded refusals, 12 arithmetic and
contract checks, 16 untrusted-input, CLI and concurrency checks, and one final
small-limit edge check. All passed (0.093 s, 0.036 s, 0.340 s and 0.010 s
respectively in this checkout). These are local
timings, not runtime guarantees. The exact full-module verify command is left
to the owning harness as requested.

## Arithmetic and contract cases

- test_reference_hand_calculations
- test_weighted_fits_and_frozen_zero_match_rational_normal_equations
- test_blank_mean_rule_and_minimum_blank_edge
- test_unknown_edges_and_no_silent_extrapolation
- test_failed_controls_retained_without_exclusion_or_unknown_quantification
- test_minimum_level_replicate_and_exclusion_edges
- test_report_counts_are_real_integers
- test_all_input_integer_fields_are_strict
- test_threshold_equality_and_loq_at_standard_edges
- test_protocol_rule_type_and_range_refusals
- test_exploratory_weights_require_separate_frozen_bundle
- test_nonpositive_slope_and_weight_underflow_refused

Hand constants are derived in README.md. Weighted fits and frozen zero-intercept
fits are independently compared to exact rational normal equations. Edge cases
include equality at deviation thresholds, LOQ at both standard endpoints,
minimum levels/replicates/blanks, zero, empty and malformed inputs.

## Untrusted-input, CLI and concurrency cases

- test_bad_types_never_leak_type_or_key_errors
- test_json_duplicate_nonfinite_huge_deep_and_root_refusals
- test_json_limits_precede_parser_and_do_not_allocate_match_list
- test_row_and_claim_budgets_before_per_item_work
- test_hardlink_aliases_share_parse_and_aggregate_budgets
- test_regular_file_size_path_hash_and_link_refusals
- test_artifact_symlink_component_refused
- test_growing_file_refused
- test_input_replacement_at_final_hash_check_refused
- test_root_swap_at_open_refused
- test_transient_ancestor_swap_at_lstat_refused
- test_changed_parent_with_same_bundle_inode_refused
- test_claim_families_and_absence_are_not_positive_evidence
- test_cli_success_refusal_arguments_and_help
- test_validator_writes_nothing_and_repeated_calls_match
- test_concurrent_calls_match_without_writes
- test_small_limit_equality_zero_and_malformed_edges

Input limits are patched down and checked at their exact boundaries and one
below; the row test also supplies a deterministic 10,001-row unknown list.
Hardlink aliases parse once and share budgets. Root/ancestor races are injected
at os.open/os.lstat and after admission while retaining the bundle inode.
The JSON test patches re.findall to raise, so allocating a regex match list
would fail it. CLI tests cover success, seeded refusal, missing file, missing/
extra/unknown arguments, a refused output option and plain --help.

## Seeded refusal and fail-before evidence

`negative-cases.json` is the authoritative list of 31 IDs, bundle paths and
expected finding codes. Each becomes a separate test named `test_seeded_`
followed by its ID with hyphens replaced by underscores; all 31 passed.

For every case, its relevant finding guard was temporarily removed from the
new module, that individual test was run once, and it failed. The module was
restored after every probe. For constant-response, disabling explicit
degenerate-fit guards still leaves a second labelled ZeroDivisionError fallback;
removing that fallback too makes its test fail. This distinguishes redundant
refusal coverage from a guard-removal probe that merely reaches the same code.

Separately, a git diff of all non-test additions was saved to session temporary
storage and applied in reverse. Every one of the 60 new cases was selected once
against HEAD and failed at import because the new module did not exist there.
The patch was reapplied and removed from temporary storage. Those import failures
are the available pre-feature baseline; the 31 individual guard-removal probes
provide behavior-specific fail-before evidence. The final grouped runs above
passed after restoration. No git stash, commit, push or background test was used.

## Audits, scope and remaining gaps

`audit_skill_references.py --require-clean` passed with 161 indexed skills,
251 references and zero findings. `audit_native_skill_maturity.py --require-clean`
passed and computed this pack as L4. Syntax compilation passed for both Python
entry files and the test module. Source/reference searches cover the new public
entry points, local record keys, finding text, filenames and CLI usage.

The requested full inventory regeneration was attempted and refused because
the isolated clone lacks `vendor/scientific-agent-skills/skills`. No install,
download or vendor change was attempted. The named-skill catalog ranking test
passed with this skill's audited record added to the existing inventory in
memory; the on-disk inventory was restored byte for byte. Wrappers, catalog,
global docs, release metadata, dependency and toolchain files remain owner work.
The repository-wide fast gate was not run: its generated inventory and global
status-document updates exceed this worker's add-only scope. The owner retains
integration, full verification and final acceptance.

The validator writes no file, ref or record, including for a second concurrent
call. A killed call leaves input bytes untouched. Tests write only their own
temporary fixture copies and remove them. All added source/reference/fixture
files are static repository artifacts, not runtime writers. Historical freeze
timing, measurement authenticity and physical or clinical validity remain
unavailable; review approval could not establish truth.
