---
name: chromatography-quantification
description: "Quantify analytes from chromatographic data with validated integration, calibration, quality controls, and uncertainty. Use for HPLC, UHPLC, GC, LC-MS, GC-MS, UV or fluorescence detection, targeted assays, purity estimates, retention data, and batch acceptance."
license: MIT
---

# Chromatographic quantification evidence

## Decision contract
Act as an analyzer. Define analyte, matrix, sample population, measurand (concentration, amount, response ratio, area percent, recovery, or purity), method scope, evidence cutoff, and batch decision. State units, calibration model/range, QC acceptance rules, uncertainty rule, and a falsifier such as failed QC or unresolved coelution before reviewing unknown results. Area percent is not automatically mass or mole purity.

## Reference usage
Read [chromatographic-quantification-evidence.md](references/chromatographic-quantification-evidence.md) before the workflow steps Assess controls (assess-controls), Lock calibration (lock-calibration), Validate performance (validate-performance), Challenge integration (challenge-integration), and Verify range and batch (verify-range-and-batch). These IDs name the numbered actions below; use the reference criteria for calibration, limits, matrix performance, system suitability, carryover, and batch decisions.

## Workflow
1. **Check gates.** If raw data, units, calibration/QC provenance or required method scope is missing, stop and ask for the missing information before quantitative interpretation; if it cannot be supplied, classify the affected claim as unavailable/inconclusive and record the unmet gate.
2. **Freeze method.** Preserve raw checksums and record extraction, internal standard, instrument/detector, column, mobile phase/carrier gas, gradient/program, flow, temperature, injection, acquisition rate, sequence order, wash, integration method, calibration range, QC levels, dilution and stability.
3. **Assess controls.** Inspect blanks, zero samples, standards, pooled QC, retention stability, peak shape/resolution, saturation, baseline, carryover, contamination, integration bounds, coelution and selectivity. Require authentic standard or orthogonal evidence where retention alone is insufficient. For LC-MS, use `$kdense-pyopenms` for trace/feature processing and `$cx-mass-spectrometry-identification` for identity claims; record control outcomes.
4. **Lock calibration.** Prespecify response, weighting, regression, range and acceptance; inspect residuals and back-calculated standards, not correlation alone. Record equation, diagnostics, exclusions and reasons.
5. **Validate performance.** Assess recovery, matrix effect, precision, accuracy, selectivity, carryover, dilution integrity and stability as applicable. Define LOD/LOQ by a method tied to false positives, precision and use, not signal-to-noise alone. Propagate calibration, preparation, volume, purity, recovery, and replicate uncertainty with `$cx-experimental-uncertainty-propagation`.
6. **Challenge integration.** Reintegrate blinded representative peaks or use locked integration; document each manual override. Check dilution parallelism and reinjection/re-extraction without counting technical repeats as independent samples.
7. **Verify range and batch.** Probe blank/carryover near lower limit and saturation near upper limit; keep calibrators/QCs independent of unknowns and distinguish calibration, validation and final batches. If QC fails, coelution persists, or samples extrapolate beyond validated range, downgrade/block the unqualified result.
8. **Report and hand off.** Retain failed runs, excluded points, reinjections and out-of-range samples; report uncertainty, units, limitations and smallest falsifiable next action. Store chromatograms, method provenance and hashes with `$science-provenance`; run `$science-review` before material quantitative or batch-acceptance claims.

## Outputs
`chromatographic-quantification-evidence-v1` required fields: sample_and_sequence_ids; method_and_raw_data_artifacts (method_record; method_hash; raw_data_paths; raw_data_hashes); chromatograms; peak_integration_bounds; integration_audit; calibration_model_and_diagnostics; qc_results; validated_range; concentration_and_units; uncertainty; identity_evidence; exclusions_and_reasons; dependency_groups; claim_register with statuses (`supported`, `contradicted`, `inconclusive`, `unavailable`); applicability_limits; next_action; provenance_receipt; review_receipt.

## Boundaries
Stop interpretation when raw data, calibration/QC provenance, or essential units are absent; report unavailable or inconclusive rather than imputing. Coelution, saturation, carryover, failed QC, or extrapolation beyond the validated range blocks an unqualified quantitative claim. Retention alone does not prove identity; detector response and area percent do not establish mass purity. Do not silently adjust baselines, boundaries, exclusions, or acceptance criteria after seeing the desired result. Report assay applicability limits and distinguish process completion from validation of the measurand.

## Source basis
Original workflow informed by current bioanalytical method-validation guidance and OpenMS chromatogram practice recorded in `../../docs/ANALYTICAL_SOURCES.md`.
