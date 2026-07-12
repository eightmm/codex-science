---
name: biostudies-search
description: "Discover public life-science studies and associated archive records through EMBL-EBI BioStudies. Use for ArrayExpress, supplementary-data, accession, and public dataset discovery."
license: MIT
---

# BioStudies Search

1. Call `science_search_biostudies` with a bounded biological query.
2. Filter by accession, study type, organism, assay, release date, and public availability before recommending a dataset.
3. Follow accession pages to verify files, linked publications, licenses, and download size; ask before large downloads.
4. Record query, accession, release, file manifest, and access time with `$science-provenance`.

Archive presence does not imply assay quality, complete metadata, or reuse permission.

Source basis: [BioStudies REST API](https://www.ebi.ac.uk/biostudies/help).
