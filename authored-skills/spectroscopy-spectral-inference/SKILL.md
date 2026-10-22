---
name: spectroscopy-spectral-inference
description: "Analyze experimental spectra with traceable preprocessing, calibration, peak or band inference, uncertainty, and alternative-model checks. Use for UV-Vis, fluorescence, IR, Raman, absorbance, emission, reflectance, and related one-dimensional spectral datasets or instrument exports."
license: MIT
---

# Spectroscopy and Spectral Inference

## Decision contract
Act as an analyzer. Define sample/state, matrix, concentration where relevant, modality, question, evidence cutoff, intended inference, and candidate claim IDs. Record axis and ordinate units, reference conditions, calibration, model-selection rule, uncertainty, and a falsifier before interpreting desired assignments. Distinguish observation, candidate assignment, chemical identity, quantitative result, and mechanistic interpretation as separate claim classes.

## Reference usage
Read the matching UV-Vis, fluorescence, IR, or Raman branch and shared reference-comparison rules in [references/modalities.md](references/modalities.md) before modality-specific processing, inference, or library comparison. The reference guides procedure and is not spectral evidence.

## Workflow
1. Define the intended claim and use; proceed only when sample/state, matrix, modality, evidence cutoff, claim IDs, uncertainty plan, and a falsifier are explicit, and record them before inspecting desired assignments.
2. Preserve raw spectra, metadata, and checksums; record path length/geometry, temperature, atmosphere, instrument/accessory, detector, acquisition mode, axis and units, resolution, scans, reference, blank, and calibration. State whether the ordinate is absorbance, transmittance, reflectance, counts, radiance, or normalized intensity; conversions are not interchangeable.
3. Use `$kdense-exploratory-data-analysis` only to inspect supported files, not infer identity. Check saturation, clipping, dark signal, cosmic spikes, etaloning, drift, range boundaries, and replicate dispersion; apply dark, blank, reference, response, and axis calibration in a declared order, preserving exclusions and reasons.
4. Choose baseline, smoothing, derivative, apodization, or deconvolution settings before viewing the desired answer; retain raw comparisons and quantify changes in position, width, area, and uncertainty. Record settings and why they are suitable to the modality.
5. Fit the smallest physically credible line-shape or mixture model; add components only when residual structure and independent constraints support them. Estimate peak/band positions, widths, areas, ratios, assignments, detection limits, and covariance with units; retain failed fits and alternative assignments.
6. Compare references only after checking source/version, phase, solvent or matrix, temperature, resolution, instrument response, and preprocessing compatibility. Treat similarity as candidate evidence, not identity proof; record library coverage, no-match and near-neighbor checks, and reference dependencies.
7. Test modality-specific controls: blank and standard; spike, dilution, and linearity for quantitative claims; independent acquisitions or held-out replicates for repeatability. Record the expected control response and whether each observed response meets the prespecified criterion.
8. Vary plausible baseline, window, smoothing, calibration, line shape, component count, and reference choices; call an assignment or quantity fragile if claim status or key result changes beyond prespecified uncertainty/tolerance, and record each comparison and its cause.
9. Verify residuals, parameter correlations, exclusions, and applicability; emit the schema below, preserve artifacts with `$science-provenance`, and run `$science-review` before material chemical identity or mechanism claims.

## Outputs
Provide one `spectral-evidence-reconciliation-v1` record per analysis with required fields: `claim_id`, `claim_class`, `claim_status` (`supported`, `contradicted`, `inconclusive`, `unavailable`), `sample_and_acquisition`, `raw_artifacts`, `processing_and_calibration`, `reference_dependencies`, `fitted_quantities_and_units`, `uncertainty_and_covariance`, `controls`, `sensitivity`, `alternative_interpretations`, `rejected_artifacts`, `applicability_limits`, `next_falsifiable_action`, and `review_and_provenance`. Include reference conditions, missing/excluded data and reasons, and artifact paths/hashes.

## Boundaries
Separate instrumental resolution from intrinsic width and random uncertainty from model ambiguity. Stop if the ordinate/axis meaning, reference, calibration, or raw-data lineage cannot be established. Do not silently repair clipping, drift, baseline, or outliers; report missing and excluded data with reasons. Library similarity cannot establish identity, and band assignment alone does not prove mechanism or composition. Retain non-unique fits and failed/null results as inconclusive. Use `$cx-complex-fourier-analysis` for transform/sampling questions and `$cx-experimental-uncertainty-propagation` for calibration/quantitative uncertainty.

## Source basis
Original workflow informed by NIST spectral-data practice and the official sources and overlap audit in `../../docs/ANALYTICAL_SOURCES.md`.
