# Spectroscopy modality branches

Load only the branch matching the experiment. The common workflow and reporting contract remain in `../SKILL.md`.

## UV-Vis absorption

- Record wavelength accuracy, spectral bandwidth, path length, solvent and blank, concentration, temperature, and cuvette.
- Confirm whether data are transmittance or absorbance before applying Beer-Lambert relations.
- Check stray light, saturation, scattering, aggregation, inner-filter behavior, and baseline mismatch.
- Fit concentration dependence only over a validated linear or mechanistic range; report molar absorptivity with units.
- Treat broad-band decomposition as model-dependent unless standards or independent constraints identify components.

## Fluorescence and emission

- Record excitation and emission bandwidths, geometry, detector correction, integration time, polarization, and dark counts.
- Correct excitation leakage, Raman scatter, detector response, inner-filter effects, reabsorption, and photobleaching as applicable.
- State whether spectra are photon-, energy-, area-, or peak-normalized; normalization removes absolute-yield information.
- For lifetimes, retain the instrument-response function, fitting window, background, convolution model, and residuals.
- Distinguish static and dynamic quenching with concentration, lifetime, temperature, or complementary evidence.

## Infrared absorption

- Record transmission, ATR, DRIFTS, or reflection geometry; crystal, angle, pressure, path length, atmosphere, and resolution.
- Apply atmospheric, ATR, baseline, and thickness corrections only with recorded parameters.
- Check water and carbon-dioxide bands, saturation, fringes, scattering, contact variation, and phase or matrix differences.
- Compare libraries with matching phase and conditions. Use functional-group assignments as constraints, not full identity proof.
- For quantitative IR, validate effective path length, band integration, concentration range, and overlap model.

## Raman scattering

- Record laser wavelength and power at the sample, objective, grating, confocal geometry, acquisition, polarization, and calibration.
- Check fluorescence background, cosmic rays, sample heating, burning, focus drift, substrate peaks, and notch-filter boundaries.
- Calibrate Raman shift with a standard and separate intensity response from peak-position calibration.
- Compare Stokes and anti-Stokes behavior only after detector response and temperature assumptions are explicit.
- Treat baseline subtraction and overlapping-band fits as model choices; show raw data and sensitivity to alternatives.

## Shared reference comparisons

- Preserve reference source, accession or identifier, snapshot date, phase, matrix, instrument, resolution, and license.
- Resample only after retaining the original grids; document interpolation and common overlap range.
- Avoid tuning preprocessing and similarity thresholds on the same references used to report recognition accuracy.
- Include no-match and near-neighbor controls and report library coverage before interpreting a top hit.
