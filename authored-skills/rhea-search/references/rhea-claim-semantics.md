# Rhea claim and dependency semantics

## Claim classes

Separate: (1) reaction-record identity; (2) participant/equation identity; (3) direction; (4) curated enzyme or EC association; (5) linked UniProt protein or pathway annotation; and (6) measured organism-specific catalysis or flux. Claims 1–5 are database claims and must cite the specific release and record. Claim 6 needs experimental evidence matched to organism, conditions, and assay; Rhea alone cannot support it.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable`. A missing result is not a contradiction. `Supported` means that the pinned source explicitly contains the matching record/annotation; it does not transfer automatically to a biological claim.

## Reaction identity and direction

Rhea represents participants as ChEBI entities with stoichiometric coefficients and may retain localization or qualifiers. Preserve stereochemistry, charge/protonation state, coefficients, and any compartment/location that affects identity. Do not merge records based on names alone.

The four-reaction quartet groups a direction-undefined master reaction with forward, reverse, and bidirectional forms. The sides of the master equation do not themselves assign substrate and product roles. Select the directional Rhea ID that matches the stated direction; cross-references may attach to particular quartet members. Direction in a curated record is not proof of net flux under the queried biological conditions.

## Source dependencies and independence

Rhea, EC, UniProt and pathway resources can be connected through curated cross-references or propagated annotations. Record the exact edge and source; do not count an EC record, UniProt annotation, and Rhea link as independent evidence when they inherit the same reaction curation. UniProt or Reactome may provide distinct organism/protein context, but independence must be assessed from provenance rather than resource count.

Pin Rhea release/access time, ChEBI identifiers/state, and releases of linked resources when available. A release change may alter reaction status, identifiers, participants, or mappings. Preserve obsolete/preliminary status and never silently remap identifiers.

## Uncertainty, controls, sensitivity

Carry uncertainty for participant normalization, protonation/charge, stereochemistry, direction, compartment, curation status, cross-reference provenance, and organism relevance. Preserve null fields and unresolved mappings. Use a known curated reaction/participant as a positive control and a well-formed impossible participant combination as a negative query; confirm retrieval and explicit no-match handling.

Vary quartet member/direction, relevant taxonomic or organism filters, and linked database selection. A claim is fragile when reaction identity, directional interpretation, curation status, or linked annotation changes across plausible choices. Record settings, release, and differences; unavailable alternatives remain untested.

## Applicability and failure modes

Rhea is a curated reaction knowledgebase, not an exhaustive catalog of biological reactions and not a measurement repository. A chemically balanced equation at its reference convention may simplify protonation states; curated directional forms do not establish that a direction is feasible or used in vivo. Organism, compartment, condition, thermodynamics, kinetics, and flux require external evidence.

- Direction misread: detect by resolving all quartet members and reading the explicit direction symbol/metadata.
- False equivalence from names: detect by comparing ChEBI IDs, charge, stereochemistry, coefficients, and location.
- Redundant entries counted as independent: detect shared quartet/master identifiers or shared upstream cross-reference lineage.
- Propagated annotation treated as experiment: trace EC and UniProt evidence to the source record and evidence type.
- Missing response treated as no reaction: distinguish empty result, null field, filtered candidate, API error, truncation, and obsolete record.

## Sources

- Alcántara et al., “Rhea—a manually curated resource of biochemical reactions,” 2012: ChEBI-based reaction representation, balancing, and master/directional quartet model.
- Bansal et al., “Rhea, the reaction knowledgebase in 2022,” 2022: current resource role and cross-reference ecosystem.
- Hastings et al., “The ChEBI reference database and ontology for biologically relevant chemistry,” 2016: chemical entities and ontology identifiers.
