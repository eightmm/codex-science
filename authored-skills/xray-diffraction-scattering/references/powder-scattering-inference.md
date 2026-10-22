# Powder diffraction and scattering inference

Use this reference to choose the strength of diffraction or scattering claims. A fit statistic summarizes a specified model/data comparison; it does not measure truth by itself.

## Claim semantics

- **Observed feature:** a peak, diffuse feature, edge, or oscillation appears in the retained measurement. Assign only after checking coverage, background, resolution, and artifact flags; record its coordinates and uncertainty.
- **Candidate phase:** a pinned reference pattern is compatible with a subset of calibrated peaks. Require several diagnostic positions within a tolerance derived from calibration and instrumental resolution, and account for unmatched observed and missing expected features. State alternatives and reference-library coverage.
- **Phase identification:** a candidate is supported across diagnostic features and plausible competing phases, with appropriate standard or orthogonal sample evidence. A database hit or aggregate match score alone remains a candidate.
- **Indexed unit cell:** report a cell only as the solution of a declared indexing problem. Preserve indexed/unindexed peaks, systematic absences if available, alternative cells, and impurity checks; indexing does not determine a unique structure.
- **Structural model / Rietveld result:** a declared CIF or model is compatible with the full pattern under justified instrument, background, profile, and sample terms. Report observed/calculated/background/difference curves, fit range and statistics, parameter correlations, boundary hits, and chemical/physical plausibility. A lower residual alone cannot justify added phases or parameters.
- **Size or microstrain:** an apparent line-broadening estimate is conditional on instrumental broadening, profile family, size/strain model, and reflection coverage. Separate coherent-domain size from particle size and report model covariance.
- **Quantitative phase result:** a fraction is supported only under a stated calibration or standard method, absorption/microabsorption assumptions, crystallinity coverage, and amorphous contribution treatment. Report normalization basis and uncertainty; do not equate crystalline normalized fractions with total composition.
- **SAXS/WAXS or pair-distribution parameters:** report model-dependent parameters with contrast, resolution smearing, background, q-range, transform/window choices where applicable, parameter covariance, and plausible alternative models. Non-unique fits remain conditional and may be inconclusive.

Use statuses consistently: `supported` means the prespecified evidence and controls support this bounded claim; `contradicted` means a discriminating observation conflicts with it; `inconclusive` means evidence is ambiguous, underpowered, or model-dependent; `unavailable` means required evidence or measurement information is missing.

## Source dependencies and independence

Pin the raw-file identity and checksum, sample/preparation identity, instrument and calibration-standard identities, radiation/wavelength, software/version and settings, and each database entry/CIF accession with release or snapshot and retrieval date. Preserve CIF provenance and calculated-pattern radiation/profile settings. Do not treat alternate database cards derived from one structure, repeated scans of one mounting, or multiple refinements of one pattern as independent evidence. Record shared sample batches, databases, calibrations, preprocessing, structural sources, code, and model assumptions. Repeat preparations are stronger than repeated scans, but shared synthesis or instrument calibration still links their errors.

For calculated patterns, record structure provenance, occupancy/disorder assumptions, radiation wavelength, peak-shape model, and whether intensities include thermal or preferred-orientation terms. A CIF can be syntactically valid and chemically plausible yet still represent the wrong specimen or polymorph. Keep candidate provenance separate from refined parameters so a fit cannot silently rewrite the source model.

For scattering reductions, record detector mask, transmission, absolute-intensity calibration, thickness/path length, background subtraction, q calibration, binning, and resolution kernel. If records or reductions share detector frames, calibration, or background subtraction, mark them as dependent. Averaging repeated reductions of one frame does not add independent observations.

## Uncertainty

Separate counting/repeatability uncertainty, axis and intensity calibration, specimen displacement, reference-structure uncertainty, fit covariance, and model ambiguity. Carry units and uncertainty through peak positions, cell parameters, widths, phase fractions, and scattering parameters. State the propagation method and assumptions; include covariance or parameter correlation when it materially affects interpretation. Do not convert a fit standard deviation into total uncertainty when calibration, absorption, or model discrepancy dominates. Record excluded peaks, ranges, and data with reasons.

Propagate angular uncertainty into d-spacing and cell parameters using the stated wavelength and geometry; preserve correlated zero-shift or wavelength terms rather than treating every peak as independent. For line broadening, distinguish uncertainty in instrument-profile subtraction from regression error across reflections. For phase fractions, include calibration and absorption uncertainty, and state when an amorphous fraction is unmeasured. For scattering, include covariance and resolution/background uncertainty in derived length scales or distributions.

## Controls and sanity checks

- Measure a certified or otherwise appropriate standard to check zero shift, line position, instrumental profile, and resolution near the relevant range; record measured deviations against the lab's prespecified tolerance.
- Use blank/container/background measurements and repeat scans to reveal parasitic scattering, fluorescence, drift, or unstable specimen mounting.
- Compare expected strong reflections and observed unassigned reflections, including low-angle and edge-of-range features; check missing peaks rather than scoring only matched peaks.
- For quantitative phase work, use a justified internal/external standard or validated calibration and test mixtures or recovery when available. Check whether absorption and amorphous content invalidate normalization.
- For SAXS/WAXS, inspect empty-cell/background, transmission/normalization, q calibration, resolution smearing, low-q parasitic scattering, and high-q coverage before interpreting model parameters.
- Check whether peak positions or intensities depend on specimen rotation, mounting, or exposure; systematic dependence flags texture, settling, beam damage, or changing sample state.
- Inspect standards before and after the specimen series when drift is plausible. A bracketed standard that exceeds the declared tolerance invalidates claims requiring that calibration interval.

## Sensitivity and fragility

Vary plausible peak-detection thresholds, background functions, zero shift, specimen displacement, fit range, excluded regions, profile/line-shape families, preferred orientation terms, phase set, and initial parameters. For SAXS/WAXS vary background, q-window, resolution smearing, contrast, and plausible model families. Define tolerances before seeing the desired result. Treat a claim as fragile when its status changes, a phase enters/leaves, the selected cell/model changes, or a reported parameter/fraction shifts beyond its propagated uncertainty or declared practical tolerance. Report the direction and size of changes; do not average incompatible models into false precision.

Do not define tolerances after seeing which model is preferred. If no validated tolerance exists, report the tested range and classify stability qualitatively. A robust candidate phase can coexist with fragile quantitative fractions; assign status at the claim level rather than transferring confidence from one claim to another.

## Applicability domain and failure modes

This workflow assumes traceable raw intensity data and enough calibrated angular/q coverage to discriminate the proposed claim. Severe texture, preferred orientation, overlapping phases, nanoscale broadening, low abundance, amorphous material, fluorescence, absorption/microabsorption, radiation damage, changing sample state, or an inadequate reference library can defeat powder identification or quantification. Sparse or narrow q-ranges, uncertain contrast, aggregation, multiple scattering, poor background subtraction, and resolution-limited features can make scattering fits non-identifiable.

Do not generalize a powder phase list to local structure, surface chemistry, reaction pathway, or biological activity. Powder averaging loses directional and spatial information. Laboratory source, geometry, detector, and sample environment matter; a protocol validated on one instrument or composition range does not automatically transfer to another.

For quantitative phase analysis, distinguish weight, mole, and volume fraction and state the normalization basis. Preferred orientation, peak overlap, microabsorption, solid solution, and amorphous content can bias all three. If the reference set omits a plausible phase, unexplained intensity is not evidence that the omitted phase is absent.

For total scattering/PDF claims, retain the transform window, termination effects, qmax, background and container correction, and real-space range. Peak-like residuals caused by finite q range or reduction artifacts should not be interpreted as local structural motifs without robustness checks.

| Failure mode | Detection and response |
|---|---|
| Zero shift or displacement mimics lattice change | Standard and repeat mounting disagree; recalibrate or report cell claim inconclusive. |
| Preferred orientation or texture distorts intensities | Relative intensities vary by mount/rotation while positions persist; weaken intensity-based identity or quantitative claims. |
| Extra phase added to absorb residuals | Improvement lacks independent peaks/chemistry or is unstable to fit range; reject or label as exploratory. |
| Unmodeled amorphous or absorption contribution | Standard/recovery or mass balance fails; do not report total composition from crystalline fractions. |
| Instrumental width mistaken for sample size/strain | Standard profile or line-shape choice changes estimate materially; report conditional estimate or abstain. |
| Non-unique SAXS/WAXS model | Alternative plausible models fit comparably with different parameters; report alternatives and downgrade parameter claims. |
| Unindexed feature dismissed as noise | Feature repeats or lies outside candidate patterns; retain it as unassigned and investigate artifact/phase alternatives. |

## Sources and scope

- Rietveld, H. M. (1969), “A profile refinement method for nuclear and magnetic structures,” *Journal of Applied Crystallography*. This is the original profile-refinement method, not a universal model-validity criterion.
- McCusker et al. (1999), IUCr Commission on Crystallographic Nomenclature report, “Rietveld refinement guidelines.” It supports reporting and refinement practice; it does not validate a particular sample model.
- International Union of Crystallography, powder diffraction and CIF resources, as recorded in `docs/ANALYTICAL_SOURCES.md`; use the current applicable dictionary/guidance for deposition details.

The claim criteria and controls above are a procedural synthesis for this skill. The cited sources do not provide universal score thresholds; derive tolerances from the instrument, intended decision, and validated method.

## Decision record

For each claim, state which observations would raise, lower, or leave it unchanged. A candidate match with unexplained peaks may support presence while leaving completeness or purity unavailable. A structural model may explain the measured pattern without being unique. A stable fit under tested settings does not establish that untested models are false.

Record the evidence that would discriminate the leading alternatives: a higher-resolution region, changed wavelength, rotated or repacked specimen, standard mixture, independent chemical assay, or additional q-range. Mark such work as a proposed next action, not an observed result.

When a control fails, quarantine only the dependent claim or result. For example, failed angular calibration prevents a cell claim but need not erase a qualitative observation that a broad feature is present. Preserve both the failure and the claims it invalidates in the reconciliation record.

Report successful checks and failed checks with the same visibility. Do not omit a poor fit, unmatched peak, or sensitivity run because another candidate looks cleaner. Keep the complete comparison artifacts discoverable through the provenance handoff.
