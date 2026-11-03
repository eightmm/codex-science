# Dose-response pack verification evidence

All checked-in inputs and numerical results are synthetic fixtures. This report records local software checks, not independent review, real assay qualification, physical validity or clinical evidence.

## Changes and scope

- Added the authored pack (contract, ordered plan, stage/schema references, progressive index, agent metadata, honest L4 declaration), synthetic examples, frozen benchmark, standard-library validator/fitter, thin CLI and focused tests.
- Existing files were not edited. The final brief prohibits registry/catalog/policy edits; owner integration must handle catalog/native-skill-policy.json, scripts/audit_skill_references.py, scripts/check.sh and generated bookkeeping as appropriate.
- No dependencies, versions, toolchain, bootstrap, global schemas, manifest/receipt fields, MCP output, frozen graders or unrelated work changed. No commits or pushes.
- git log -S dose-response-pack-v1 on source/scripts and the writer-path history returned no earlier writer; no stored record class changes validation or review behavior.

## Checks actually run

| Check | Observed result |
| --- | --- |
| PYTHONPATH=src:tests python3 -m unittest test_workflow_dose_response_pack | 49 tests pass; last complete run 2.811 seconds (all commands bounded with timeout 60) |
| Seeded refusal mutations | Each of 31 seeded tests fails when its named refusal is disabled in the actual source; original source restored, suite passes |
| Complete non-test patch reversal | Saved git diff, applied in reverse, selected all 49 tests once: 49 import errors because the new module does not exist at HEAD; patch reapplied in finally |
| test_catalog and test_skill_maturity | 60 tests pass in 4.782 seconds; existing SyntaxWarning in test_skill_maturity.py, outside scope |
| Existing native-skill quality checks excluding known count-document assertion | 12 tests pass |
| Named-skill ranking with freshly audited authored rows merged with stored vendor rows | Existing representative repository prompts test passes; new skill active with no catalog reasons |
| audit_skill_references.py --require-clean | 145 skills, 209 references, zero findings |
| audit_native_skill_maturity.py --require-clean | Passed; new pack computed/declared L4, no reasons; aggregate 145 skills, L3 120, L4 25 |
| py_compile | New source, CLI and test module pass |
| Consumer/documentation and CLI search | Public functions, schema names, file names and help reviewed across tests, scripts, docs and root READMEs; consumers are new pack files only |

## Failed or skipped shared checks

- Existing test_status_documents_match_native_skill_maturity_audit fails its two subtests: docs/IMPLEMENTATION_STATUS.md and docs/ROADMAP.md still state 144 skills/L4 24, versus new 145/L4 25. Those documents are outside the worker scope and were not changed.
- Full scripts/audit_skills.py regeneration fails because vendor/scientific-agent-skills/skills is absent. No vendor download or installation was authorized or attempted. Routing was additionally checked with regenerated authored entries and the stored vendor entries, without editing catalog files.
- The harness-owned tests.workflow_dose_response command was not run, as instructed; that module is absent from this clone. The new focused test module was run directly. Shared check.sh fast/public and real/live/remote/GPU checks were not run; shared registration and missing vendor sources remain owner work.

## Each focused test

The following 18 tests pass; the remaining 31 are enumerated with their specific refusal below.

- `test_artifact_paths_and_special_files_never_hang`
- `test_control_threshold_equality_zero_and_malformed`
- `test_declared_integer_bounds_empty_zero_equal_and_malformed`
- `test_disjoint_intervals_allow_bounded_ordering`
- `test_failed_controls_preserved_as_unavailable`
- `test_fixture_labels_are_boolean_consistent_and_not_authentication`
- `test_hash_binding_final_replacement_and_single_parse`
- `test_ic50_decreasing_curve_and_optimizer_failure`
- `test_insufficient_converged_bootstrap_draws_refuse_intervals`
- `test_json_duplicates_depth_numbers_types_and_cli_refusals`
- `test_nonfinite_plate_and_zero_biological_variance`
- `test_numerical_empty_zero_nonfinite_and_malformed_inputs`
- `test_own_evidence_same_hash_copy_is_not_independent`
- `test_recorded_units_exploratory_deviation_and_equal_minimums`
- `test_seeded_failures_have_frozen_benchmark_and_quality_coverage`
- `test_size_limit_zero_equal_oversized_and_growing`
- `test_swapped_fifo_after_lstat_is_refused`
- `test_synthetic_recovery_intervals_cli_and_read_only`

| Synthetic defect / test suffix | Expected refusal | API and CLI | Disabled check |
| --- | --- | --- | --- |
| `extrapolated-potency` / `test_refuse_extrapolated_potency` | `potency-extrapolation` | Pass; no traceback/input writes | Test fails |
| `unreached-plateau` / `test_refuse_unreached_plateau` | `plateau-not-reached` | Pass; no traceback/input writes | Test fails |
| `too-few-concentrations` / `test_refuse_too_few_concentrations` | `insufficient-concentrations` | Pass; no traceback/input writes | Test fails |
| `too-few-biological-replicates` / `test_refuse_too_few_biological_replicates` | `insufficient-replicates` | Pass; no traceback/input writes | Test fails |
| `too-few-technical-replicates` / `test_refuse_too_few_technical_replicates` | `insufficient-replicates` | Pass; no traceback/input writes | Test fails |
| `technical-as-biological` / `test_refuse_technical_as_biological` | `pseudoreplication` | Pass; no traceback/input writes | Test fails |
| `missing-vehicle` / `test_refuse_missing_vehicle` | `missing-control` | Pass; no traceback/input writes | Test fails |
| `missing-positive` / `test_refuse_missing_positive` | `missing-control` | Pass; no traceback/input writes | Test fails |
| `failed-controls` / `test_refuse_failed_controls` | `controls-failed` | Pass; no traceback/input writes | Test fails |
| `unrecorded-unit-conversion` / `test_refuse_unrecorded_unit_conversion` | `unit-mismatch` | Pass; no traceback/input writes | Test fails |
| `nonconverged-fit` / `test_refuse_nonconverged_fit` | `unreportable-fit` | Pass; no traceback/input writes | Test fails |
| `boundary-fit` / `test_refuse_boundary_fit` | `unreportable-fit` | Pass; no traceback/input writes | Test fails |
| `changed-model` / `test_refuse_changed_model` | `unlabelled-deviation` | Pass; no traceback/input writes | Test fails |
| `changed-constraints` / `test_refuse_changed_constraints` | `unlabelled-deviation` | Pass; no traceback/input writes | Test fails |
| `changed-outlier-rule` / `test_refuse_changed_outlier_rule` | `unlabelled-deviation` | Pass; no traceback/input writes | Test fails |
| `unreasoned-exclusion` / `test_refuse_unreasoned_exclusion` | `outlier-rule` | Pass; no traceback/input writes | Test fails |
| `point-ranking` / `test_refuse_point_ranking` | `point-ranking` | Pass; no traceback/input writes | Test fails |
| `overlapping-ranking` / `test_refuse_overlapping_ranking` | `overlapping-intervals` | Pass; no traceback/input writes | Test fails |
| `clinical-claim` / `test_refuse_clinical_claim` | `claim-boundary` | Pass; no traceback/input writes | Test fails |
| `safety-claim` / `test_refuse_safety_claim` | `claim-boundary` | Pass; no traceback/input writes | Test fails |
| `dose-claim` / `test_refuse_dose_claim` | `claim-boundary` | Pass; no traceback/input writes | Test fails |
| `causality-claim` / `test_refuse_causality_claim` | `claim-boundary` | Pass; no traceback/input writes | Test fails |
| `mechanism-claim` / `test_refuse_mechanism_claim` | `claim-boundary` | Pass; no traceback/input writes | Test fails |
| `computed-support` / `test_refuse_computed_support` | `computed-claim` | Pass; no traceback/input writes | Test fails |
| `review-as-truth` / `test_refuse_review_as_truth` | `computed-claim` | Pass; no traceback/input writes | Test fails |
| `computed-result-disguise` / `test_refuse_computed_result_disguise` | `computed-claim` | Pass; no traceback/input writes | Test fails |
| `own-independent` / `test_refuse_own_independent` | `own-evidence` | Pass; no traceback/input writes | Test fails |
| `own-external` / `test_refuse_own_external` | `own-evidence` | Pass; no traceback/input writes | Test fails |
| `own-preregistered` / `test_refuse_own_preregistered` | `own-evidence` | Pass; no traceback/input writes | Test fails |
| `post-outcome-freeze` / `test_refuse_post_outcome_freeze` | `outcome-dependent-freeze` | Pass; no traceback/input writes | Test fails |
| `self-review` / `test_refuse_self_review` | `self-review` | Pass; no traceback/input writes | Test fails |

Baseline import errors alone do not prove refusal sensitivity. The source-mutation checks supply that evidence for each seeded defect. Non-seeded transport, numerical and metadata tests use their closest public-path checks, including real FIFOs, symlinks, a descriptor-open race, an exact 64 MiB input, growing/replaced input, malformed JSON, IC50, optimizer failure and biological-bootstrap failure.

## Pack-local schemas

- `dose-response-pack-v1`
- `dose-response-assay-v1`
- `dose-response-plate-v1`
- `dose-response-qc-v1`
- `dose-response-fit-v1`
- `dose-response-uncertainty-v1`
- `dose-response-claims-v1`
- `dose-response-handoff-v1`
- `dose-response-validation-v1`

## Writes, concurrency and interruption

The implementation writes no file, ref, record, checkpoint or receipt. Every path added by this change is a checked-in source, procedure, synthetic fixture, expected artifact or benchmark. A second validator call independently reads the same immutable bundle. A kill leaves only partial stdout/stderr; no two-write state exists. Replaced inputs are refused by final hash and descriptor-identity checks. Fixture artifacts are not runtime output or review receipts.

Temporary generator, mutation, baseline, inventory and audit files are removed after use; pre-existing room-relay files remain untouched. The owning harness captures the new worktree files as the patch artifact.

## Remaining uncertainty

The bounded local monotone 4PL and small percentile bootstrap have synthetic acceptance only. Neither global optimization, residual adequacy, statistical coverage, real pharmacology nor clinical translation is established. Labels and timestamps cannot authenticate experimental independence or preregistration; the English lexical claim filter cannot establish semantic safety. Coordinator-owned independent review and shared batch integration remain outstanding.

## Proposed CHANGELOG bullet

- Add the dose-response curve pack with frozen assay/control checks, deterministic stdlib 4PL fitting and biological-bootstrap potency intervals, hash-bound synthetic acceptance fixtures, and bounded in-vitro claim handoff; no existing stored record class changes validation.
