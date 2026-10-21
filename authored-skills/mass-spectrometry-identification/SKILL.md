---
name: mass-spectrometry-identification
description: "Identify and quantify support for analytes from mass spectrometry with explicit acquisition context, calibration, false-discovery control, and isomer-aware evidence. Use for GC-MS, LC-MS, MS/MS, accurate mass, isotope patterns, adducts, fragments, library searching, proteomics, metabolomics, and unknown identification."
license: MIT
---

# Mass Spectrometry Identification

## Decision contract
Act as an analyzer. Define the analyte/sample, matrix, acquisition scope, evidence cutoff, claim type (formula, compound class, structure, or quantity), and intended use. Prespecify identification taxonomy and its evidence requirements or use explicit evidence classes; define quantitative units, FDR/error criterion, uncertainty, applicability, and falsifier. Retain unresolved constitutional and stereochemical alternatives.

## Workflow
1. Record sample/preparation, separation, source, polarity, analyzer, resolving-power definition, scan range, profile/centroid state, calibration, lock mass, MS level, isolation width, collision method/energy, acquisition mode, blanks, pooled QC, standards, and raw checksum. Prefer mzML with controlled metadata while preserving vendor raw files and conversion parameters.
2. Route mzML processing, feature detection, alignment, quantification, identification, and FDR to `$kdense-pyopenms`; small-molecule spectrum cleaning/library comparison/networks to `$kdense-matchms`; file triage only to `$kdense-exploratory-data-analysis`; mass calibration and quantitative uncertainty to `$cx-experimental-uncertainty-propagation`. Package installation, database download, and proprietary conversion require approval. Pin tool, database/library snapshot, adduct list, tolerances, and preprocessing filters.
3. Inspect blanks, carryover, contaminants, isotopes, charge states, adducts, in-source fragments, and duplicate features. Generate neutral formula candidates from calibrated mass/isotope evidence without dropping charge/isotope labels. Compare MS/MS only with compatible precursor, polarity, collision energy, instrument class, and processing. Add retention index/time, authentic standard, isotope labeling, or complementary spectroscopy where available.
4. Verify by reprocessing representative raw/mzML files and auditing profile-to-centroid and deisotoping effects. Check precursor/fragment mass error, isotope fit, atom/formula consistency, diagnostic ions, and unexplained intense peaks. Estimate target-decoy FDR or appropriate empirical false-match rate; never map similarity directly to probability. Freeze thresholds using compatible independent standards, decoys, no-match spectra, and near-neighbor isomers; report library coverage and sensitivity. Keep library selection, calibration, and final evaluation distinct. Confirm across replicates, blanks, dilution series, and orthogonal standards where required.

## Outputs
Return normalized sample/acquisition inputs; features, filters, and inclusion/exclusion reasons; versioned database/library; ranked candidates; evidence for and against; error/FDR metrics; identification level; claim IDs/status (`supported`, `contradicted`, `inconclusive`, `unavailable`); uncertainty, dependencies, and limitations. Include unmatched-query/library coverage, unresolved isomers, smallest falsifiable next action, raw/conversion records and artifact paths/hashes via `$science-provenance`. Run `$science-review` before material identity or quantitative claims.

## Boundaries
Stop when calibration, precursor assignment, sample mapping, essential raw files, or method compatibility is unresolved. A library score is not a probability or unique identity; MS often cannot resolve isomers. No universal similarity cutoff exists. Report unmatched and unavailable data distinctly from negative evidence. Do not claim identification beyond the selected taxonomy's support or quantitative validity without calibration. Installation/download/conversion gates remain in force; preserve failed and inconclusive runs.

## Source basis
Original workflow informed by HUPO-PSI mzML, OpenMS, matchms, and NIST spectral practice documented in `../../docs/ANALYTICAL_SOURCES.md`.
