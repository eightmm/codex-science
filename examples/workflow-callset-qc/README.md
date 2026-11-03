# Synthetic callset QC fixtures

Every file here is redistributable synthetic test data. There is no real cohort, VCF parser, variant interpretation or clinical conclusion.

`pack.json` binds exact-byte SHA-256 identities for `rules.json`, `table.json` and `qc.json`. Rules were declared frozen before synthetic genotypes. `expected.json` duplicates the expected arithmetic report for hand-checked acceptance. `negative-cases.json` lists individual named refusal mutations; tests apply them only to temporary copies and refresh identities rather than misreporting a hash failure as a domain refusal.

Run `python3 scripts/validate_callset_qc_pack.py examples/workflow-callset-qc/pack.json`. It reads one bundle, returns unreviewed JSON and writes nothing. Argument and validation refusals are JSON on stderr with exit two. Help uses stdout with exit zero.

The table is tab-free JSON with exact ordered sample IDs. Genotypes are 0/0, 0/1, 1/1 or the missing token `./.`. Per-call depth, quality and alternate depth are explicit nonnegative numbers. Minimum quality filters site quality; call quality is retained. There is no imputation, strand flipping or multiallelic decomposition.

Hand checks: four declared controls at fixture-site-1 have counts one, two, one, giving exact Hardy-Weinberg p value one. With two, zero, two, conditional table weights are one, eight and eight thirds, giving three thirty-fifths for the observed two-sided p value. One transition and two transversions remain after frozen filters, giving Ti/Tv one half. Father has one heterozygote out of three calls. Bad-sample has no calls and unavailable heterozygosity. Four site removals retain quality, depth, allele balance and missingness reasons. The trio has a Mendelian error at fixture-site-2 and an unavailable comparison at fixture-site-6; father contradicts the declared X check. These failed controls remain in the output.

The validator is read-only. Concurrent calls or terminating a call leave the original fixture untouched. A producer interrupted between table and pack writes leaves inconsistent hashes, which are refused. The coordinator owns ordinary artifact registration, separate claim-register entries, rigor and independent review.
