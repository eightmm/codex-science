---
name: pride-search
description: "Discover public proteomics projects through PRIDE Archive. Use for mass-spectrometry datasets, reanalysis candidates, protein evidence, or public-study discovery."
license: MIT
---

# PRIDE Search

1. Call `science_search_pride` with a bounded organism, disease, tissue, protein, instrument, or assay query.
2. Verify accession, organism, tissue, instrument, quantification method, publication, file availability, and license on the project page.
3. Inspect file manifests and sizes before download; ask before large transfers.
4. Record accession, release, exact query, files used, and transformations with `$science-provenance`.

Dataset discovery is not peptide/protein identification evidence until the relevant files and search parameters are inspected.

Source basis: [PRIDE Archive API](https://www.ebi.ac.uk/pride/ws/archive/v3/swagger-ui.html).
