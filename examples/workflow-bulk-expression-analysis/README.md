# Synthetic bulk-expression fixtures

Every input, expected artifact and negative example in this directory is a synthetic fixture under the repository license. These records contain no patient, clinical or empirical biological data. Seed 1729 generated the checked-in counts using Python's standard-library `random.Random`: for each of 20 genes and eight samples, round a base count times a uniform [0.7, 1.3] multiplier. The first two genes have base 100 and a tenfold treated effect; the other 18 genes have base 1000. Four independent synthetic samples per group share two alternating batch labels. The planted effect is a software control.

`pack.json` declares groups, biological replicate assumptions, batch, empty covariates, synthetic genome/annotation versions and the fixture identifier namespace. `counts.json` and `gene-sets.json` are bound by path and SHA-256. The frozen specification includes all QC thresholds, the contrast/model, alpha values, every tested gene and the complete background; its canonical hash precedes testing by declaration. The runner cannot independently verify historical timing.

Run from the repository root:

```sh
python3 scripts/validate_bulk_expression_pack.py examples/workflow-bulk-expression-analysis/pack.json
PYTHONPATH=src:tests python3 -m unittest tests.test_workflow_bulk_expression
```

The result schema is `bulk-expression-result-v1`: complete QC, 20 gene tests with BH, three supplied set tests with BH, all negative results, immutable input/freeze hashes, declared statistical claims, limitations and unavailable independent review. `expected.json` gives portable acceptance targets: G01 and G02 selected, planted-set hypergeometric p=1/190, planted-set significance, and no null-set significance. Floating-point Welch values may differ in their last bits across platforms; tests use tolerances for known numerical probabilities.

`negative-cases.json` indexes 13 standalone negative pack records and their required finding codes: perfectly confounded batches; unlabeled post-result contrast/threshold changes; missing or selective correction; missing or incomplete background; expression/gene-set namespace and annotation mismatches; insufficient declared replicates; outlier removal without a reason or threshold; and a causal pathway claim. The two mismatched collections are also labelled synthetic fixtures. Each negative record retains its problematic declaration instead of silently repairing it. The Python entry point raises a labelled ValueError; the CLI prints `error:` and exits 2. Tests exercise each named defect, QC edges, pre-test refusal, exploratory revisions, statistics, unavailable evidence and output preservation.

Only an optional single `--output` outside this directory is written; default output is stdout. Repeated or concurrent calls leave one complete result at that destination, with the last atomic replacement winning. A kill before replacement preserves the prior complete file or leaves no result, with a possible hidden temporary file beside the destination; after replacement the complete result remains. Use separate output paths to retain multiple runs. No input, checkpoint, ref, claim register or review receipt is written. A result and review approval never establish biological, physical, clinical or causal validity.
