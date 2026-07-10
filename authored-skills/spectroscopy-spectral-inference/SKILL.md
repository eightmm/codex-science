---
name: spectroscopy-spectral-inference
description: "Analyze experimental spectra with traceable preprocessing, calibration, peak or band inference, uncertainty, and alternative-model checks. Use for UV-Vis, fluorescence, IR, Raman, absorbance, emission, reflectance, and related one-dimensional spectral datasets or instrument exports."
license: MIT
---

# Spectroscopy and Spectral Inference

## Preserve the measurement

Record sample identity and state, matrix, concentration, path length or geometry, temperature, atmosphere,
instrument and accessory, detector, acquisition mode, axis quantity and units, resolution, scans, reference,
blank, calibration, and raw-file checksum. Preserve raw intensities and metadata. State whether the ordinate is
absorbance, transmittance, reflectance, counts, radiance, or normalized intensity; conversions are not interchangeable.

Read [references/modalities.md](references/modalities.md) for the applicable UV-Vis, fluorescence, IR, or Raman
branch. Use `$kdense-exploratory-data-analysis` only to inspect supported files, not to infer chemical identity.

## Process without manufacturing evidence

1. Inspect saturation, clipping, dark signal, cosmic spikes, etaloning, drift, range boundaries, and replicate dispersion.
2. Apply dark, blank, reference, response, and axis calibration corrections in a declared order.
3. Choose baseline, smoothing, derivative, apodization, or deconvolution settings before examining the desired answer.
4. Retain an unprocessed comparison. Show how processing changes peak position, width, area, and uncertainty.
5. Fit the smallest physically credible line-shape or mixture model; do not add components solely to improve residuals.

Use `$cx-complex-fourier-analysis` for transform or sampling questions. Use
`$cx-experimental-uncertainty-propagation` for calibration and quantitative uncertainty.

## Infer and compare

Estimate peak or band locations, widths, areas, ratios, assignments, detection limits, and covariance with units.
Compare reference spectra only after matching phase, solvent or matrix, temperature, resolution, instrument response,
and preprocessing. Treat a library similarity as candidate evidence, not identity proof.

## Verify

- Refit plausible baseline, window, line shape, and component counts; report assignment stability.
- Inspect structured residuals and parameter correlations; use held-out replicates for model selection when available.
- Check blank, standard, spike, dilution, and concentration-linearity behavior appropriate to the modality.
- Compare raw and processed results and reproduce key features across independent acquisitions.
- Separate instrumental resolution from intrinsic width and random uncertainty from model ambiguity.

## Deliver

Report raw-data provenance, processing history, calibration, fitted quantities with uncertainty, reference conditions,
alternative explanations, rejected artifacts, and the strongest conclusion supported by the spectra.

## Source basis

Original workflow informed by NIST spectral-data practice and the official sources and overlap audit in
`../../docs/ANALYTICAL_SOURCES.md`.
