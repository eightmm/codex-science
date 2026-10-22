# NMR evidence interpretation

## Claim semantics

Use the skill's four statuses consistently. Supported means the prespecified spectral observations satisfy the criteria for the stated NMR claim. Contradicted means a reproducible, adequately detectable observation conflicts with it. Inconclusive means overlap, exchange, inconsistent correlations, or competing assignments prevent a decision. Unavailable means the FID, acquisition context, or sample state needed to decide is absent.

Keep signal detection, atom-to-resonance assignment, connectivity, relative stereochemistry, and absolute stereochemistry as separate claims. A high assignment confidence requires a reproducible signal with a coherent integral and multiplicity and an unambiguous path through the relevant 1D and 2D evidence. Moderate confidence retains one plausible alternative; low confidence marks unresolved overlap, exchange, or a tentative correlation. These are ordinal evidence labels, not probabilities.

An assignment table must retain the nucleus, chemical shift, integral or qualitative integration status, multiplicity, coupling values where resolved, atom label, confidence, and alternative assignments. Formula, symmetry, atom count, and exchangeable-proton behavior constrain assignments but do not replace observed correlations.

## 2D correlation consistency

For each COSY, HSQC, HMBC, or NOE/ROE claim, record the observed cross-peak, expected atom pair, acquisition settings, and transfer limitations. COSY supports coupled spin relationships; HSQC supports a directly bonded heteronuclear pair under the selected sequence; HMBC constrains longer-range relationships but does not by itself prove a unique bond path.

Check the full proposed network against atom counts, symmetry, chemical-shift plausibility, and all confidently assigned cross-peaks. A single attractive HMBC or NOE/ROE peak cannot override contradictory correlations. Record whether an expected peak was observed, absent with adequate sensitivity, or not diagnostic. Treat absence as a contradiction only when the pulse sequence, coupling, mixing time, concentration, signal-to-noise, and relaxation make the peak reasonably observable.

## Referencing, solvent, and sample state

Record solvent identity, isotopic composition when known, concentration, temperature, pH or apparent pH for exchange-sensitive systems, field strength, reference compound, referencing convention, and referencing uncertainty. State whether shifts were referenced to an internal standard, residual solvent, or an external reference. Do not silently translate between conventions.

Solvent, concentration, temperature, ionization state, hydrogen bonding, aggregation, and exchange can move or broaden resonances. Keep solvent and water signals distinct from analyte assignments; document suppression, solvent subtraction, or masking. Re-check a decisive shift under an alternative defensible reference and against minimally processed data.

## Source dependencies and independence

Group spectra from the same preparation, aliquot, instrument session, and shared processing pipeline. A 1D spectrum and 2D experiments from one sample share sample-state and calibration uncertainty; they add different constraints but are not independent sample replication. Reprocessing one FID with several parameter sets is a sensitivity analysis, not replication.

Pin pulse-program and processing software versions, sequence parameters, reference convention, and any database or calculated-shift release. Preserve vendor FIDs, conversion settings, nmrML exports when practical, and hashes. If an assignment guided acquisition of a later experiment, mark that selection dependence and keep a predeclared diagnostic experiment distinct where possible.

## Assignment uncertainty

Report shift uncertainty and assignment ambiguity separately. For shifts, record digital resolution, line width, referencing uncertainty, and any calibration or fitting error that affects the conclusion. For integrals and couplings, retain the integration window, overlap, baseline, line-shape assumptions, and unresolved multiplet structure.

Propagate uncertainty for any quantitative NMR measurand, including concentration, standard purity, relaxation, pulse calibration, integration, and sampling components that materially affect it. Report units and the decision rule. Do not give extra decimal places to an assignment whose uncertainty is dominated by overlap or a disputed reference.

## Controls and sanity checks

Check the reference signal, phase, baseline, digital-filter correction, expected solvent peaks, and known impurity regions before assigning weak features. Use a solvent blank or process blank to identify contaminants. Where available, a known reference compound or repeat acquisition should reproduce diagnostic shifts and coupling patterns.

Use an independent diagnostic correlation or a separate experiment to test a proposed unique connectivity when the initial 2D network is underdetermined. For relative stereochemistry, state whether NOE/ROE build-up and mixing-time controls support proximity rather than spin diffusion. A control failure limits only the claims that depend on it; preserve the failed trace and do not tune acceptance after seeing the sample.

## Sensitivity analyses

Vary only defensible choices capable of changing a claim: phase, baseline, apodization, zero filling, reference peak or convention, peak-picking thresholds, integration boundaries, overlap grouping, and solvent or temperature assumptions. For correlations, examine alternative cross-peak assignments and plausible transfer-efficiency limits.

Report the assignment and claim status under each variation. A result is fragile if a defensible processing or referencing choice changes the atom assignment, breaks 2D network consistency, changes relative-stereo interpretation, or changes the status. Downgrade and name the smallest resolving experiment, such as a repeat with a different solvent, a selective 1D experiment, or an additional long-range correlation.

## Applicability domain

Limit conclusions to the declared solution state, solvent, temperature, concentration, field strength, nuclei, pulse sequences, signal-to-noise, and processing range. These criteria do not transfer automatically to solids, highly exchanging systems, mixtures with unresolved components, quadrupolar nuclei with broad lines, or spectra lacking raw acquisition data.

Achiral solution NMR alone cannot establish absolute stereochemistry. Relative stereochemistry requires interpretable coupling or spatial evidence and a stated conformational model; NOE/ROE intensity is not a direct distance without the relevant motion and mixing assumptions. Predicted shifts and database matches are comparison evidence, not measurements.

## Common failure modes and detection

- **Wrong shift reference:** compare residual solvent or standard signals with the recorded convention; recalculate only with a documented transformation and retain the original values.
- **Processing-created or suppressed peak:** compare raw/minimally processed and final spectra, inspect phase and baseline near the feature, and downgrade if the signal depends on aggressive processing.
- **False 2D link:** inspect the local cross-peak, noise, artifacts, and sequence conditions; check whether the rest of the proposed network is internally consistent.
- **Overlap treated as one resonance:** inspect line shape, multiplicity, integral, temperature/solvent response, and alternative decompositions; retain unresolved atoms as ambiguous.
- **Stereochemistry beyond the experiment:** check chirality of the environment, conformational exchange, NOE/ROE build-up, coupling model, and presence of an independent chiral measurement.
- **False replication:** compare aliquot, acquisition-session, and processing lineage; group shared observations rather than counting them as independent support.

## Confidence escalation and stereo claims

Escalate an atom assignment only after checking the full spin-system context. High confidence requires a unique assignment consistent with observed 1D and diagnostic 2D data; moderate confidence retains a named alternative; low confidence records an unresolved overlap, weak or indirect correlation, or shift-only analogy.

For connectivity, write the atom-pair path supported by each correlation and identify any bond or ring closure that depends on an ambiguous HMBC interpretation. If two proposed connectivities satisfy the observed network, report both as unresolved rather than selecting one by shift fit alone.

For relative stereochemistry, state the conformational assumptions behind coupling or NOE/ROE interpretation and the alternative conformers that could reverse it. For absolute stereochemistry, name the independent chiral measurement or reference comparison; an achiral spectrum cannot make that assignment.

Before reporting a resolved atom label, preserve the raw peak coordinates and local noise context that support it. If chemical exchange produces multiple states, report the state-specific assignment and acquisition conditions rather than averaging peaks into one shift.

When an expected correlation is absent, distinguish an insensitive experiment from a truly informative negative result. Name the sequence setting or signal limitation that determines detectability and retain the absence in the claim record.

## Quantitation and mixture limits

Do not infer concentration from proton integration unless relaxation delay, pulse calibration, standard purity, excitation, baseline, and integration selectivity support the measurand. Report integral normalization and any overlap or exchange that limits quantitation.

For mixtures, preserve component-specific signals and note when multiple constituents share a resonance. An apparent integral or symmetry pattern can reflect an unresolved mixture; use separation or another diagnostic experiment before assigning a single-component structure.

## Sources and boundaries

Ernst, Bodenhausen, and Wokaun (1987), *Principles of Nuclear Magnetic Resonance in One and Two Dimensions*, supports the interpretation of NMR experiments and transfer behavior. The nmrML standard describes NMR data interchange and metadata; it is not an assignment-confidence framework. Consult docs/ANALYTICAL_SOURCES.md for the repository's scoped tool and source capabilities.
