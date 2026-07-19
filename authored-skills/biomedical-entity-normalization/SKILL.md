---
name: biomedical-entity-normalization
description: "Normalize genes, proteins, variants, diseases, phenotypes, compounds, reactions, tissues, cell types, organisms, studies, and accessions before multi-source biomedical research. Use whenever aliases, assemblies, releases, or identifier namespaces could change retrieval."
license: MIT
---

# Biomedical Entity Normalization

## Decision contract
Create a versioned mapping table with raw input, entity type, canonical label, stable IDs, species, assembly or release, selected record, alternatives, confidence, and rationale; preserve the original string and never overwrite ambiguity.
## Workflow
Resolve genes and proteins across MyGene, NCBI Gene, Ensembl, and UniProt while separating paralogs, pseudogenes, transcripts, and isoforms; normalize variants by assembly, chromosome, position, REF/ALT, left alignment, multiallelic decomposition, transcript, and liftover log.
Resolve disease, phenotype, tissue, and cell concepts through versioned ontologies; resolve compounds and reactions with explicit stereochemistry, tautomer, charge, salt, isotope, role, and cross-references; preserve study repository, accession, version, organism, assay, and terms.
Validate round trips and cardinality for every crosswalk, record deprecated or merged identifiers, and propagate a mapping confidence rather than silently collapsing alternatives.
## Outputs
Return accepted mappings, rejected near matches, unresolved entities, conversion provenance, one-to-many and many-to-one warnings, and a machine-readable table reusable by every evidence lane.
## Boundaries
Stop when species, assembly, transcript, isoform, chemical form, ancestry, ontology concept, or accession ambiguity could change a material conclusion; do not use label similarity alone as identity.
Record mappings, alternatives, source releases, and conversion logs with `$science-provenance`; require `$science-review` whenever a mapping controls retrieval, aggregation, or a reported claim.
