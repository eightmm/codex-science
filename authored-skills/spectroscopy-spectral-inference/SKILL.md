---
name: spectroscopy-spectral-inference
description: "Analyze experimental spectra with traceable preprocessing, calibration, peak or band inference, uncertainty, and alternative-model checks. Use for UV-Vis, fluorescence, IR, Raman, absorbance, emission, reflectance, and related one-dimensional spectral datasets or instrument exports."
license: MIT
---

# Spectroscopy and Spectral Inference

## Decision contract
Act as an analyzer. Define sample/state, matrix, concentration, modality, question, evidence cutoff, intended inference, and candidate claim IDs. Record axis/ordinate units, reference conditions, calibration, model-selection rule, uncertainty, and a falsifier before interpreting desired assignments. Use the matching branch in [references/modalities.md](references/modalities.md).

## Workflow
1. Preserve raw intensities, metadata, and checksum. Record path length/geometry, temperature, atmosphere, instrument/accessory, detector, acquisition mode, axis and units, resolution, scans, reference, blank, calibration. State whether intensity is absorbance, transmittance, reflectance, counts, radiance, or normalized intensity; conversions are not interchangeable.
2. Use `$kdense-exploratory-data-analysis` only to inspect supported files, not infer identity. Inspect saturation, clipping, dark signal, cosmic spikes, etaloning, drift, range boundaries, and replicate dispersion. Apply dark, blank, reference, response, and axis calibration in a declared order.
3. Choose baseline, smoothing, derivative, apodization, or deconvolution settings before seeing the desired answer. Retain raw comparison and quantify processing effects on position, width, area, and uncertainty. Fit the smallest physically credible line-shape/mixture model; do not add components solely to improve residuals. Use `$cx-complex-fourier-analysis` for transform/sampling questions and `$cx-experimental-uncertainty-propagation` for calibration/quantitative uncertainty.
4. Verify by estimating peak/band locations, widths, areas, ratios, assignments, detection limits, and covariance with units. Compare references only after matching phase, solvent/matrix, temperature, resolution, instrument response, and preprocessing. Treat similarity as candidate evidence, not identity proof. Refit plausible baseline, window, line shape, and component counts; inspect residuals/parameter correlations and use held-out replicates when available. Check blank, standard, spike, dilution, linearity, and reproduce features across independent acquisitions.

## Outputs
Provide normalized sample/acquisition inputs, raw-data lineage, processing/calibration history, fitted quantities and units with uncertainty, reference conditions, alternative interpretations, rejected artifacts, and claim IDs/status (`supported`, `contradicted`, `inconclusive`, `unavailable`). State dependencies, applicability and limitations, smallest falsifiable next action, and artifact paths/hashes via `$science-provenance`. Run `$science-review` before material chemical identity or mechanism claims.

## Boundaries
Separate instrumental resolution from intrinsic width and random uncertainty from model ambiguity. Stop if the ordinate/axis meaning, reference, calibration, or raw-data lineage cannot be established. Do not silently repair clipping, drift, baseline, or outliers; report missing and excluded data with reasons. Library similarity cannot establish identity, and band assignment alone does not prove mechanism or composition. Retain non-unique fits and failed/null results as inconclusive.

## Source basis
Original workflow informed by NIST spectral-data practice and the official sources and overlap audit in `../../docs/ANALYTICAL_SOURCES.md`.
