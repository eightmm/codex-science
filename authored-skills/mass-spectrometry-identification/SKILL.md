---
name: mass-spectrometry-identification
description: "Identify and quantify support for analytes from mass spectrometry with explicit acquisition context, calibration, false-discovery control, and isomer-aware evidence. Use for GC-MS, LC-MS, MS/MS, accurate mass, isotope patterns, adducts, fragments, library searching, proteomics, metabolomics, and unknown identification."
license: MIT
---

# Mass Spectrometry Identification

## Capture acquisition context

Record sample and preparation, separation, ion source, polarity, analyzer, resolving power definition, scan range,
profile or centroid state, calibration, lock mass, MS level, isolation width, collision method and energy, acquisition
mode, blanks, pooled QC, standards, and raw-file checksum. Prefer mzML with controlled metadata while preserving
vendor raw data and conversion parameters.

## Route the computation

- Use `$kdense-pyopenms` for mzML inspection, feature detection, alignment, quantification, identification, and FDR.
- Use `$kdense-matchms` for small-molecule spectrum cleaning, library comparison, and similarity networks.
- Use `$kdense-exploratory-data-analysis` for file triage only.
- Use `$cx-experimental-uncertainty-propagation` for mass calibration, response, and quantitative uncertainty.

Package installation, database download, and proprietary conversion remain approval-gated. Pin tool, database,
spectral-library snapshot, adduct list, tolerances, and every preprocessing filter.

## Build identification evidence

1. Inspect blanks, carryover, contaminants, isotopes, charge states, adducts, in-source fragments, and duplicate features.
2. Establish neutral formula candidates from calibrated mass and isotope evidence without dropping charge or isotope labels.
3. Compare MS/MS only under compatible precursor, polarity, collision energy, instrument class, and processing.
4. Add orthogonal retention index/time, authentic standard, isotope labeling, or complementary spectroscopy when available.
5. Select and cite a named identification-confidence taxonomy appropriate to the domain before assigning levels; record
   its required evidence. If no suitable taxonomy applies, use explicit evidence classes instead of inventing a level.
6. Retain alternative constitutional or stereochemical isomers that MS cannot distinguish.

## Verify

- Reprocess representative files from raw or mzML and audit profile-to-centroid and deisotoping effects.
- Check precursor and fragment mass error, isotope fit, atom/formula consistency, diagnostic ions, and unexplained intense peaks.
- Estimate target-decoy FDR or an appropriate empirical false-match rate; never map a similarity score directly to probability.
  Freeze the threshold on compatible independent standards, decoys, no-match spectra, and near-neighbor isomers, then report
  library coverage and sensitivity at that threshold. There is no universal similarity cutoff.
- Keep library selection, threshold calibration, and final evaluation data distinct; report unmatched queries and coverage.
- Confirm candidates across replicates, blanks, dilution series, and an orthogonal standard where the claim requires identity.

## Deliver

Report acquisition and conversion provenance, features and filters, database/library version, ranked candidates, evidence
for and against each, error and FDR metrics, identification level, uncertainty, and unresolved isomers.

## Source basis

Original workflow informed by HUPO-PSI mzML, OpenMS, matchms, and NIST spectral practice documented in
`../../docs/ANALYTICAL_SOURCES.md`.
