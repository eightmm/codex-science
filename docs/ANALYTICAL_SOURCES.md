# Analytical Chemistry Sources and Capability Audit

This registry records the official standards, tool documentation, and reference-data sources used to design the
Codex-native spectroscopy and analytical chemistry workflows. The skills are independent procedural syntheses;
they do not copy database spectra, proprietary methods, vendor files, or standards text.

## Existing capability audit

- `kdense-exploratory-data-analysis` recognizes NMR, MS, optical spectroscopy, X-ray, and chromatography formats,
  but performs file triage rather than defensible chemical inference.
- `kdense-matchms` supplies small-molecule MS filtering and similarity computation; it does not define an
  identification confidence or orthogonal-confirmation policy.
- `kdense-pyopenms` supplies current OpenMS processing, feature, identification, FDR, and quantification tools.
- `kdense-pymatgen` calculates powder patterns from candidate structures; it is not an experimental Rietveld engine.
- `cx-complex-fourier-analysis` and `cx-experimental-uncertainty-propagation` provide transform and uncertainty
  foundations but not modality-specific artifact or identity rules.

The new skills compose these capabilities rather than duplicate their APIs.

## Official sources

### NIST Chemistry WebBook, SRD 69

- Scope: evaluated or compiled IR, mass, UV-Vis, vibrational, retention, and thermochemical reference data.
- URL: <https://webbook.nist.gov/chemistry/>
- Usage boundary: preserve source and acquisition conditions; a reference match is candidate evidence, not identity proof.

### HUPO Proteomics Standards Initiative — mzML

- Scope: mass-spectrometry arrays, acquisition context, instrument configuration, processing, and controlled metadata.
- Repository: <https://github.com/HUPO-PSI/mzML>
- Usage boundary: preserve vendor raw data and record conversion, centroiding, and data-reduction parameters.

### OpenMS and pyOpenMS 3.5

- Scope: MS signal processing, feature detection, alignment, identification, FDR, quantification, and chromatography.
- Documentation: <https://pyopenms.readthedocs.io/en/release-3.5.0/>
- Usage boundary: pin algorithm parameters and database snapshots; validate representative outputs against raw data.

### matchms

- Scope: mass-spectrum metadata filtering, peak processing, similarity, and spectral networking.
- Documentation: <https://matchms.readthedocs.io/en/latest/>
- Usage boundary: similarity depends on preprocessing, tolerance, collision conditions, and library coverage.

### nmrML

- Scope: open interchange schema and controlled vocabulary for raw and processed NMR data.
- Repository: <https://github.com/nmrML/nmrML>
- Usage boundary: keep vendor acquisition data and record phase, baseline, apodization, reference, and transform choices.

### International Union of Crystallography

- Scope: CIF dictionaries, powder diffraction data, Rietveld results, and reporting guidance.
- CIF resources: <https://www.iucr.org/resources/cif>
- Powder guidance: <https://iucrdata.iucr.org/x/services/powder.html>
- Usage boundary: deposit observed and calculated data with difference curves; fit indices alone do not validate a model.

### ICH M10 bioanalytical method validation and study sample analysis

- Scope: chromatographic calibration, selectivity, accuracy, precision, recovery, stability, and in-study analysis.
- FDA final guidance page: <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/m10-bioanalytical-method-validation-and-study-sample-analysis>
- Final guidance: <https://www.fda.gov/media/162903/download>
- Usage boundary: apply the current jurisdiction- and purpose-specific standard; this source does not replace a laboratory SOP.

### NIST measurement uncertainty

- Scope: Type A and Type B components, combined and expanded uncertainty, and traceable reporting.
- Registry entry: [`TEXTBOOK_SOURCES.md`](TEXTBOOK_SOURCES.md#barry-n-taylor-and-chris-e-kuyatt--nist-technical-note-1297)

## Skills grounded in this registry

- `spectroscopy-spectral-inference`
- `nmr-structure-analysis`
- `mass-spectrometry-identification`
- `xray-diffraction-scattering`
- `chromatography-quantification`
- `chemical-structure-elucidation`
