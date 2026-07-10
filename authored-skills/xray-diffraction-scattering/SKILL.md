---
name: xray-diffraction-scattering
description: "Analyze and verify X-ray diffraction and scattering data. Use for powder XRD, phase identification, indexing, lattice parameters, Rietveld refinement, crystallite size or strain, texture, amorphous content, SAXS, WAXS, pair distributions, and comparison with calculated patterns."
license: MIT
---

# X-ray Diffraction and Scattering

## Define the measurement

Record sample history, composition and form, radiation and wavelength, geometry, detector, polarization, slit and
resolution settings, angular or `q` calibration, scan range and step, exposure, rotation, environment, blank or
container, standard, and raw-file checksum. State whether the axis is `2theta`, `q`, or reciprocal length and whether
intensity is raw, corrected, normalized, or absolute.

## Choose the claim level

- Phase search identifies candidates; it does not prove purity or a refined structure.
- Pin the reference database, entry/card or CIF, snapshot, radiation, and calculated-pattern settings. Define peak-position
  tolerance from calibrated instrument resolution and zero-shift uncertainty, and predefine the intensity inclusion rule.
- Indexing proposes unit cells; test alternatives, impurities, and unindexed peaks.
- Rietveld refinement tests a declared structural model against the full pattern.
- Size and microstrain estimates require instrumental broadening and line-shape assumptions.
- SAXS/WAXS model fitting is often non-unique; report contrast, resolution smearing, background, and parameter covariance.

Use `$kdense-pymatgen` to calculate a pattern from a known structure, not as an experimental refinement engine.
Use `$cx-experimental-uncertainty-propagation` for calibration and parameter uncertainty, and
`$cx-condensed-matter-solid-state` for physical interpretation.

## Analyze

Correct or model background, zero shift, displacement, absorption, fluorescence, polarization, preferred orientation,
and instrument response only when justified. Add phases or free parameters based on residual structure and independent
evidence, not solely a lower fit statistic. Preserve the observed, calculated, background, and difference curves.

## Verify

- Check calibration against a standard and reproduce peak positions across scans or sample preparations.
- Account for every strong observed peak and every strong calculated peak; retain unidentified features.
- Report the peak or full-pattern match statistic, scan-range coverage, missing expected peaks, unmatched observed peaks,
  and sensitivity to the position and intensity thresholds; no universal match score proves phase identity.
- Inspect difference curves, parameter correlations, boundary hits, and physical constraints, not only `R` factors.
- Repeat plausible background, profile, orientation, size/strain, and phase models; report stability of conclusions.
- Validate CIF syntax and chemistry and, for quantitative phases, test standards, absorption, and amorphous contributions.

## Deliver

Report raw-data provenance, corrections, candidate phases or model, refinement strategy, fit diagnostics, covariance,
unassigned features, claim level, uncertainty, and files needed to reproduce the result.

## Source basis

Original workflow informed by IUCr powder-CIF and Rietveld guidance and the tool audit in
`../../docs/ANALYTICAL_SOURCES.md`.
