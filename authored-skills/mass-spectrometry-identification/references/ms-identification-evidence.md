# Mass spectrometry identification evidence

## Claim semantics

Use the skill's four statuses consistently. Supported means prespecified evidence meets the criterion for the stated identification or measurement claim. Contradicted means a reliable, compatible observation conflicts with it. Inconclusive means multiple structures, formulae, or interference explanations remain consistent with the evidence. Unavailable means required raw data, calibration, sample mapping, or search-space information is missing.

For small molecules, when its assumptions fit the experiment, use the five confidence levels of Schymanski et al. (2014): Level 1 confirmed structure; Level 2 probable structure; Level 3 tentative candidate(s); Level 4 unequivocal molecular formula; Level 5 exact mass of interest. State the evidence that supports the assigned level. A spectral similarity score or library rank alone does not establish a probability or Level 1 identity.

For peptides, use target-decoy false discovery control rather than the small-molecule levels. State the search database, enzyme and modification rules, decoy construction, score threshold, and the level at which false discovery rate (FDR) or q-value is controlled: peptide-spectrum match, distinct peptide, or protein group. An aggregate FDR controls a set under its assumptions; it is not an individual peptide's posterior probability.

## Mass accuracy and isotope evidence

Record precursor and fragment mass errors in the reported unit (ppm, mDa, or both), calibration state, resolving-power definition, mass range, lock-mass use, and acceptance tolerance. Give the observed error distribution or representative range for relevant standards and samples. Do not transfer one tolerance across instruments or mass ranges without calibration evidence.

Assess isotope spacing for charge state and compare observed isotope pattern with the proposed elemental composition at the acquired resolution and signal-to-noise. Check overlapping ions, isotope peaks from contaminants, natural isotope abundance assumptions, adducts, and in-source fragments. Formula evidence does not establish connectivity.

## Fragmentation and library evidence

Compare MS/MS only when precursor assignment, adduct, polarity, collision regime, instrument class, and processing are sufficiently compatible. Record diagnostic product ions, neutral losses, collision energy, relative abundance where reproducible, unexplained intense peaks, and evidence against the proposed structure. A match that depends on one common fragment or a library spectrum from the same source is weak.

For Level 1 small-molecule confirmation, compare an authentic reference standard acquired under compatible conditions using orthogonal observables such as retention and fragmentation as appropriate. If no standard is available, assign only the confidence level justified by the reference data and retain constitutional, regio-, and stereochemical alternatives.

## Source dependencies and independence

Record sample preparation, batch, instrument and acquisition method, calibration, conversion software, centroiding/deisotoping, feature grouping, database or library release, search space, and evidence cutoff. Preserve vendor data and conversion parameters alongside mzML when available. Pin every release and parameter set needed to reproduce results.

Group repeated injections, scans, precursor isotopes, adducts, fragments, reprocessed spectra, and library entries derived from a shared spectrum. They may provide different observables but are not independent sample replications. For peptides, distinguish spectra and runs from shared sample preparation and disclose shared database or training/reference provenance.

## Error and uncertainty reporting

Keep mass measurement uncertainty, isotope-pattern ambiguity, spectral match uncertainty, structural ambiguity, and FDR as distinct quantities. Report calibration uncertainty and mass error for the actual range. For quantitative claims, propagate standard, sample preparation, dilution, response, matrix, and replicate components relevant to the measurand.

Report score or error statistic definition, search space, decoy strategy, threshold, controlled entity level, and coverage. Do not call a database score a probability, or interpret a set-level FDR as the probability that a particular reported identification is false. Retain unmatched spectra and queries as data, not as negative confirmations.

## Controls and decoys

Use calibration and lock-mass checks, known standards, blanks, pooled QC, and appropriate replicate or dilution checks. For small-molecule library matching, include no-match spectra and near-neighbor structures where feasible; decoy or shuffled spectra can diagnose permissive matching only when the decoy process resembles the relevant null comparisons.

For peptide search, construct target and decoy sequences under a stated strategy, check target/decoy score behavior, and report FDR at the entity level used for the claim. Avoid contaminant-only decoys or decoys with a materially easier score distribution. Inspect blank carryover and common contaminants before interpreting sample hits.

## Sensitivity analyses

Vary defensible mass tolerances, calibration, charge/adduct assignments, isotope-fit threshold, centroiding and deisotoping, peak filters, collision energy, library snapshot, similarity settings, and decoy/search parameters. Keep the raw spectrum and fixed evaluation set so selection changes can be identified.

Report whether formula, confidence level, ranking, unmatched-query set, or peptide FDR changes. A result is fragile if a defensible perturbation changes the reported confidence level, removes key fragments, changes target-decoy acceptance, or exposes a plausible near-neighbor. Downgrade and name a resolving measurement, such as a standard, alternative collision energy, ion mobility, or orthogonal spectroscopy.

## Applicability domain

Limit formula and identity claims to the calibrated mass range, charge/adduct states, resolution, acquisition mode, sample matrix, fragmentation conditions, library coverage, and peptide search space actually evaluated. Small-molecule confidence levels do not resolve stereoisomers unless the evidence distinguishes them. Spectral libraries are sparse and instrument-dependent.

Peptide FDR is conditional on the target-decoy design, database composition, scoring and filtering procedure; it does not automatically validate localization of labile modifications, variant peptides, or results outside the searched sequence space. Do not transfer an FDR threshold to another search space without re-estimation.

## Common failure modes and detection

- **Mass calibration drift:** inspect lock-mass and standard residuals across the acquisition; recalibrate under a recorded procedure or withhold affected mass claims.
- **Wrong precursor or adduct:** compare isotope spacing, charge, chromatographic coelution, and source conditions; retain alternate assignments when unresolved.
- **Isotope interference:** inspect profile data and neighboring ions; test formula fit only after resolving charge and overlap.
- **Incompatible library match:** compare precursor, instrument, collision conditions, and preprocessing; downgrade when similarity is driven by generic fragments.
- **Decoy design or level mismatch:** audit target/decoy construction and reported entity level; do not infer individual confidence from a global FDR.
- **False independence or carryover:** trace injections, source spectra, blanks, and shared preparation; group dependent evidence and flag affected samples.
- **Missing search coverage:** report unmatched queries, library/database snapshot, and search space; do not turn no match into evidence of absence.

## Confidence assignment checks

Level 1 is a confirmed structure only when an authentic standard supports the match under compatible conditions; record which orthogonal observables agree. Level 2 is a probable structure with strong reference or diagnostic evidence, but state any remaining isomer limitation.

Level 3 retains one or more tentative structures because the evidence does not yet select a unique structure. Level 4 supports an unequivocal molecular formula without a unique connectivity claim. Level 5 records an exact mass of interest when formula assignment is not established.

Do not turn a database or in-silico match into a higher confidence level without the evidence required by that level. For peptides, report sequence and modification-localization uncertainty separately from the FDR threshold, and state whether the threshold applies to spectra, peptides, or protein groups.

For every unmatched query, retain the raw-spectrum identifier, precursor/adduct assignment, filters applied, and libraries or search databases evaluated. “Unmatched” means no match was returned in the stated search space; it does not mean the analyte is absent or novel.

Record whether small-molecule confidence was assigned from a library spectrum, diagnostic fragment reasoning, standard comparison, or formula evidence, and keep those evidence types visible in the claim table.

Report peptide decoy counts and the score threshold alongside FDR or q-value. If a modification site is not localized by fragment ions spanning the site, state the localization as unresolved even when the peptide sequence passes its FDR rule.

When fragments are shared by many structures, state that they support a substructure or class only. Retain the unassigned product ions and explain whether they are low abundance, interference, or unexplained.

## Sources and boundaries

Schymanski et al. (2014), “Identifying Small Molecules via High Resolution Mass Spectrometry: Communicating Confidence,” defines the five-level small-molecule confidence scheme (DOI 10.1021/es5002105). Elias and Gygi (2007), “Target-decoy search strategy for increased confidence in large-scale protein identifications by mass spectrometry,” describes target-decoy control for proteomics (DOI 10.1038/nmeth1019). mzML is an interchange standard; OpenMS/pyOpenMS 3.5 and matchms documentation describe tools, not universal identification thresholds.
