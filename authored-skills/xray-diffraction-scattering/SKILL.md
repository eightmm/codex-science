---
name: xray-diffraction-scattering
description: "Analyze and verify X-ray diffraction and scattering data. Use for powder XRD, phase identification, indexing, lattice parameters, Rietveld refinement, crystallite size or strain, texture, amorphous content, SAXS, WAXS, pair distributions, and comparison with calculated patterns."
license: MIT
---

# X-ray Diffraction and Scattering

## Decision contract
Act as an analyzer. Define sample history/composition/form, measurement type, question and claim level (candidate phase, phase identification, unit cell, structural model, size/strain, or scattering parameters), evidence cutoff, and intended use. Prespecify calibration/uncertainty, peak/intensity inclusion rules, fit acceptance, applicability, and falsifier. For SAXS/WAXS state model assumptions and non-uniqueness.

## Workflow
1. Record radiation/wavelength, geometry, detector, polarization, slit/resolution, angular or `q` calibration, scan range/step, exposure, rotation, environment, blank/container, standard, and raw checksum. State whether axis is `2theta`, `q`, or reciprocal length, and whether intensity is raw, corrected, normalized, or absolute.
2. For phase search pin reference database, entry/card or CIF, snapshot, radiation, and calculated-pattern settings. Define peak-position tolerance from calibrated instrument resolution and zero-shift uncertainty and prespecify intensity inclusion. Indexing proposes cells: test alternatives, impurities, and unindexed peaks. Rietveld tests a declared structural model against the full pattern. Size/microstrain need instrumental-broadening and line-shape assumptions. SAXS/WAXS fitting must report contrast, resolution smearing, background, and covariance.
3. Use `$kdense-pymatgen` to calculate a pattern from a known structure, not as an experimental refinement engine. Use `$cx-experimental-uncertainty-propagation` for calibration/parameter uncertainty and `$cx-condensed-matter-solid-state` for physical interpretation.
4. Verify by correcting/modeling background, zero shift, displacement, absorption, fluorescence, polarization, preferred orientation, and instrument response only when justified. Add phases/free parameters based on residual structure and independent evidence, not solely a lower fit statistic. Preserve observed, calculated, background, and difference curves. Check standard calibration and repeat peak positions across scans/preparations; account for strong observed and calculated peaks. Report match statistic, scan coverage, missing expected and unmatched observed peaks, and sensitivity to thresholds. Inspect difference curves, parameter correlations, boundary hits, physical constraints, and plausible model stability. Validate CIF syntax/chemistry; for quantitative phases test standards, absorption, and amorphous contributions.

## Outputs
Return normalized inputs and a machine-readable evidence/fit table with candidate phases/models, reference snapshot, corrections, refinement strategy, diagnostics, covariance, unassigned features, claim IDs/status (`supported`, `contradicted`, `inconclusive`, `unavailable`), uncertainty, dependencies, applicability limits, rejected alternatives, and smallest falsifiable next action. Preserve raw and derived curves, paths and hashes via `$science-provenance`. Run `$science-review` before material phase/structure or quantitative phase claims.

## Boundaries
Phase search is not proof of purity or refined structure; no universal match score proves phase identity. Indexing is not unique structural determination. SAXS/WAXS fits can be non-unique, and size/strain depends on instrument and line-shape assumptions. Stop if calibration, radiation, reference identity, or raw intensity semantics are unresolved. Retain unidentified peaks and failed/inconclusive fits; do not add phases or silently correct data only to improve fit statistics.

## Source basis
Original workflow informed by IUCr powder-CIF and Rietveld guidance and the tool audit in `../../docs/ANALYTICAL_SOURCES.md`.
