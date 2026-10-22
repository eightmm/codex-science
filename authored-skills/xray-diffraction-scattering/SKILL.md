---
name: xray-diffraction-scattering
description: "Analyze and verify X-ray diffraction and scattering data. Use for powder XRD, phase identification, indexing, lattice parameters, Rietveld refinement, crystallite size or strain, texture, amorphous content, SAXS, WAXS, pair distributions, and comparison with calculated patterns."
license: MIT
---

# X-ray Diffraction and Scattering

## Decision contract
Act as an analyzer. Before interpreting data, define sample history, composition and form; measurement type; question and intended use; evidence cutoff; and claim level (candidate phase, phase identification, unit cell, structural model, size/strain, or scattering parameters). Prespecify calibration and uncertainty, peak and intensity inclusion rules, fit acceptance criteria, applicability domain, and a falsifier. For SAXS/WAXS, state model assumptions and non-uniqueness. Keep phase search, indexing, structural refinement, and quantitative phase analysis as distinct claims.

## Reference usage
Read [powder diffraction and scattering inference](references/powder-scattering-inference.md) before assigning powder-pattern claims, comparing reference patterns, refining a structural model, estimating size/strain or quantitative phase fractions, or interpreting SAXS/WAXS fits. The reference sets evidence and failure criteria; it is not evidence about the sample.

## Workflow
1. Define the requested claim and its decision use; proceed only when sample state, evidence cutoff, claim level, and a falsifier are explicit, and record them with stable claim IDs.
2. Preserve raw files and checksums; determine whether the data are powder diffraction, SAXS, WAXS, or another scattering measurement, and record radiation/wavelength, geometry, detector, polarization, resolution, scan range/step, exposure, rotation, environment, blank/container, and standard. Record whether the axis is `2theta`, `q`, or reciprocal length and intensity is raw, corrected, normalized, or absolute.
3. Check calibration and data quality against the standard, blank, repeat scans, axis units, coverage, and counting/background behavior; if radiation, calibration, axis, or intensity semantics are unresolved, stop the affected claim and record the gap.
4. Choose a method suited to the claim: use reference search for candidates, indexing to propose cells, Rietveld only to test a declared structural model against the full pattern, line-profile analysis for size/strain only with instrument broadening and line-shape assumptions, and explicit scattering models for SAXS/WAXS. Record why alternatives are unsuitable.
5. Pin every reference database and entry/card/CIF by source, identifier, version or snapshot, retrieval date, radiation, and calculated-pattern settings; accept a candidate only when calibrated positions and declared intensity evidence satisfy prespecified criteria, recording unmatched observed and missing expected features.
6. Apply background, zero-shift, displacement, absorption, fluorescence, polarization, preferred-orientation, or instrument-response corrections only when justified by measurement physics and controls; retain raw and corrected data and record the correction model and parameters.
7. Fit the simplest credible model; add phases or free parameters only when residual structure and independent evidence justify them. Inspect observed, calculated, background and difference curves, match/fit statistics, scan coverage, missing expected and unmatched observed peaks, covariance, parameter correlations, boundary hits, physical constraints, and standard/repeat behavior; record unresolved features and every rejected or failed fit.
8. Vary plausible peak thresholds, background and correction choices, reference entries, line shapes, fit ranges, and model complexity; call the result fragile if claim status, phase set, cell, fraction, or key parameter changes beyond the prespecified tolerance, and record the comparison.
9. Verify CIF syntax/chemistry and quantitative-phase assumptions, including standards, absorption and amorphous contribution; emit the schema below, preserve raw and derived curves, paths and hashes via `$science-provenance`, and run `$science-review` before material phase/structure or quantitative phase claims.

## Outputs
Return one `xray-evidence-reconciliation-v1` record per analysis with required fields: `claim_id`, `claim_class`, `claim_status` (`supported`, `contradicted`, `inconclusive`, `unavailable`), `sample_and_measurement`, `raw_artifacts`, `calibration_and_uncertainty`, `reference_dependencies`, `method_and_corrections`, `fit_or_scattering_diagnostics`, `controls`, `sensitivity`, `unassigned_features`, `alternatives_and_rejections`, `applicability_limits`, `next_falsifiable_action`, and `review_and_provenance`. Include candidate phases/models, reference snapshot, covariance, units and uncertainty where applicable; retain paths and hashes.

## Boundaries
Phase search is not proof of purity or refined structure; no universal match score proves phase identity. Indexing is not unique structural determination. SAXS/WAXS fits can be non-unique, and size/strain depends on instrument and line-shape assumptions. Stop if calibration, radiation, reference identity, or raw intensity semantics are unresolved. Retain unidentified peaks and failed/inconclusive fits; do not add phases or silently correct data only to improve fit statistics. `$kdense-pymatgen` calculates a pattern from a known structure; it is not an experimental refinement engine. Use `$cx-experimental-uncertainty-propagation` for calibration/parameter uncertainty and `$cx-condensed-matter-solid-state` for physical interpretation.

## Source basis
Original workflow informed by IUCr powder-CIF and Rietveld guidance and the tool audit in `../../docs/ANALYTICAL_SOURCES.md`.
