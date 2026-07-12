---
name: proteomexchange-search
description: "Resolve a known PXD accession through ProteomeXchange. Use for cross-repository accession verification and proteomics reanalysis planning; use PRIDE for keyword discovery."
license: MIT
---

# ProteomeXchange Search

1. Obtain a PXD accession from a paper, PRIDE search, or dataset record.
2. Call `science_search_proteomexchange` with that exact accession.
3. Verify accession, hosting repository, species, instrument, publication status, keywords, and availability at the repository of record.
4. Prefer PRIDE-specific metadata when the dataset is hosted by PRIDE; keep repository-specific identifiers intact.
5. Record source, accession, release/access time, file manifest, and terms before reanalysis.

Do not infer completeness or identification quality from ProteomeXchange registration alone.

Record accessions and repository checks with `$science-provenance`; review dataset-selection claims with `$science-review`.

Source basis: [ProteomeXchange API](https://proteomecentral.proteomexchange.org/cgi/GetDataset).
