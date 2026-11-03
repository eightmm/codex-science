# Synthetic offline screening analysis

All compound identities, scores, labels and controls are synthetic, redistributable fixture data.
No molecules were docked and no biological efficacy is demonstrated. Two states per
compound exercise best-observed-state aggregation; all eight attempts are retained.

From the verified plugin root, run:

```sh
python3 scripts/analyze_virtual_screening.py examples/virtual-screening-campaign/screening.json
```

The expected result is `expected.json`: AP 1, constant-score AP 0.5, enrichment
2 at k=2. `accepted_analysis` means supplied-record analysis thresholds pass; it
is not a reviewed run receipt or scientific validation. Save input/output under
an actual run and register their hashes as ordinary manifest artifacts through
science-provenance. Do not register this expected result as experimental evidence.
