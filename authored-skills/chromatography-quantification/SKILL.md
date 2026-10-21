---
name: chromatography-quantification
description: "Quantify analytes from chromatographic data with validated integration, calibration, quality controls, and uncertainty. Use for HPLC, UHPLC, GC, LC-MS, GC-MS, UV or fluorescence detection, targeted assays, purity estimates, retention data, and batch acceptance."
license: MIT
---

# Chromatography Quantification

## Decision contract
Act as an analyzer. Define analyte, matrix, sample population, measurand (concentration, amount, response ratio, area percent, recovery, or purity), method scope, evidence cutoff, and batch decision. State units, calibration model/range, QC acceptance rules, uncertainty rule, and a falsifier such as failed QC or unresolved coelution before reviewing unknown results. Area percent is not automatically mass or mole purity.

## Workflow
1. Preserve raw-file checksums and record extraction, internal standard, instrument/detector, column, mobile phase or carrier gas, gradient/program, flow, temperature, injection, acquisition rate, sequence, wash, integration method, dilution, and stability.
2. Inspect blanks, zero samples, standards, pooled QC, retention stability, peak shape/resolution, saturation, baseline, carryover, contamination, integration bounds, coelution, and selectivity. Require an authentic standard or orthogonal evidence for identity when retention alone is insufficient. For LC-MS, use `$kdense-pyopenms` for trace/feature processing and `$cx-mass-spectrometry-identification` for identity claims.
3. Prespecify response, weighting, regression, range, and acceptance. Inspect residuals and back-calculated standards; do not choose weighting from correlation alone. Assess recovery, matrix effect, precision, accuracy, selectivity, carryover, dilution integrity, and stability as applicable. Define LOD/LOQ with a method linked to false positives, precision, and intended use; do not rely blindly on signal-to-noise. Propagate calibration, preparation, volume, purity, recovery, and replicate uncertainty with `$cx-experimental-uncertainty-propagation`.
4. Verify by reintegrating blinded representative peaks or using locked integration; document every manual override. Check dilution parallelism and reinjection/re-extraction without counting technical repeats as independent samples. Keep calibrators/QCs independent of unknowns and distinguish calibration, validation, and final batches. Probe blank/carryover near the lower limit and saturation near the upper limit. Retain failed runs, excluded points, reinjections, and out-of-range samples; never silently replace a result.

## Outputs
Return normalized assay inputs and a machine-readable evidence table with sample/sequence IDs, peak and integration bounds, calibration equation and diagnostics, QC results, accepted range, concentration with units and uncertainty, identity evidence, and claim IDs/status (`supported`, `contradicted`, `inconclusive`, `unavailable`). Record exclusions and reasons, dependencies, limitations, smallest falsifiable next action, chromatograms, method provenance, raw-data paths and hashes via `$science-provenance`. Run `$science-review` before material quantitative or batch-acceptance claims.

## Boundaries
Stop interpretation when raw data, calibration/QC provenance, or essential units are absent; report unavailable or inconclusive rather than imputing. Coelution, saturation, carryover, failed QC, or extrapolation beyond the validated range blocks an unqualified quantitative claim. Retention alone does not prove identity; detector response and area percent do not establish mass purity. Do not silently adjust baselines, boundaries, exclusions, or acceptance criteria after seeing the desired result. Report assay applicability limits and distinguish process completion from validation of the measurand.

## Source basis
Original workflow informed by current bioanalytical method-validation guidance and OpenMS chromatogram practice recorded in `../../docs/ANALYTICAL_SOURCES.md`.
