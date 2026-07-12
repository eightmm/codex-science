---
name: biomedical-entity-normalization
description: "Normalize genes, proteins, variants, diseases, phenotypes, compounds, reactions, tissues, cell types, organisms, studies, and accessions before multi-source biomedical research. Use whenever aliases, assemblies, releases, or identifier namespaces could change retrieval."
license: MIT
---

# Biomedical Entity Normalization

Create an entity table with raw input, entity type, canonical label, stable IDs, species, release/assembly, selected record, alternatives, and rationale.

- Genes/proteins: use MyGene, NCBI Gene, Ensembl, and UniProt; keep isoforms and pseudogenes distinct.
- Variants: preserve input; verify reference allele, assembly, chromosome, position, REF/ALT, normalization, transcript, and liftover log with `$cx-dbsnp-search`/`$cx-ensembl-search`.
- Disease/phenotype/tissue/cell type: use OLS/EFO and preserve ontology version plus rejected near matches.
- Compounds/metabolites/reactions: use ChEBI, PubChem, ChEMBL, and Rhea; preserve stereochemistry, charge, salt, and role.
- Studies/datasets: preserve repository, accession, version, organism, assay, release, and terms.

Stop when a consequential ambiguity remains. Never silently choose a genome build, transcript, isoform, species, ancestry, chemical form, or ontology concept.

Record mappings and alternatives with `$science-provenance`; run `$science-review` when a mapping controls a material conclusion.
