---
name: chromatography-quantification
description: "Quantify analytes from chromatographic data with validated integration, calibration, quality controls, and uncertainty. Use for HPLC, UHPLC, GC, LC-MS, GC-MS, UV or fluorescence detection, targeted assays, purity estimates, retention data, and batch acceptance."
license: MIT
---

# Chromatography Quantification

## Define the assay

Record analyte and matrix, extraction, internal standard, instrument and detector, column, mobile phase or carrier gas,
gradient or program, flow, temperature, injection, acquisition rate, sequence order, wash, integration method, calibration
range, QC levels, dilution, stability, and raw-file checksum. State the measurand: concentration, amount, response ratio,
area percent, recovery, or purity. Area percent is not automatically mass or mole purity.

## Inspect system and peaks

Check blanks, zero samples, standards, pooled QC, retention stability, peak shape, resolution, signal saturation, baseline,
carryover, contamination, integration boundaries, coelution, and detector selectivity. Require an authentic standard or
orthogonal evidence for identity when retention alone is insufficient. For LC-MS, use `$kdense-pyopenms` for trace and
feature processing and `$cx-mass-spectrometry-identification` for identity claims.

## Calibrate and quantify

1. Define response, weighting, regression model, range, and acceptance rules before fitting.
2. Inspect residuals and back-calculated standards; do not select weighting by correlation coefficient alone.
3. Evaluate recovery, matrix effect, precision, accuracy, selectivity, carryover, dilution integrity, and stability as applicable.
4. Define LOD and LOQ from a method tied to false positives, precision, and intended use; do not use signal-to-noise alone blindly.
5. Propagate calibration, preparation, volume, purity, recovery, and replicate uncertainty with
   `$cx-experimental-uncertainty-propagation`.

## Verify

- Reintegrate blinded representative peaks or use a locked integration method; document every manual override.
- Check dilution parallelism and reinjection or re-extraction evidence without treating technical repeats as independent samples.
- Confirm calibrator and QC independence from unknowns and distinguish calibration, validation, and final batches.
- Test blank and carryover effects near the lower limit and saturation near the upper limit.
- Report failed runs, excluded points, reinjections, and out-of-range samples rather than silently replacing them.

## Deliver

Provide sequence and method provenance, chromatograms, integration audit, calibration equation and diagnostics, QC table,
accepted range, concentrations with uncertainty, exclusions, identity evidence, and assay applicability limits.

## Source basis

Original workflow informed by current bioanalytical method-validation guidance and OpenMS chromatogram practice recorded
in `../../docs/ANALYTICAL_SOURCES.md`.
