# Do FinnGen, BioBank Japan, and UKB/TOPMed provide sufficient comparable PheWAS evidence to establish directional diabetes replication for 10:112998590-C-T?

**Run:** phewas-replication-20260712

## Status

| Review | Plan | Claims | Files |
| --- | --- | ---: | ---: |
| ✅ Passed | 4/4 complete | 2 | 4 |

## Results

### Recorded — The snapshot contains positive significant diabetes-related associations in FinnGen… (descriptive-signal)

The snapshot contains positive significant diabetes-related associations in FinnGen and UKB/TOPMed.
- **Evidence:** evidence.json, result.json

### Recorded — Three-source directional replication is not established because only FinnGen has a… (replication-boundary)

Three-source directional replication is not established because only FinnGen has a verified build in this retrieval contract and BioBank Japan returned no comparable diabetes phenotype.
- **Evidence:** evidence.json, result.json

## Limitations and next steps

No claim-specific limitations or next steps were recorded in the bundle.

## Primary files

- **Analysis result:** [result.json](result.json)

## Details

### Plan

- **✅ Complete:** Use one explicit variant query and verify every returned response identity.
- **✅ Complete:** Retrieve at most ten associations from each public PheWAS source.
- **✅ Complete:** Count only build-verified, positive, significant diabetes phenotypes as comparable replication evidence.
- **✅ Complete:** Independently reject variant, p-value, missingness, and genome-build overclaims.

### All files

- [evidence.json](evidence.json) — Source snapshot
- [result.json](result.json) — Analysis result
- [execution.log](execution.log) — Execution log
- [review.json](review.json) — Review

Full artifact metadata and SHA-256 checksums are in [manifest.json](manifest.json).

_Generated from `manifest.json` and validated hashed sidecars; this index is a derived view, not evidence._
