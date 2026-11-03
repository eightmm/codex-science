# Verification of synthetic Western blot fixtures

All inputs, expected outputs and negative cases are synthetic fixtures. These checks establish software behavior only. Independent scientific review remains unavailable.

The focused Python 3 checks explicitly selected all 42 cases of tests.test_workflow_wb_pack.WBPackTests, each bounded with timeout. Result: Ran 42 tests; OK. The harness-owned whole-module verification command was left to admission.

Fail-before evidence: saved all non-test additions as a temporary git patch, reversed it without stash, ran each of the 42 individual tests once and observed ImportError because the new implementation was absent, then reapplied the patch and checked exact byte hashes. This establishes feature absence, not a pre-existing arithmetic defect. Every test passed with implementation restored.

Mutation evidence: for each of the 18 seeded negative cases, temporarily disabled its named labelled guard in the source, ran only that individual test and observed failure, then restored source. Also disabled band-identity for the antibody-pair regression and observed that test fail. All 19 guard-removal probes were detected. A guard removal can expose a later different refusal or an error; tests require the distinct stated finding, not merely any refusal. Source and input bytes were restored before the passing run.

Reference audit with --require-clean: exit 0, zero findings. Native skill maturity audit with --require-clean: exit 0, passed. Python syntax compilation passed. New-file whitespace checks passed. Consumer search covered 123 added function, field, schema, filename, option and output terms across tests, scripts, docs and README files; WB-specific consumers are the new CLI/test module and the new local references.

Full multi-source inventory regeneration was attempted and refused because the vendored scientific-agent-skills catalog is absent in this isolated clone. The authored-only audit succeeded, marked this pack active with no reasons, and the existing representative catalog-ranking test passed with the new audited entry added temporarily to the existing inventory. The original inventory bytes were restored. Full fast/whole-suite and wrapper generation were skipped: integration bookkeeping belongs to the owner, and full source regeneration lacks the vendor tree. No network, download, install, GPU or remote check was run.

No pre-existing tracked file changed. A git log -S search found no historical wb-rules-v1 writer at the new module path; no existing stored record class newly fails validation. All six schemas are pack-local. Existing global schema and MCP contracts are unchanged.

The validator and reference computation write no file, ref or stored record. Two concurrent validations return identical results and leave all input bytes unchanged. A kill between reads preserves supplied artifacts and may truncate stdout; callers must capture durable output atomically. The temporary reverse patch and mutation files were removed after checks.

The Welch log-delta interval is approximate, assumes independent biological units, and omits reference-lane calibration uncertainty. Shared blot references induce dependence. Frozen hashes prove byte identity, not historical preregistration or true independence. The conservative English claim gate is incomplete. No biological or clinical conclusion is established.

## Tests exercised

- test_all_dimension_limits_equal_excess_empty_and_types
- test_bytes_budget_hardlink_and_parse_once
- test_claim_empty_unavailable_replication_and_types
- test_claim_kind_and_result_not_labels
- test_cli_success_refusal_arguments_and_help
- test_collection_limits_before_work
- test_external_alias_path_hash_and_hardlink
- test_file_replacement_and_growth
- test_final_hash_and_root_recheck
- test_fixture_hand_arithmetic
- test_integer_fields_identity_series_and_reference
- test_near_zero_comparison_has_no_absolute_tolerance
- test_parent_swap_preserving_bundle_inode
- test_paths_special_files_and_missing
- test_preparse_and_cumulative_json_budget
- test_range_saturation_cv_and_exploratory_edges
- test_report_counts_types_freeze_order_hash_and_partial_missing
- test_root_replaced_between_lstat_and_open
- test_seed_duplicate_lane
- test_seed_loading_control_cv_ignored
- test_seed_loading_control_outside_range
- test_seed_missing_blot_reference
- test_seed_missing_lane
- test_seed_negative_background_used
- test_seed_overreach_causality
- test_seed_overreach_clinical
- test_seed_overreach_expression
- test_seed_overreach_mechanism
- test_seed_overreach_physical
- test_seed_overreach_protein_abundance
- test_seed_post_outcome_rules
- test_seed_saturated_band_used
- test_seed_technical_counted_biological
- test_seed_unfrozen_rules
- test_seed_unreliable_in_group_summary
- test_seed_unreliable_lane_included
- test_strict_json
- test_transient_ancestor_and_root_symlink_swaps
- test_unavailable_mixed_evidence_all_statuses
- test_unreliable_excluded_and_small_groups_unavailable
- test_welch_known_quantiles_and_degenerate_inputs
- test_wording_families_and_refusal_order

## Seeded findings exercised

- loading-control-outside-range: loading-control-range
- saturated-band-used: saturated-band
- negative-background-used: negative-after-background
- technical-counted-biological: technical-replicates
- missing-blot-reference: reference-lane
- loading-control-cv-ignored: loading-control-cv
- post-outcome-rules: post-outcome-rules
- unreliable-lane-included: target-range
- unreliable-in-group-summary: reported-number
- unfrozen-rules: rule-freeze
- duplicate-lane: duplicate-lane
- missing-lane: missing-lane
- overreach-protein-abundance: claim-overreach
- overreach-expression: claim-overreach
- overreach-mechanism: claim-overreach
- overreach-clinical: claim-overreach
- overreach-causality: claim-overreach
- overreach-physical: claim-overreach

## Files added

- src/codex_science/western_blot_densitometry_pack.py:1 — Pinned read-only validator, lane QC, biological-unit summaries, approximate Welch log-delta bounds and claim refusals.
- scripts/validate_western_blot_densitometry_pack.py:1 — One-bundle JSON CLI with labelled argument refusals and plain help.
- tests/test_workflow_wb_pack.py:1 — 42 focused cases, including 18 seeded negative cases and deterministic hostile-input probes.
- authored-skills/workflow-western-blot-densitometry/SKILL.md:1 — Decision contract, five ordered stages, stop rules, boundaries and review handoff.
- authored-skills/workflow-western-blot-densitometry/agents/openai.yaml:1 — Native selection metadata.
- authored-skills/workflow-western-blot-densitometry/references/index.json:1 — Progressive reference routes and evidence boundaries.
- authored-skills/workflow-western-blot-densitometry/references/stages.md:1 — Exact local record fields, controls, limits, arithmetic, refusals and command behavior.
- authored-skills/workflow-western-blot-densitometry/references/plan.json:1 — Existing manifest step shape with the five fixed stage IDs.
- authored-skills/workflow-western-blot-densitometry/quality.json:1 — L4 synthetic acceptance declaration, six local schemas, test file and seeded failures.
- benchmarks/workflow-western-blot-densitometry/tasks.json:1 — Frozen synthetic arithmetic and refusal questions with CPU-only budgets.
- examples/workflow-western-blot-densitometry/pack.json:1 — Primary accepting synthetic bundle and immutable identities.
- examples/workflow-western-blot-densitometry/rules.json:1 — Frozen synthetic lane, antibody, dilution, reference, replicate and uncertainty rules.
- examples/workflow-western-blot-densitometry/table.json:1 — Tiny synthetic two-blot intensity table, including a technical repeat and unreliable lane.
- examples/workflow-western-blot-densitometry/report.json:1 — Applied rules and expected bounded synthetic report.
- examples/workflow-western-blot-densitometry/expected.json:1 — Deterministic expected synthetic computation.
- examples/workflow-western-blot-densitometry/negative-cases.json:1 — 18 independently exercised synthetic defects with distinct findings.
- examples/workflow-western-blot-densitometry/README.md:1 — Hand arithmetic, invocation and limitations for the synthetic fixture.
- examples/workflow-western-blot-densitometry/VERIFICATION.md:1 — Checks, fail-before evidence, every test name, limitations and this addition manifest.
