# Scientific run: phewas-replication-20260712

**Question:** Do FinnGen, BioBank Japan, and UKB/TOPMed provide sufficient comparable PheWAS evidence to establish directional diabetes replication for 10:112998590-C-T?
**Review:** passed

## Plan

- **completed:** Use one explicit variant query and verify every returned response identity.
- **completed:** Retrieve at most ten associations from each public PheWAS source.
- **completed:** Count only build-verified, positive, significant diabetes phenotypes as comparable replication evidence.
- **completed:** Independently reject variant, p-value, missingness, and genome-build overclaims.

## Claims

- **descriptive-signal:** The snapshot contains positive significant diabetes-related associations in FinnGen and UKB/TOPMed. — evidence: evidence.json, result.json
- **replication-boundary:** Three-source directional replication is not established because only FinnGen has a verified build in this retrieval contract and BioBank Japan returned no comparable diabetes phenotype. — evidence: evidence.json, result.json

## Visual results

No raster image artifacts recorded.

## Files

- [evidence.json](evidence.json) — source-snapshot; SHA-256 `497c6a795b47f749671b100b9a783c1a5bcd1b0ac21f03a3a095b767f8174235`
- [result.json](result.json) — analysis-result; SHA-256 `e9733a805bcde2b4e8f75ad07bb524c3d94cab7d4023f5c2f2ca9aff514fe55f`
- [execution.log](execution.log) — execution-log; SHA-256 `72795d894ae6f8ca7b60a426b2e043e4f8332475200136d2263fc55b115a1c7c`
- [review.json](review.json) — review; SHA-256 `901c63d7d00aa05be77f85b488662475ee888b1ce79414f4d60f515898faa0df`

_Generated from `manifest.json`; this index is a derived view, not evidence._
