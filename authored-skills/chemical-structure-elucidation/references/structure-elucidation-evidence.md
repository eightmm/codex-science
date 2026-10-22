# Structure elucidation evidence reconciliation

## Claim semantics

Use the skill's four statuses consistently. Supported means prespecified observations meet criteria for the named formula, class, connectivity, regiochemistry, relative stereochemistry, or absolute-structure claim. Contradicted means reliable evidence conflicts with that claim. Inconclusive means orthogonal evidence conflicts, is underdetermined, or leaves plausible alternatives. Unavailable means sample state, essential raw evidence, or provenance needed for reconciliation is missing.

Report confidence separately for each structural level. A formula can be supported while connectivity is inconclusive; a supported connectivity claim does not automatically establish stereochemistry. Define structural claim levels before ranking and do not collapse formula, constitution, regiochemistry, relative stereochemistry, absolute stereochemistry, tautomer, salt, solvate, and component count into one identity label.

## Orthogonal evidence integration

For each claim, identify which modality contributes the discriminating observation and what that modality can establish. Examples include accurate mass and isotope pattern for formula constraints, assigned NMR correlations for connectivity, IR/Raman bands for functional groups, chromatographic resolution for mixture separation, and diffraction for the sampled crystalline phase. A modality's signal similarity or database match generates a hypothesis; it is not independent confirmation if that same observation selected the structure.

Build a claim-to-evidence matrix with stable claim IDs, raw-data location, processing and method, units, uncertainty, dependence group, and support or contradiction. Treat orthogonal methods as independent only for the uncertainty components they do not share. Shared sample preparation, standards, instrument calibration, source databases, or candidate-selection decisions create dependence that must be disclosed.

Do not vote by modality count. Weight a result by specificity, data quality, applicability, and whether it distinguishes the alternatives at issue. Preserve unresolved conflict and state which new measurement would separate the remaining explanations.

## Rejected alternatives and isomer ambiguity

For every plausible alternative considered, record its structure identifier and the prespecified observation expected to distinguish it. State the evidence that rejects it and whether that observation was actually detectable. If no observation separates alternatives, retain them as unresolved and say “not uniquely identified.”

Distinguish constitutional, positional, stereochemical, tautomeric, salt/solvate, conformational, and mixture alternatives. Exact mass, a common fragment, one shift prediction, or a library rank rarely distinguishes all isomers. A unique structure requires observed evidence that discriminates the relevant alternatives under the actual sample and instrument conditions.

For mixtures, report components only to the resolution supported by separation and spectra. A composite spectrum or unresolved chromatographic peak cannot be forced into a single structure. Preserve the possibility that different modalities sampled different fractions, phases, or components.

## Source dependencies and independence

Record sample identity, isolation or extraction, purity, storage, aliquot, matrix, phase, and the order of measurements. Preserve instrument and method versions, calibration, processing parameters, reference/database snapshots, and cutoff dates. Pin external standards, predicted-data versions, and library releases where used.

Group evidence sharing a sample preparation, internal standard, calibration, derived database record, model, or preprocessing pathway. Repeated processing of one spectrum and repeated measurements of one aliquot are not independent sample replication. If candidate selection used a source, do not count that source again as blind validation.

## Uncertainty and reconciliation

Keep measurement uncertainty for each modality separate from uncertainty about assignments, structural alternatives, and the final ranking. Preserve units and intervals for quantitative measurements; for qualitative evidence, record ambiguity, missingness, and detectability. Propagate relevant preparation, calibration, purity, recovery, and sampling components when combining quantitative results.

Show which uncertainties are shared across evidence rows and which can change each structural claim. Do not average conflicting evidence without a justified measurement model. If uncertainty or missing provenance could change the leading structure or claim level, downgrade to inconclusive and state the resolving evidence.

## Controls and sanity checks

Verify sample identity and purity before cross-modal comparison. Use reference compounds, known mixtures, or method controls appropriate to each modality; include blanks for contamination and carryover checks for chromatography and MS. Confirm that a reported diffraction model corresponds to the measured phase and that spectroscopy and chromatography refer to the same sample fraction.

Check elemental composition, charge, unsaturation, isotope abundance, atom counts, NMR integrations and correlations, diagnostic bands, expected fragments, and observed-versus-calculated diffraction evidence where available. These are consistency checks, not substitutes for the observations needed to distinguish isomers.

Set acceptance and exclusion criteria before ranking. Retain control failures and state which claim they invalidate; do not rescue an otherwise unsupported structure by changing modality thresholds after review.

## Sensitivity analyses

Re-evaluate the ranking under defensible changes to formula/adduct assumptions, uncertain atom assignments, peak inclusion, spectral thresholds, calibration, modality weights, dependence grouping, and inclusion of plausible alternatives. Keep reserved diagnostic observations separate from evidence used to generate the structures.

Report changes in status, claim level, and ranking. The conclusion is fragile if a reasonable perturbation changes the leading structure, removes the evidence for uniqueness, or exposes a mixture explanation. Downgrade and name the smallest resolving experiment with distinct expected outcomes for the remaining alternatives.

## Applicability domain

Limit conclusions to the measured sample, phase, component separation, concentration, solvent, temperature, ionization and fragmentation settings, spectral resolution, standards, and reference coverage. Do not transfer results between isolated fractions and bulk samples without evidence that they correspond.

Single-crystal diffraction addresses the measured crystal and may not represent a solution mixture or bulk polymorph. Achiral NMR alone cannot establish absolute stereochemistry. Mass spectrometry often leaves isomer ambiguity. Area percent does not establish mass purity without validated response factors and recovery.

## Common failure modes and detection

- **Circular confirmation:** trace which observation proposed the structure and whether it is reused as confirmation; require an independent discriminating observation or lower the claim.
- **Shared evidence counted twice:** inspect sample, standard, calibration, library, and processing lineage; group correlated rows before evaluating support.
- **Rejected alternative not tested:** compare its discriminating observation with actual raw data and detectability; retain it when the test was absent or ambiguous.
- **Isomer overclaim:** inspect whether available observables distinguish positional, stereochemical, tautomeric, or conformational alternatives; report ambiguity explicitly.
- **Mixture collapsed into one identity:** inspect chromatographic resolution, duplicated or composite signals, purity evidence, and fraction history; record component-level uncertainty.
- **Cross-modal mismatch:** compare sample fraction, phase, solvent, temperature, ionization, and method conditions; withhold reconciliation when the measurements refer to different material states.
- **Unsupported confidence:** trace each claim level to its evidence rows and uncertainty; downgrade if any higher-level conclusion rests only on a database match or unvalidated score.

## Reconciliation record

For each retained structure, give the structural claim level, evidence rows that support it, contradictory rows, and the unresolved questions that prevent a stronger claim. A claim summary must be traceable back to raw observations and processing records.

For each rejected alternative, state the distinguishing observation, whether the method could detect it in this sample, and the actual result. Do not label an alternative rejected because it has a lower score when the decisive evidence is shared or was used to generate the ranking.

For a mixture, link each component claim to a resolved chromatographic peak, isolated fraction, or independently attributable spectrum. If component attribution is ambiguous, keep the mixture question in the unresolved record and report limits on component count or purity.

When a result depends on an orthogonal modality, note whether the modality measures the same physical material and what uncertainty remains shared. This keeps a cross-modal agreement from being reported as independent replication when it shares a sample, standard, or source record.

Keep unresolved questions in a separate field from rejected alternatives so missing discrimination is not mistaken for a negative result.

## Sources and boundaries

Sumner et al. (2007), “Proposed minimum reporting standards for chemical analysis,” describes metabolomics chemical-analysis reporting and identification evidence in that scope (DOI 10.1007/s11306-007-0082-2). NIST Chemistry WebBook SRD 69 provides reference data whose conditions and coverage must be checked; nmrML and HUPO-PSI mzML describe interchange metadata; IUCr CIF resources address crystallographic records. These sources do not set universal cross-modal identity thresholds.
