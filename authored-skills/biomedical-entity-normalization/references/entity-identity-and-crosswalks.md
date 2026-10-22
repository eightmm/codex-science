# Biomedical identity and crosswalks

## Claim semantics

Classify each proposed relation before using it. **Exact identity** means the same entity under the same species, namespace, and relevant version. **Equivalent representation** means a reversible or explicitly normalized form under stated rules, such as a variant representation normalized on a pinned assembly. **Related concept** means broader, narrower, part-of, orthologous, homologous, or otherwise biologically connected; it is not identity. **Ambiguous** means multiple plausible records remain. **Deprecated/merged** records a source-declared status transition while preserving the historical ID. **Unresolved** means evidence is insufficient to assign one of these relations. Record source IDs and release, transformation, supporting attributes, alternatives, uncertainty, and permitted use for every mapping.

Do not infer identity from label similarity, shared symbols, a database cross-reference alone, or a successful lookup. Gene, transcript, protein isoform, variant, disease concept, phenotype, tissue, cell type, compound form, reaction participant, organism, study, and accession each have distinct identity criteria. For genes/proteins, compare species and stable identifiers and retain paralog, pseudogene, transcript, and isoform distinctions. For variants, compare assembly, chromosome, normalized position, REF/ALT, transcript context, and transformation history. For chemicals, retain stereochemistry, tautomer, charge, salt, isotope, and role where material.

## Source dependencies and independence

Pin database/ontology name, release or assembly, query, access date, record ID, status, and response snapshot. Record missing version information explicitly. A cross-reference graph is usually propagated: multiple databases may import the same upstream record, ontology release, symbol authority, or mapping service. Group mappings by upstream source and transformation lineage; several matching registries do not constitute independent biological confirmation when they share provenance.

Keep original input, source-specific identifiers, and all alternatives. Record each normalization operation (case or punctuation normalization, left alignment, multiallelic splitting, transcript selection, liftover, ontology ancestor relation, chemical canonicalization) and its software/version when used. Never erase the source identifier after mapping or silently replace a deprecated ID with a successor.

## Uncertainty

Represent uncertainty as explicit candidate sets, relation class, source status, and rationale. Confidence is qualitative unless a calibrated mapping model has been validated for the entity class and domain. Carry uncertainty through crosswalks: a one-to-many mapping remains one-to-many downstream, and a mapping that depends on uncertain species, assembly, transcript, or chemical form cannot become certain through repeated joins. Distinguish source absence, query failure, stale record, filtered candidate, and true unresolved identity.

## Controls and sanity checks

- **Positive control:** include an unambiguous, version-pinned canonical record for each entity class in use; confirm expected identity and attributes survive the mapping path.
- **Negative control:** include a plausible near-match that differs in species, paralog, isoform, assembly, stereochemistry, or ontology granularity; confirm it is not collapsed into exact identity.
- **Round trip:** map source A to B and back where supported; require recovery of the original record or document a known lossy relation.
- **Cardinality:** report 1:1, 1:many, many:1, and many:many joins; reject accidental row multiplication or silent row loss.
- **Variant invariants:** validate REF against the pinned reference assembly, coordinate convention, allele orientation, and liftover status; never treat failed liftover as a valid coordinate.
- **Scope checks:** verify species, assembly, release, record status, and required chemical stereochemical fields before downstream retrieval.

Passing controls verifies transformation consistency for the checked records, not biological equivalence for all database records.

## Sensitivity analysis

Compare plausible source releases and authorities, alias inclusion/exclusion, species-resolution assumptions, genome assembly, transcript selection, ontology version/granularity, and chemical representation. Recompute the downstream query or aggregation for each plausible mapping when feasible. A mapping is fragile if an alternative changes entity identity, retrieved evidence, group membership, direction of an effect, or a material claim. Report affected records and retain the ambiguity rather than selecting whichever result supports the preferred conclusion.

## Applicability domain

Crosswalks apply only to the named entity class, species, namespace, release, and transformation rules. They may fail for rapidly changing symbols, incomplete organisms, non-reference assemblies, complex variants, transcript-specific effects, ancestry-dependent interpretation, context-sensitive ontology concepts, mixtures, stereoisomers, or poorly curated accessions. Identifier resolution does not establish function, pathogenicity, mechanism, target engagement, clinical relevance, or experimental validity. Stop when the unresolved distinction could change the conclusion or action.

## Common failure modes and detection

| Failure | Detection |
| --- | --- |
| Symbol collision across species or gene families | Check taxonomy and stable IDs; run a negative control for paralogs and pseudogenes. |
| Gene/protein/transcript/isoform collapse | Compare entity type and isoform/transcript-specific attributes; preserve separate IDs. |
| Variant assembly or coordinate mismatch | Validate REF against pinned assembly and inspect liftover logs and coordinate conventions. |
| Many-to-many joins silently inflate evidence | Check join cardinality and row counts before and after each crosswalk. |
| Deprecated identifiers discarded | Query record status and successor history; retain old ID and source-declared transition. |
| Ontology relatedness mistaken for equivalence | Record relation type and ancestor/descendant path; exact identity requires same concept ID/release. |
| Compound forms merged | Compare stereochemistry, charge, tautomer, salt, isotope, and role in a negative near-match. |
| Cross-database agreement overcounted | Trace upstream references/releases and group propagated mappings by lineage. |

## Sources

- NCBI Gene and Ensembl gene/transcript documentation: stable identifiers, record scope, and species-specific reference context; consult the pinned release documentation for the actual mapping.
- UniProt Consortium (2023), UniProt Knowledgebase: protein record and isoform context; database records do not by themselves prove functional equivalence.
- GA4GH Variation Representation Specification (VRS; 2022): normalized, computable representation of variation; a representation standard does not resolve clinical interpretation.
- HUGO Gene Nomenclature Committee recommendations (Wain et al., 2002): approved human gene nomenclature; symbols remain labels that require stable identifier and species context.
- Smith et al. (2007), “The OBO Foundry: coordinated evolution of ontologies to support biomedical data integration,” *Nature Biotechnology*: ontology principles and the distinction between interoperable concepts and identical records.
- FAIR Guiding Principles (Wilkinson et al., 2016): persistent identifiers and provenance support reuse but do not establish semantic identity without explicit mappings.
