# Spectroscopy modality branches

Load only the branch matching the experiment. The shared workflow and reporting contract remain in `../SKILL.md`. These procedures guide analysis; library entries and this reference are not evidence that an unknown sample has a particular identity.

## Claim semantics

- **Observed feature:** a repeatable peak, band, shoulder, edge, or decay component in a named region, after checking axis calibration, resolution, acquisition artifacts, and raw data. Report location, width/intensity measure, uncertainty, and exclusions.
- **Candidate assignment:** a feature is compatible with a functional group, transition, or library entry under stated phase/matrix/solvent and instrument conditions. Report competing assignments and missing expected features; similarity alone does not establish identity.
- **Chemical identity or composition:** requires a validated reference or standard, adequate specificity against near neighbors, compatible conditions, and appropriate orthogonal or spike/recovery evidence. Keep an unresolved candidate as `inconclusive`.
- **Quantitative result:** requires a validated calibration/range and a response model suitable for matrix, path length, dilution, and detector behavior. Report units, calibration uncertainty, range, residuals, and dilution/recovery checks.
- **Mechanistic interpretation:** remains an inference beyond a band or spectral match; require discriminating perturbation or orthogonal evidence and state alternatives. A signal or assignment alone does not prove mechanism.

Use statuses consistently: `supported` means prespecified evidence and controls support the bounded claim; `contradicted` means a discriminating observation conflicts with it; `inconclusive` means ambiguous, underpowered, or model-dependent evidence; `unavailable` means required information or evidence is missing.

## Shared source dependencies and independence

Pin raw-file checksum, sample/preparation and aliquot identity, instrument/accessory/detector, acquisition settings, axis and ordinate units, calibration standards, software/version/parameters, processing history, and every library/source identifier with version or snapshot and retrieval date. Preserve vendor raw data when available and record conversion or resampling. Library records derived from the same source or reference specimen are not independent confirmations. Replicate scans from one aliquot test acquisition repeatability, not independent sample preparation. Record shared batches, standards, instruments, libraries, preprocessing and model assumptions so apparent agreement is not counted twice.

## Uncertainty, controls, and sensitivity

Separate repeatability and counting noise from axis calibration, instrumental resolution, baseline/model choice, reference variability, and matrix or sample-state effects. Propagate standard/calibration uncertainty into positions, widths, areas, ratios, and concentrations; include covariance for overlapping bands or fitted components. For all modes, inspect blanks, standards, near-neighbor/no-match controls, replicate acquisition, and raw-versus-processed traces. Quantitative claims additionally need spike/recovery, dilution or linearity controls appropriate to the method.

Vary plausible baseline family/order, smoothing width, derivative or apodization settings, fit window, line shape, component count, calibration, reference subset, and similarity threshold. Prespecify meaningful tolerances. Call a result fragile when claim status or assignment changes, or a quantity shifts beyond propagated uncertainty or declared practical tolerance; report alternatives instead of averaging incompatible models.

## UV-Vis absorption

- Record wavelength accuracy, spectral bandwidth, path length, solvent and blank, concentration, temperature, and cuvette; note scattering or turbid samples.
- Confirm transmittance versus absorbance before applying Beer-Lambert relations; retain the source ordinate and calculation.
- Check stray light, saturation, scattering, aggregation, inner-filter behavior, and baseline mismatch. Do not infer concentration from a clipped or matrix-mismatched spectrum.
- Fit concentration dependence only over a validated linear or mechanistic range; report molar absorptivity with units, calibration residuals, range, and uncertainty.
- Treat broad-band decomposition as model-dependent unless standards or independent constraints identify components.

## Fluorescence and emission

- Record excitation and emission bandwidths, geometry, detector correction, integration time, polarization, and dark counts.
- Correct excitation leakage, Raman scatter, detector response, inner-filter effects, reabsorption, and photobleaching only as applicable; preserve uncorrected spectra and correction factors.
- State whether spectra are photon-, energy-, area-, or peak-normalized; normalization removes absolute-yield information.
- For lifetimes, retain the instrument-response function, fitting window, background, convolution model, residuals, and parameter covariance.
- Distinguish static and dynamic quenching with concentration, lifetime, temperature, or complementary evidence; fluorescence intensity change alone is ambiguous.

## Infrared absorption

- Record transmission, ATR, DRIFTS, or reflection geometry; crystal, angle, pressure, path length, atmosphere, and resolution.
- Apply atmospheric, ATR, baseline, and thickness corrections only with recorded parameters; retain original and corrected spectra.
- Check water and carbon-dioxide bands, saturation, fringes, scattering, contact variation, and phase or matrix differences.
- Compare libraries with matching phase and conditions. Use functional-group assignments as constraints, not full identity proof.
- For quantitative IR, validate effective path length, band integration, concentration range, overlap model, and standard/recovery performance.

## Raman scattering

- Record laser wavelength and power at the sample, objective, grating, confocal geometry, acquisition, polarization, and calibration.
- Check fluorescence background, cosmic rays, sample heating, burning, focus drift, substrate peaks, and notch-filter boundaries; compare repeat acquisitions at lower power when damage is plausible.
- Calibrate Raman shift with a standard and separate intensity response from peak-position calibration.
- Compare Stokes and anti-Stokes behavior only after detector response and temperature assumptions are explicit.
- Treat baseline subtraction and overlapping-band fits as model choices; show raw data and sensitivity to alternatives.

## Shared reference comparisons

- Preserve reference source, accession or identifier, snapshot date, phase, matrix, instrument, resolution, preprocessing, and license.
- Resample only after retaining original grids; document interpolation, common overlap range, axis conversion, and intensity normalization.
- Avoid tuning preprocessing and similarity thresholds on the same references used to report recognition accuracy.
- Include no-match and near-neighbor controls and report library coverage before interpreting a top hit.
- NIST Chemistry WebBook SRD 69 is an evaluated/compiled reference resource; retain its record and conditions. A reference spectrum is a candidate comparator, not an identity certificate.

## Applicability limits and failure detection

This workflow assumes traceable spectra and known axis/ordinate semantics. It may fail with unknown mixtures, unmatched phases or matrices, insufficient resolution, detector saturation, strong scattering/fluorescence, uncorrected response, sample photochemistry/heating, incomplete library coverage, or non-identifiable overlapping bands. Extrapolation beyond validated concentration, temperature, phase, geometry, or instrument range is not supported.

| Failure mode | Detection and response |
|---|---|
| Axis or ordinate mislabeled | Metadata, standards, or raw export disagree; stop conversion and affected quantitative/assignment claim. |
| Baseline removes a broad real feature | Raw-versus-corrected trace or alternative baseline changes assignment/area; retain alternatives and downgrade. |
| Saturation or clipping hides peak height | Flat-topped/ceiling values or failed dilution; do not report intensity-based quantity. |
| Fluorescence or Raman damage mimics bands | Excitation dependence, time drift, laser-power dependence, or damaged spot; preserve data and reacquire only under authorized conditions. |
| Library top hit is a near neighbor | Near-neighbor/no-match control or missing expected bands contradicts the hit; report candidate or inconclusive status. |
| Overfit decomposition creates components | Components are unstable to baseline/window/model or strongly correlated; report combined envelope and ambiguity. |
| Normalization hides absolute response | Original total scale is absent or normalized data presented as absolute; retract yield/intensity claim and restore raw scale if available. |

## Sources and scope

- IUPAC, *Compendium of Analytical Nomenclature* (3rd edition, 1997): analytical terminology and nomenclature; it does not set sample-specific acceptance thresholds.
- Taylor and Kuyatt, NIST Technical Note 1297 (1994), *Guidelines for Evaluating and Expressing the Uncertainty of NIST Measurement Results*: uncertainty components and reporting; it does not validate a spectral assignment.
- NIST Chemistry WebBook, SRD 69 (reference resource): spectral reference records; evaluate the record's conditions and provenance for each comparison.

Modality-specific controls, sensitivity tests, and claim criteria here are a procedural synthesis. Do not infer validation from a citation or invent universal library-match cutoffs.
