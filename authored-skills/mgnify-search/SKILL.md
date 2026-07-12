---
name: mgnify-search
description: "Discover public microbiome and metagenomics studies through MGnify. Use for biome, sample, assembly, taxonomic, functional, or public microbiome dataset questions."
license: MIT
---

# MGnify Search

1. Call `science_search_mgnify` with a biome, host, disease, location, assay, or accession query.
2. Verify study/sample/analysis level, biome ontology, host, sequencing method, pipeline version, and public status.
3. Preserve sample and study identifiers; do not collapse repeated subjects, sites, or longitudinal samples.
4. Record accession, release, pipeline, query, and files used with `$science-provenance`.

Do not compare abundance across studies without accounting for extraction, sequencing, pipeline, compositionality, batch, and sampling design.

Source basis: [MGnify API](https://www.ebi.ac.uk/metagenomics/api/v1/).
