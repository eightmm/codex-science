---
name: biomedical-entity-normalization
description: "Normalize genes, proteins, variants, diseases, phenotypes, compounds, reactions, tissues, cell types, organisms, studies, and accessions before multi-source biomedical research. Use whenever aliases, assemblies, releases, or identifier namespaces could change retrieval."
license: MIT
---

# Biomedical Entity Normalization

## Decision contract
Create a versioned mapping table with raw input, entity type, canonical label, stable IDs, species, assembly or release, selected record, alternatives, confidence, and rationale; preserve the original string and never overwrite ambiguity.

## Reference usage
Read [entity-identity-and-crosswalks.md](references/entity-identity-and-crosswalks.md) before selecting identifiers, transforming variants, joining namespaces, resolving ontology concepts or chemical forms, or adjudicating one-to-many mappings. It specifies identity classes, source dependencies, uncertainty, controls, sensitivity, and scope limits.

## Workflow
1. Preserve each raw string and context, then classify entity type, species, source namespace, and intended use; record unresolved type or species ambiguity.
2. Pin the relevant authority and release/assembly for each entity class; record access date, query, source record identifier, and version before interpreting matches.
3. Generate exact and alias candidates from fit-for-purpose registries; record candidate identifiers, labels, species, status, and why candidates were included or excluded.
4. Apply domain identity criteria: resolve genes and proteins across MyGene, NCBI Gene, Ensembl, and UniProt while separating paralogs, pseudogenes, transcripts, and isoforms; normalize variants by assembly, chromosome, position, REF/ALT, left alignment, multiallelic decomposition, transcript, and liftover log.
5. Resolve disease, phenotype, tissue, and cell concepts against versioned ontologies; resolve compounds and reactions with stereochemistry, tautomer, charge, salt, isotope, role, and cross-references; preserve study repository, accession, version, organism, assay, and terms.
6. Classify each mapping as exact, equivalent under a stated transformation, broader/narrower related, ambiguous, deprecated/merged, or unresolved; record rationale, alternatives, confidence, dependencies, and applicable domain.
7. Run positive and negative identity controls plus round-trip, cardinality, species, assembly, and status checks; record expected invariants and every failed check.
8. Vary alias sets, source releases, assembly/transcript choices, ontology versions, and chemical representation; record whether the selected identity or downstream retrieval changes and downgrade fragile mappings.
9. Verify that no material ambiguity is silently collapsed; retain unresolved mappings or stop when species, assembly, transcript, isoform, chemical form, ancestry, ontology concept, or accession changes interpretation.
10. Emit `entity-mapping-v1`, preserve mapping alternatives, releases, and conversion logs with `$science-provenance`, and require `$science-review` whenever mapping controls retrieval, aggregation, or a reported claim.

## Outputs
Emit one `entity-mapping-v1` record with required fields: `schema_version`, `mapping_set_id`, `source_releases`, `mappings`, `rejected near matches` (`rejected_near_matches`), `unresolved_entities`, `crosswalk_dependencies`, `one-to-many and many-to-one warnings` (`crosswalk_cardinality_warnings`), `control_results`, `sensitivity`, `limitations`, and `provenance`. Each mapping retains `raw_input`, `entity_type`, `canonical_label`, `stable_ids`, `species`, `assembly_or_release`, `selected_record`, `alternatives`, `claim_class`, `confidence`, and `rationale`.

## Boundaries
Stop when species, assembly, transcript, isoform, chemical form, ancestry, ontology concept, or accession ambiguity could change a material conclusion; do not use label similarity alone as identity. Record mappings, alternatives, source releases, and conversion logs with `$science-provenance`; require `$science-review` whenever a mapping controls retrieval, aggregation, or a reported claim. A registry match establishes an identifier relationship under its release, not biological function or clinical significance.
