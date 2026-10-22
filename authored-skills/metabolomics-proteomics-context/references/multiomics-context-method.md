# Metabolomics and proteomics context method

## Claim semantics

Separate **feature detection**, **chemical identity**, **abundance difference**, **pathway context**, **dataset suitability**, and **mechanism**. A feature is an instrument signal with m/z, retention time, polarity, and processing context; it is not a compound identity. An identity claim requires an explicit confidence basis such as reference-standard match or stated spectral/orthogonal evidence, with isomer and adduct ambiguity retained. An abundance claim names sample unit, contrast, normalization, effect estimate, uncertainty, and multiplicity handling. Pathway membership is annotation evidence; enrichment additionally depends on a declared background universe and mapping process. Mechanism requires evidence connecting perturbation or exposure to a relevant molecular change and phenotype, with alternatives addressed.

Use `supported` only when evidence meets the predeclared class criteria; `contradicted` for eligible conflicting evidence; `inconclusive` for unresolved ambiguity or insufficient precision; and `unavailable` when records, files, or required assay data cannot be accessed. Missing, below-detection, filtered, and failed are distinct states.

## Source dependencies and independence

Pin database/release or reported update and record query, accession, publication, study, cohort, sample identifiers, assay, processing, and file hashes. PRIDE/ProteomeXchange and metabolomics portals may expose the same study or reprocessed files; pathway databases may propagate literature annotations. Represent these provenance edges and count independent studies or biological samples, not portals, files, features, or copied records. Distinguish discovery and validation cohorts and record shared controls. Preserve chemical form, adduct, charge, modification, organism, and mapping version.

## Uncertainty

Carry identification confidence separately from abundance uncertainty. Record biological replicate count, sample unit, missingness, detection limits, quantification method, effect estimate, interval or standard error, and multiplicity correction as reported. For proteomics, distinguish peptide/protein inference ambiguity and missing-not-at-random risks; for metabolomics, distinguish signal uncertainty from structural identification. Report pathway mapping and enrichment uncertainty, background universe, and dependence among analytes. Do not combine incompatible scales or turn confidence scores into probabilities without a calibrated model.

## Controls and sanity checks

Check blanks, pooled quality-control samples, internal standards, batch/run-order drift, carryover, and replicate consistency when available. Verify expected mass/charge/adduct and retention or fragmentation evidence for identity. For proteomics inspect peptide uniqueness, protein inference, decoys/FDR policy as reported, and contaminant handling. For abundance comparisons check sample labels, biological unit, group balance, batch, normalization, and missingness by group. For enrichment verify the tested universe, mapping success, and pathway size. Missing controls must be recorded as unavailable, not silently assumed.

## Sensitivity analysis

Vary plausible entity mappings and chemical forms, identification cutoffs, normalization and missing-value policy, sample exclusions, batch adjustment, background universe, pathway mapping release, and multiple-testing policy. Report changes in identity resolution, effect direction, claim status, or pathway ranking. Treat status or direction reversal, dependence on one ambiguous mapping, or disappearance under a defensible missingness/background choice as fragile.

## Applicability domain and failure modes

A platform's detection window, extraction, ionization, digestion, instrument, and processing pipeline constrain what can be observed. Cross-study comparisons fail when matrices, units, sample units, or normalization differ. Pathway databases are incomplete and organism/version specific. Common failures include feature-to-compound overassignment, protein group ambiguity, treating missing values as zero, pseudoreplication, duplicated portal studies, and enrichment with a post hoc universe. Detect via raw metadata/provenance checks, mapping alternatives, sample-level dependency graph, missingness summaries, and declared-universe audit; narrow or stop claims when unresolved.

## Sources

The Metabolomics Standards Initiative (Sumner et al., 2007) sets reporting and identification recommendations; Proteomics Standards Initiative guidance (Deutsch et al., 2023) covers proteomics data reporting; MIAPE (Taylor et al., 2007) describes minimum proteomics information; Reactome (Gillespie et al., 2022) and Rhea (Lombardot et al., 2019) provide curated pathway/reaction context. These references inform reporting and resource use and do not establish causal mechanism or universal thresholds.
