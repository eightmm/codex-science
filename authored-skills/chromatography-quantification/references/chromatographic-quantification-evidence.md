# Chromatographic quantification evidence

## Claim semantics

Use the skill's four statuses consistently. Supported means prespecified assay evidence meets the criterion for the stated measurand or batch decision. Contradicted means a valid control or sample measurement conflicts with that criterion. Inconclusive means unresolved coelution, matrix interference, unstable response, or conflicting QC prevents a decision. Unavailable means raw data, units, calibration, or required method records are missing.

Keep detection, retention-time association, analyte identity, concentration or amount, recovery, purity, and batch acceptance as separate claims. Detection requires a signal above a declared decision threshold. Retention time alone is not identity. Quantification requires an accepted calibration and quality controls over the reported interval. Batch acceptance requires all prespecified sample-level and run-level rules to pass.

## Calibration and reportable range

Record the measurand, response definition, standard identity and traceability, concentrations, preparation, calibration model, weighting, fit procedure, and accepted range. Evaluate residual patterns and back-calculated calibrators across the range; correlation alone does not establish an adequate model. Inspect the low and high ends separately for bias, heteroscedasticity, saturation, and insufficient selectivity.

Report the validated calibration range separately from the instrument response range and any dilution-adjusted reportable range. Do not extrapolate beyond accepted calibrators. If a nonlinear model is used, document why it is suitable and how it was selected before unknown results are reviewed.

## Detection and quantification limits

State how the limit of detection (LOD) and limit of quantification (LOQ) were estimated, which matrix and analyte level the estimate covers, and the intended decision use. A signal-to-noise ratio alone does not demonstrate reliable detection or quantification. Demonstrate the lower reportable limit with appropriate blanks, low-level samples, and precision or bias evidence suited to the method.

Keep the estimated detection limit distinct from the validated lower calibration limit. If a sample response lies between these boundaries, report detection or quantification only under the declared rules; do not substitute zero, the LOD, or the LOQ without an explicit convention.

## Matrix effects, recovery, and preparation

For the actual matrix and preparation, assess selectivity, extraction recovery, matrix effect, dilution integrity, stability, and internal-standard behavior where relevant. State whether comparison used neat standards, post-extraction spikes, or pre-extraction spikes; these answer different questions. Report the sample preparation and recovery evidence alongside the reported measurand.

An internal standard can correct shared variation only when its behavior tracks the analyte through the relevant steps. A structural analogue is not automatically commutable. Matrix-specific response, ion suppression/enhancement, extraction losses, adsorption, degradation, and coelution can invalidate transfer of a calibration from solvent or another matrix.

## System suitability and carryover

Define run-specific system suitability before analyzing the batch: relevant retention stability, resolution or selectivity, peak shape, response range, pressure or detector checks when applicable, and performance of standards/QCs. Document observed values, acceptance limits, and the sequence position of each check. A suitability failure affects the interval of samples bounded by valid checks according to the written procedure.

Place solvent and matrix blanks in positions that can reveal contamination and carryover, especially after high-concentration samples and near low-level decisions. Report blank response relative to the stated analyte decision rule. Investigate carryover through wash conditions, injection order, blank response, and repeat runs; do not delete a blank or change the threshold after observing it.

## Source dependencies and independence

Track the standards lot and preparation, stock and working solutions, calibration batch, QC preparation, sample extraction batch, sequence, instrument, column, processing version, and method revision. Calibrators and QCs made from a common stock share preparation uncertainty; samples from one extraction batch share matrix and recovery effects. Group dependent records and state the independence basis for any external QC.

Technical reinjections, repeated integration of one chromatogram, and replicate aliquots from one extraction do not create independent biological or process samples. Pin method and software versions, reference standards and lots, integration parameters, and raw-file hashes so the assay can be reconstructed.

## Measurement uncertainty

Separate uncertainty in the estimated concentration from variability among samples and from identity uncertainty. Include relevant contributions from standards and purity, weighing or volumetric preparation, dilution, calibration fit, recovery, matrix effects, integration, repeatability, and sampling. State which components were quantified and which remain unquantified.

Report units, uncertainty interval or justified bound, coverage convention, and decision rule. Near a specification or action limit, show whether the uncertainty interval crosses that limit. Do not report more precision than supported by calibration, sample preparation, and integration.

## Controls and acceptance checks

Use traceable calibrators, low/mid/high QCs as suitable to the range, blank matrix, zero sample when an internal standard is used, and carryover blanks. Include pre- and post-extraction spikes when recovery and matrix effects must be distinguished. Check retention and peak resolution against authentic standards when identity is material.

Prespecify control acceptance and handling of failed runs, reinjections, and exclusions. A failed QC or system suitability result blocks the affected quantitative or batch claim until the written procedure resolves it. Retain the original failed result and all subsequent measurements.

## Sensitivity analyses

Recalculate results under defensible integration boundaries, baseline methods, calibration weighting or model, accepted calibrator set, dilution, recovery correction, and uncertainty assumptions. Include alternative peak attribution where coelution is plausible. Do not choose a model or integration solely because it gives the desired pass/fail decision.

Report changes in concentration, uncertainty interval, LOD/LOQ decision, and batch status. The result is fragile if an admissible choice changes reportable status, crosses an action limit, or shifts the result by more than its stated uncertainty. Identify the smallest resolving action, such as re-extraction, dilution, improved separation, or matrix-matched calibration.

## Applicability domain

Limit conclusions to the declared analyte, matrix, sample preparation, detector, column and mobile/carrier phase, gradient or program, concentration range, stability window, and batch conditions. Area percent describes detector response under the stated method; it is not automatically mass fraction or mole fraction.

Do not transfer calibration, LOD/LOQ, recovery, or QC limits across materially different matrices, extraction protocols, detectors, columns, or regulatory purposes without validation. Coeluting compounds, unstable analytes, samples outside the calibrated range, and uncharacterized matrix interference are outside the demonstrated domain.

## Common failure modes and detection

- **Calibration curvature or end bias:** inspect residuals and back-calculated standards by level; restrict the range or revise the model under a prespecified procedure.
- **Matrix suppression or enhancement:** compare matrix-matched and neat/post-extraction responses; report the matrix domain and assess recovery separately.
- **Integration drift or coelution:** inspect chromatograms, peak shape, resolution, boundaries, and blinded reintegration; keep unresolved analyte contribution inconclusive.
- **Unproven low-level result:** compare blanks, low-level replicates, precision, and the defined LOD/LOQ procedure; report below-range observations without forced numeric substitution.
- **Carryover or contamination:** inspect preceding high samples, wash steps, sequence blanks, and blank response; flag affected neighboring samples under the batch rule.
- **System suitability or QC failure:** compare recorded checks with prespecified limits and sequence location; block the affected range rather than averaging away failure.
- **Untraceable calibration:** verify standard identity, purity, lot, stock preparation, and hashes; treat unsupported concentration results as unavailable.

## Peak integration and identity boundaries

Retain the chromatogram, integration start and end, baseline rule, peak assignment, and every manual change for each reportable result. Integrate controls and unknowns under the same locked procedure unless a documented exception is allowed by the method.

For unresolved shoulders or coelution, inspect resolution and orthogonal detector evidence before assigning area to one component. A retention match on a nonselective detector may support an association but cannot distinguish a coeluting interferent.

For a linear calibration claim, inspect response residuals throughout the accepted interval and confirm that dilution or concentration does not move samples outside that interval. Record detector saturation and integration clipping as invalidating conditions, even if the software returns an area.

There is no universal LOD, LOQ, carryover, or system-suitability threshold across analytes and methods. The method and intended decision must supply the limits; preserve the supporting blank, low-level, and suitability observations.

## Sources and boundaries

ICH M10 (2022), *Bioanalytical Method Validation and Study Sample Analysis*, covers validation and study-sample analysis for its stated bioanalytical scope; it does not define universal limits for every assay. Taylor and Kuyatt, NIST Technical Note 1297 (1994), describes measurement uncertainty components and reporting. OpenMS/pyOpenMS 3.5 documentation describes supported processing tools, not assay validation criteria.
