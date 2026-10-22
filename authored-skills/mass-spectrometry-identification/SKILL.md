---
name: mass-spectrometry-identification
description: "Identify and quantify support for analytes from mass spectrometry with explicit acquisition context, calibration, false-discovery control, and isomer-aware evidence. Use for GC-MS, LC-MS, MS/MS, accurate mass, isotope patterns, adducts, fragments, library searching, proteomics, metabolomics, and unknown identification."
license: MIT
---

# Mass spectrometry identification evidence

## Decision contract
Act as an analyzer. Define analyte/sample, matrix, acquisition scope, evidence cutoff, claim type (formula, compound class, structure, or quantity), and intended use. Prespecify and cite a named identification-confidence taxonomy with its evidence requirements, or use explicit evidence classes when no suitable taxonomy applies; define quantitative units, FDR/error criterion, uncertainty, applicability, and falsifier. Retain unresolved constitutional and stereochemical alternatives.

## Reference usage
Read [ms-identification-evidence.md](references/ms-identification-evidence.md) before the workflow steps Pin processing (pin-processing), Audit background (audit-background), Compare compatible evidence (compare-compatible-evidence), Calibrate error (calibrate-error), and Verify and classify (verify-and-classify). These IDs name the numbered actions below; use the reference criteria for confidence levels, mass accuracy, isotope and fragmentation evidence, and decoy-based error control.

## Workflow
1. **Check gates.** Stop and ask for clarification if calibration, precursor assignment, sample mapping, essential raw files or method compatibility is unresolved; if it cannot be resolved, classify the affected claim as unavailable/inconclusive and record missing items. Package installation, database download and proprietary conversion require approval.
2. **Freeze acquisition.** Record sample/preparation, separation, source, polarity, analyzer, resolving-power definition, scan range, profile/centroid state, calibration, lock mass, MS level, isolation width, collision method/energy, acquisition mode, blanks, pooled QC, standards and raw checksum. Prefer mzML with controlled metadata and preserve vendor raw/conversion parameters.
3. **Pin processing.** Route mzML processing, feature detection/alignment, quantification, identification and FDR to `$kdense-pyopenms`; small-molecule cleaning/library comparison/networks to `$kdense-matchms`; triage only to `$kdense-exploratory-data-analysis`; mass-calibration and quantitative uncertainty to `$cx-experimental-uncertainty-propagation`. Pin tools, database/library snapshot, adduct list, tolerances and filters.
4. **Audit background.** Inspect blanks, carryover, contaminants, isotopes, charge states, adducts, in-source fragments and duplicate features. Record neutral formula candidates from calibrated mass/isotope evidence without dropping charge/isotope labels.
5. **Compare compatible evidence.** Compare MS/MS only with compatible precursor, polarity, collision energy, instrument class and processing. Add retention index/time, authentic standard, isotope labeling or complementary spectroscopy when available. Record support and contradictions per candidate.
6. **Calibrate error.** Estimate target-decoy FDR or appropriate empirical false-match rate; never map similarity directly to probability. Freeze thresholds using compatible independent standards, decoys, no-match spectra and near-neighbor isomers; report library coverage, sensitivity and shared provenance.
7. **Verify and classify.** Reprocess representative raw/mzML and audit profile-to-centroid/deisotoping effects; check precursor/fragment mass error, isotope fit, atom/formula consistency, diagnostic ions and unexplained intense peaks. Keep library selection, calibration and final evaluation distinct; assign only the taxonomy supported.
8. **Report and hand off.** Confirm across replicates, blanks, dilution series and orthogonal standards where required. Report unmatched queries, unresolved isomers, uncertainty, limitations and next action; preserve failed/inconclusive runs and hashes with `$science-provenance`, then run `$science-review` before material identity or quantitative claims.

## Outputs
`ms-identification-evidence-v1` required fields: sample_and_acquisition; raw_and_conversion_hashes; processing_and_filter_versions; database_or_library_snapshot; feature_and_exclusion_register; ranked_candidates; evidence_for_and_against; error_and_fdr_metrics; identification_level; claim_register with statuses (`supported`, `contradicted`, `inconclusive`, `unavailable`); uncertainty; dependency_groups; library_coverage; unmatched_queries; unresolved_isomers; applicability_limits; next_action; provenance_receipt; review_receipt.

## Boundaries
Stop when calibration, precursor assignment, sample mapping, essential raw files, or method compatibility is unresolved. A library score is not a probability or unique identity; MS often cannot resolve isomers. No universal similarity cutoff exists. Report unmatched and unavailable data distinctly from negative evidence. Do not claim identification beyond the selected taxonomy's support or quantitative validity without calibration. Installation/download/conversion gates remain in force; preserve failed and inconclusive runs.

## Source basis
Original workflow informed by HUPO-PSI mzML, OpenMS, matchms, and NIST spectral practice documented in `../../docs/ANALYTICAL_SOURCES.md`.
